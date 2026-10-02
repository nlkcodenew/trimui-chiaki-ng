package main

import (
	"testing"
	"time"

	"golang.org/x/sys/unix"
)

func TestGuardMustSeeReleaseBeforeArming(t *testing.T) {
	g := guardGesture{}
	keys := [768]bool{}
	keys[314], keys[315] = true, true
	start := time.Unix(100, 0)
	for _, delay := range []time.Duration{0, 3 * time.Second, 10 * time.Second} {
		if got := g.update(keys, start.Add(delay)); got != "" {
			t.Fatalf("held keys from preceding test caused immediate exit: %s", got)
		}
	}
	keys[314], keys[315] = false, false
	g.update(keys, start.Add(11*time.Second))
	keys[314], keys[315] = true, true
	g.update(keys, start.Add(12*time.Second))
	if got := g.update(keys, start.Add(14*time.Second)); got != "START_SELECT" {
		t.Fatal(got)
	}
}

func TestGuardContinuousHoldAndMenuFallback(t *testing.T) {
	for _, tc := range []struct {
		name string
		keys []int
		hold time.Duration
	}{{"START_SELECT", []int{314, 315}, 2 * time.Second}, {"MENU_HOLD", []int{316}, 3 * time.Second}} {
		t.Run(tc.name, func(t *testing.T) {
			g := guardGesture{}
			keys := [768]bool{}
			t0 := time.Unix(100, 0)
			g.update(keys, t0)
			for _, key := range tc.keys {
				keys[key] = true
			}
			g.update(keys, t0)
			if g.update(keys, t0.Add(tc.hold-time.Millisecond)) != "" {
				t.Fatal("early exit")
			}
			keys[tc.keys[0]] = false
			g.update(keys, t0.Add(tc.hold))
			keys[tc.keys[0]] = true
			g.update(keys, t0.Add(2*tc.hold))
			if g.update(keys, t0.Add(3*tc.hold-time.Millisecond)) != "" {
				t.Fatal("release did not reset hold")
			}
			if got := g.update(keys, t0.Add(3*tc.hold)); got != tc.name {
				t.Fatal(got)
			}
		})
	}
}

func TestObservedShortHoldsThenSuccessfulRetry(t *testing.T) {
	g := guardGesture{}
	start := time.Unix(100, 0)
	// Replay the reported key-state transitions: all three overlapping
	// holds are shorter than two seconds. Recognizing the correct buttons
	// must not bypass the physical hold test.
	trace := []struct {
		ms                    int
		selectDown, startDown bool
	}{
		{0, false, false}, {4400, true, false}, {4440, true, true},
		{4720, false, false}, {5880, true, true}, {7440, false, false},
		{8400, false, true}, {8480, true, true}, {9240, false, false},
		{12000, false, false}, {13000, true, true}, {14999, true, true},
	}
	for _, point := range trace {
		keys := [768]bool{}
		keys[314], keys[315] = point.selectDown, point.startDown
		if got := g.update(keys, start.Add(time.Duration(point.ms)*time.Millisecond)); got != "" {
			t.Fatalf("unexpected success at %d ms: %s", point.ms, got)
		}
	}
	keys := [768]bool{}
	keys[314], keys[315] = true, true
	if got := g.update(keys, start.Add(15*time.Second)); got != "START_SELECT" {
		t.Fatalf("a continuous retry should succeed in the extended window: %s", got)
	}
}

func TestInputFloodYieldsForCancellation(t *testing.T) {
	pair, e := unix.Socketpair(unix.AF_UNIX, unix.SOCK_SEQPACKET|unix.SOCK_NONBLOCK|unix.SOCK_CLOEXEC, 0)
	if e != nil {
		t.Fatal(e)
	}
	defer unix.Close(pair[0])
	defer unix.Close(pair[1])
	// Each emitted frame refills the queue: an unbounded drain would never
	// return to the server's context and heartbeat checks. Stop at 1000 to
	// make a regression fail decisively without hanging the test process.
	frame := encodedEvent(0, 0, 0)
	if _, e = unix.Write(pair[0], frame); e != nil {
		t.Fatal(e)
	}
	count := 0
	d := inputDevice{fd: pair[1]}
	if e = d.read(&padState{}, func([]byte) {
		count++
		if count < 1000 {
			if _, e := unix.Write(pair[0], frame); e != nil {
				t.Fatal(e)
			}
		}
	}); e != nil {
		t.Fatal(e)
	}
	if count != 8 {
		t.Fatalf("processed %d batches without yielding, want 8", count)
	}
	buf := make([]byte, 24)
	if n, e := unix.Read(pair[1], buf); e != nil || n != 24 {
		t.Fatal("test did not maintain backlog", n, e)
	}
}
