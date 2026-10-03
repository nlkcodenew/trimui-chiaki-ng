package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"

	"golang.org/x/sys/unix"
)

const version = "0.3.2-stock"

func writeFileAtomic(path, value string) error {
	if path == "" {
		return nil
	}
	if e := os.WriteFile(path+".new", []byte(value+"\n"), 0600); e != nil {
		return e
	}
	return os.Rename(path+".new", path)
}
func check(mapping *padMapping) (string, error) {
	fmt.Println("Native backend:", version, runtime.GOARCH, "(no Python/dbus-python/GLib runtime required)")
	d, e := chooseInput()
	if e != nil {
		return "INPUT_ERROR", e
	}
	defer d.close()
	fmt.Printf("Input: %s %q; axes: %+v\n", d.path, d.name, d.ranges)
	var pad padState
	pad.padMap = mapping
	if e = d.snapshot(&pad); e != nil {
		return "INPUT_ERROR", e
	}
	// Every physical button the Stock OS pad exposes as a Linux key that the
	// active mapping ignores. Nothing is broken here, but each entry is a
	// button the phone will never see, so name it in the check output.
	if extra := pad.unmappedKeys(0); len(extra) > 0 {
		fmt.Printf("Input keys without a mapping: %v\n", pad.unmappedKeys(64))
		fmt.Println("Run THU BUT from the app to map them.")
	}
	b, e := connectBus()
	if e != nil {
		return "BUS_ERROR", e
	}
	defer b.conn.Close()
	if e = b.adapter(); e != nil {
		return "BLUETOOTH_OFF", e
	}
	fmt.Println("Adapter:", b.path, "address:", b.saved["Address"], "powered:", b.saved["Powered"])
	address, _ := b.saved["Address"].Value().(string)
	fds, e := bindHID(address, false)
	if e != nil {
		if errors.Is(e, unix.EADDRINUSE) {
			// The stock daemon owns the HID PSMs because it runs with its input
			// plugin. runSession handles this by taking the service over for
			// the session and handing it back afterwards, so this is a note
			// rather than a failure to start.
			fmt.Println("Detail: stock Bluetooth service holds the HID channels; Connect switches it temporarily")
		} else {
			return "BLUETOOTH_ERROR", e
		}
	} else {
		closeFDs(fds)
	}
	return "READY", nil
}

func runSession(ctx context.Context, status func(string), heartbeat func(), marker string, mapping *padMapping) (result error) {
	status("bus_connect")
	b, e := connectBus()
	if e != nil {
		return e
	}
	radio := &radioLease{marker: marker}
	var server *hidServer
	var originalClass uint32
	classChanged := false
	hciTool := commandPath("hciconfig")
	defer func() {
		status("restoring")
		if server != nil {
			server.close()
		}
		b.unregister()
		if classChanged {
			if e := runCommand(context.Background(), 2*time.Second, hciTool, "hci0", "class", fmt.Sprintf("0x%06x", originalClass)); e != nil {
				fmt.Println("Restore class:", e)
			}
		}
		b.restore()
		if e := radio.restore(); e != nil {
			result = fmt.Errorf("restore normal Bluetooth service: %w (session: %v)", e, result)
		}
		b.conn.Close()
	}()
	if e = ensureRadio(ctx, b, status); e != nil {
		return e
	}
	originalProperties := b.saved
	status("adapter_power")
	if e = b.set("Powered", true); e != nil {
		return e
	}
	if e = pause(ctx, 200*time.Millisecond); e != nil {
		return e
	}
	address, _ := b.saved["Address"].Value().(string)
	status("hid_listen")
	listeners, e := bindHID(address, true)
	if errors.Is(e, unix.EADDRINUSE) {
		if e = radio.switchToHID(ctx, b, status); e != nil {
			return e
		}
		if e = b.adapter(); e != nil {
			return fmt.Errorf("refresh BlueZ owner after HID switch: %w", e)
		}
		b.saved = originalProperties
		if e = b.set("Powered", true); e != nil {
			return e
		}
		if e = pause(ctx, 200*time.Millisecond); e != nil {
			return e
		}
		listeners, e = bindHID(address, true)
	}
	if e != nil {
		return e
	}
	status("input_open")
	d, e := chooseInput()
	if e != nil {
		closeFDs(listeners)
		return e
	}
	server = &hidServer{b: b, input: d, mapping: mapping, listeners: listeners, channels: [2]int{-1, -1}, status: status, heartbeat: heartbeat}
	fmt.Printf("Input selected: %s %q\n", d.path, d.name)
	status("register_profile")
	if e = b.register(); e != nil {
		return e
	}
	if value, ok := originalProperties["Class"].Value().(uint32); ok && hciTool != "" {
		status("device_class")
		originalClass = value
		if e = runCommand(ctx, 2*time.Second, hciTool, "hci0", "class", "0x002508"); e == nil {
			classChanged = true
		} else {
			fmt.Println("Optional gamepad device class:", e)
		}
	}
	return server.loop(ctx)
}
func main() {
	checkFlag := flag.Bool("check", false, "Read-only target checks")
	guardFlag := flag.Bool("guard", false, "Independent emergency button reader; no Bluetooth and no input grab")
	guardState := flag.String("guard-state", "", "Guard readiness/heartbeat file")
	cancelFile := flag.String("cancel-file", "", "Guard exit request file")
	parentPID := flag.Int("parent-pid", 0, "Guard exits when its launcher parent disappears")
	logKeys := flag.Bool("guard-log-keys", false, "Log key state changes during the exit test")
	runFlag := flag.Bool("run", false, "Start Bluetooth HID gamepad")
	recoverFlag := flag.Bool("recover", false, "Restore the normal stock OS Bluetooth service after an interrupted session")
	versionFlag := flag.Bool("version", false, "Show version")
	resultPath := flag.String("result", "", "Check result file")
	statusPath := flag.String("status-file", "", "Session status file")
	heartbeatPath := flag.String("heartbeat-file", "", "Backend heartbeat file")
	marker := flag.String("recovery-file", "", "Temporary service recovery marker")
	mapPath := flag.String("map-file", "", "Button/axis map JSON; defaults to bluetooth-map.json beside the app")
	profileFlag := flag.String("profile", "ps", "HID button bit layout: ps (positional, default) or labels (case print)")
	flag.Parse()
	if _, ok := hidButtonLayouts[*profileFlag]; ok {
		hidProfile = *profileFlag
	} else {
		fmt.Printf("Unknown HID profile %q, using ps\n", *profileFlag)
	}
	if *versionFlag {
		fmt.Println("Brick Pro Bluetooth", version, runtime.GOOS, runtime.GOARCH)
		return
	}
	if *guardFlag {
		if *guardState == "" || *cancelFile == "" {
			fmt.Fprintln(os.Stderr, "Missing guard status/cancel file")
			os.Exit(2)
		}
		ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
		defer stop()
		if e := runGuard(ctx, *guardState, *cancelFile, *parentPID, *logKeys); e != nil {
			fmt.Fprintln(os.Stderr, e)
			writeFileAtomic(*guardState, "error")
			os.Exit(1)
		}
		return
	}
	if *recoverFlag {
		if *marker == "" {
			fmt.Fprintln(os.Stderr, "Missing recovery marker")
			os.Exit(2)
		}
		if _, e := os.Stat(*marker); os.IsNotExist(e) {
			return
		}
		if e := restoreNormalServiceFromMarker(*marker); e != nil {
			fmt.Fprintln(os.Stderr, e)
			os.Exit(1)
		}
		os.Remove(*marker)
		return
	}
	mappingPath := *mapPath
	if mappingPath == "" {
		mappingPath = defaultMapPath()
	}
	mapping := loadMapping(mappingPath)
	if *checkFlag {
		result, e := check(mapping)
		fmt.Println("Preflight:", result)
		if e != nil {
			fmt.Println("Detail:", e)
		}
		if e = writeFileAtomic(*resultPath, result); e != nil {
			fmt.Fprintln(os.Stderr, e)
			os.Exit(1)
		}
		if result != "READY" {
			os.Exit(1)
		}
		return
	}
	if !*runFlag || *marker == "" {
		fmt.Fprintln(os.Stderr, "Use --check or --run --recovery-file PATH")
		os.Exit(2)
	}
	started := time.Now()
	status := func(s string) {
		fmt.Printf("[+%s] Stage: %s\n", time.Since(started).Round(time.Millisecond), s)
		os.Stdout.Sync()
		if e := writeFileAtomic(*statusPath, s); e != nil {
			fmt.Println("Status file:", e)
		}
	}
	lastBeat := time.Time{}
	beat := 0
	heartbeat := func() {
		if time.Since(lastBeat) >= time.Second {
			beat++
			writeFileAtomic(*heartbeatPath, fmt.Sprint(beat))
			lastBeat = time.Now()
		}
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
	defer stop()
	if *parentPID > 0 {
		go func(expectedParent int) {
			ticker := time.NewTicker(250 * time.Millisecond)
			defer ticker.Stop()
			for {
				select {
				case <-ctx.Done():
					return
				case <-ticker.C:
					if os.Getppid() != expectedParent {
						fmt.Println("Supervisor parent disappeared; stopping safely")
						stop()
						return
					}
				}
			}
		}(*parentPID)
	}
	status("starting")
	fmt.Println("HID button profile:", hidProfile)
	if e := runSession(ctx, status, heartbeat, *marker, mapping); e != nil {
		status("error")
		fmt.Fprintln(os.Stderr, "Bluetooth session:", e)
		os.Exit(1)
	}
	status("stopped")
	fmt.Println("Bluetooth gamepad stopped cleanly")
}
