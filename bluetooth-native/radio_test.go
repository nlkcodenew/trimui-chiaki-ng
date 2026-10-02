package main

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"
)

func TestFailedRestoreKeepsRecoveryMarker(t *testing.T) {
	marker := filepath.Join(t.TempDir(), "restore-bluez")
	if err := os.WriteFile(marker, []byte("/etc/init.d/bluetooth\n"), 0600); err != nil {
		t.Fatal(err)
	}
	lease := radioLease{marker: marker, restoreNeeded: true}
	if err := lease.restoreWith(func(string) error { return errors.New("service unavailable") }); err == nil {
		t.Fatal("restore failure was hidden")
	}
	if _, err := os.Stat(marker); err != nil || !lease.restoreNeeded {
		t.Fatal("recovery marker was lost", err)
	}
	called := 0
	if err := lease.restoreWith(func(path string) error {
		called++
		if path != marker {
			t.Fatalf("wrong marker %q", path)
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(marker); !os.IsNotExist(err) || lease.restoreNeeded || called != 1 {
		t.Fatal("successful restore was not committed", err)
	}
}

func TestRestoreStopsOwnedPrivateDaemonFirst(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Unix process signal test")
	}
	marker := filepath.Join(t.TempDir(), "restore-bluez")
	if err := os.WriteFile(marker, []byte("restore\n"), 0600); err != nil {
		t.Fatal(err)
	}
	command := exec.Command("sleep", "30")
	if err := command.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = command.Process.Kill() })
	lease := radioLease{
		marker: marker, restoreNeeded: true, cmd: command, done: make(chan error, 1),
	}
	go func() { lease.done <- command.Wait() }()
	if err := lease.restoreWith(func(string) error {
		if command.ProcessState == nil {
			t.Error("normal service started before the private daemon exited")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
}

func TestFirstExecutableAndStockServiceDiscovery(t *testing.T) {
	directory := t.TempDir()
	missing := filepath.Join(directory, "missing")
	service := filepath.Join(directory, "bluetooth")
	if err := os.WriteFile(service, []byte("#!/bin/sh\n"), 0644); err != nil {
		t.Fatal(err)
	}
	if got := firstExecutable([]string{missing, service}); got != service {
		t.Fatalf("got %q", got)
	}
}
