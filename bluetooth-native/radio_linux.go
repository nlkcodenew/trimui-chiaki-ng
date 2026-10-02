package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

var serviceCandidates = []string{
	"/etc/init.d/bluetooth",
	"/etc/init.d/bluetoothd",
	"/etc/init.d/S40bluetooth",
	"/etc/init.d/S40bluetoothd",
	"/etc/init.d/S50bluetooth",
	"/etc/init.d/S50bluetoothd",
	"/etc/init.d/S30bluetooth",
	"/etc/bluetooth/bluetoothd",
	"/usr/trimui/bin/bluetooth",
}

var radioInitCandidates = []string{
	"/etc/bluetooth/bt_init.sh",
	"/usr/trimui/bin/bt_init.sh",
	"/mnt/SDCARD/System/bin/bt_init.sh",
}

func runCommand(parent context.Context, limit time.Duration, path string, args ...string) error {
	ctx, cancel := context.WithTimeout(parent, limit)
	defer cancel()
	command := exec.CommandContext(ctx, path, args...)
	command.Stdout = os.Stdout
	command.Stderr = os.Stderr
	err := command.Run()
	if ctx.Err() != nil {
		return fmt.Errorf("%s: %w", path, ctx.Err())
	}
	return err
}

func pause(ctx context.Context, duration time.Duration) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(duration):
		return nil
	}
}

func firstExecutable(candidates []string) string {
	for _, candidate := range candidates {
		if info, err := os.Stat(candidate); err == nil && !info.IsDir() {
			return candidate
		}
	}
	return ""
}

func stockServicePath() string {
	if service := firstExecutable(serviceCandidates); service != "" {
		return service
	}
	for _, pattern := range []string{"/etc/init.d/*bluetooth*", "/etc/init.d/*bluez*"} {
		matches, _ := filepath.Glob(pattern)
		if service := firstExecutable(matches); service != "" {
			return service
		}
	}
	return ""
}

func radioInitializerPath() string {
	if initializer := firstExecutable(radioInitCandidates); initializer != "" {
		return initializer
	}
	for _, pattern := range []string{"/etc/bluetooth/*init*.sh", "/usr/trimui/bin/*bt*.sh"} {
		matches, _ := filepath.Glob(pattern)
		if initializer := firstExecutable(matches); initializer != "" {
			return initializer
		}
	}
	return ""
}

func commandPath(names ...string) string {
	for _, name := range names {
		if path, err := exec.LookPath(name); err == nil {
			return path
		}
		for _, prefix := range []string{"/usr/bin", "/usr/sbin", "/bin", "/sbin"} {
			path := filepath.Join(prefix, name)
			if info, err := os.Stat(path); err == nil && !info.IsDir() {
				return path
			}
		}
	}
	return ""
}

func runScript(parent context.Context, limit time.Duration, path string, args ...string) error {
	if info, err := os.Stat(path); err == nil && info.Mode()&0111 != 0 {
		return runCommand(parent, limit, path, args...)
	}
	return runCommand(parent, limit, "/bin/sh", append([]string{path}, args...)...)
}

func waitAdapter(ctx context.Context, bluezBus *bluez, limit time.Duration) error {
	deadline := time.Now().Add(limit)
	var lastErr error
	for time.Now().Before(deadline) {
		if err := ctx.Err(); err != nil {
			return err
		}
		lastErr = bluezBus.adapter()
		if lastErr == nil {
			return nil
		}
		if err := pause(ctx, 200*time.Millisecond); err != nil {
			return err
		}
	}
	return fmt.Errorf("Bluetooth adapter did not become ready: %w", lastErr)
}

func startStockBluetooth(ctx context.Context) error {
	if rfkill := commandPath("rfkill"); rfkill != "" {
		_ = runCommand(ctx, 2*time.Second, rfkill, "unblock", "bluetooth")
	}
	if service := stockServicePath(); service != "" {
		if err := runScript(ctx, 15*time.Second, service, "start"); err == nil {
			return nil
		}
	}
	if initializer := radioInitializerPath(); initializer != "" {
		if err := runScript(ctx, 18*time.Second, initializer, "start"); err == nil {
			return nil
		}
	}
	if hciconfig := commandPath("hciconfig"); hciconfig != "" {
		if err := runCommand(ctx, 4*time.Second, hciconfig, "hci0", "up"); err == nil {
			return nil
		}
	}
	return errors.New("stock OS Bluetooth service could not be started")
}

func ensureRadio(ctx context.Context, bluezBus *bluez, status func(string)) error {
	started := false
	if err := bluezBus.adapter(); err != nil {
		status("radio_start")
		fmt.Println("Starting Bluetooth using a detected stock OS service")
		if err := startStockBluetooth(ctx); err != nil {
			return err
		}
		if err := waitAdapter(ctx, bluezBus, 6*time.Second); err != nil {
			return err
		}
		started = true
	}
	// The stock daemon is often running while the controller itself is powered
	// down, which leaves the phone with no Bluetooth at all. Power it on
	// before deciding the radio is unusable.
	if err := bluezBus.powerOnAdapter(); err != nil {
		if !started {
			return err
		}
		fmt.Println("Adapter still reports no power:", err)
	} else if started || !poweredNow(bluezBus) {
		fmt.Println("Adapter powered on")
	}
	return nil
}

func poweredNow(bluezBus *bluez) bool {
	powered, ok := bluezBus.saved["Powered"].Value().(bool)
	return ok && powered
}

type radioLease struct {
	cmd           *exec.Cmd
	done          chan error
	marker        string
	restoreNeeded bool
}

// unblockRadio makes sure the controller is not held in rfkill. On this Stock
// OS hciconfig has no pkt_type/power_save/sc_only subcommands, and merely
// calling it leaves hci0 reported DOWN, so only the rfkill part is attempted.
func unblockRadio(ctx context.Context) {
	if rfkill := commandPath("rfkill"); rfkill != "" {
		if err := runCommand(ctx, 2*time.Second, rfkill, "unblock", "bluetooth"); err != nil {
			fmt.Println("rfkill unblock:", err)
		}
	}
}

func (lease *radioLease) switchToHID(ctx context.Context, bluezBus *bluez, status func(string)) error {
	if lease.marker == "" {
		return errors.New("missing recovery marker path")
	}
	bluetoothd := commandPath("bluetoothd")
	if bluetoothd == "" {
		return errors.New("bluetoothd executable not found")
	}
	service := stockServicePath()
	if service == "" {
		return errors.New("no supported stock Bluetooth service script found")
	}
	if err := os.WriteFile(lease.marker, []byte(service+"\n"), 0600); err != nil {
		return err
	}
	lease.restoreNeeded = true
	status("radio_switch")
	if err := runScript(ctx, 6*time.Second, service, "stop"); err != nil {
		return fmt.Errorf("stop stock Bluetooth service: %w", err)
	}
	deadline := time.Now().Add(3 * time.Second)
	for {
		if _, ownerErr := bluezBus.getOwner(); ownerErr != nil {
			break
		}
		if time.Now().After(deadline) {
			return errors.New("BlueZ service did not stop; refusing to kill unrelated processes")
		}
		if err := pause(ctx, 100*time.Millisecond); err != nil {
			return err
		}
	}
	lease.cmd = exec.Command(bluetoothd, "-n", "--noplugin=input")
	lease.cmd.Stdout = os.Stdout
	lease.cmd.Stderr = os.Stderr
	lease.cmd.SysProcAttr = &syscall.SysProcAttr{Pdeathsig: syscall.SIGTERM}
	if err := lease.cmd.Start(); err != nil {
		lease.cmd = nil
		return err
	}
	lease.done = make(chan error, 1)
	go func() { lease.done <- lease.cmd.Wait() }()
	if err := waitAdapter(ctx, bluezBus, 5*time.Second); err != nil {
		return err
	}
	unblockRadio(ctx)
	return nil
}

func (lease *radioLease) restore() error {
	return lease.restoreWith(restoreNormalServiceFromMarker)
}

func (lease *radioLease) restoreWith(restoreService func(string) error) error {
	if !lease.restoreNeeded {
		return nil
	}
	if lease.cmd != nil && lease.cmd.Process != nil {
		_ = lease.cmd.Process.Signal(syscall.SIGTERM)
		select {
		case <-lease.done:
		case <-time.After(2 * time.Second):
			_ = lease.cmd.Process.Kill()
			<-lease.done
		}
		lease.cmd = nil
		lease.done = nil
	}
	if err := restoreService(lease.marker); err != nil {
		return err
	}
	lease.restoreNeeded = false
	return os.Remove(lease.marker)
}

func restoreNormalServiceFromMarker(marker string) error {
	data, err := os.ReadFile(marker)
	if err != nil {
		return err
	}
	service := strings.TrimSpace(string(data))
	if service == "" {
		service = stockServicePath()
	}
	if service == "" {
		return errors.New("cannot find stock Bluetooth service for recovery")
	}
	if err = runScript(context.Background(), 8*time.Second, service, "start"); err != nil {
		return err
	}
	bus, err := connectBus()
	if err != nil {
		return err
	}
	defer bus.conn.Close()
	if err = waitAdapter(context.Background(), bus, 5*time.Second); err != nil {
		return err
	}
	// The stock daemon comes back but leaves the controller powered down, so
	// the phone sees no Bluetooth at all until something switches it on again.
	if err = bus.powerOnAdapter(); err != nil {
		return fmt.Errorf("power on adapter after restore: %w", err)
	}
	fmt.Println("Stock Bluetooth service restored and adapter powered on")
	return nil
}

func restoreNormalService() error {
	service := stockServicePath()
	if service == "" {
		return errors.New("cannot find stock Bluetooth service")
	}
	if err := runScript(context.Background(), 8*time.Second, service, "start"); err != nil {
		return err
	}
	bus, err := connectBus()
	if err != nil {
		return err
	}
	defer bus.conn.Close()
	if err = waitAdapter(context.Background(), bus, 5*time.Second); err != nil {
		return err
	}
	return bus.powerOnAdapter()
}
