package main

import (
	"testing"
	"time"
)

// Every channel loss must name itself in the log: the phone never explains
// why it went away, so the reason string is the only evidence for the next
// round of disconnect diagnosis.
func TestDisconnectRecordsReason(t *testing.T) {
	s := &hidServer{channels: [2]int{7, 8}, status: func(string) {}}
	s.disconnect("peer closed HID channel")
	if s.lastDropReason != "peer closed HID channel" {
		t.Fatalf("lastDropReason = %q", s.lastDropReason)
	}
	if s.channels != [2]int{-1, -1} {
		t.Fatalf("channels = %v, want closed", s.channels)
	}
}

// The server resends the current report on an idle but healthy link, like a
// real DualShock streams continuously. Suspended or half-open links must
// stay quiet.
func TestShouldResendOnlyOnIdleHealthyLink(t *testing.T) {
	now := time.Now()
	fresh := &hidServer{channels: [2]int{7, 8}, lastReport: now}
	if fresh.shouldResend(now) {
		t.Fatal("fresh link must not resend")
	}
	idle := &hidServer{channels: [2]int{7, 8}, lastReport: now.Add(-5 * time.Second)}
	if !idle.shouldResend(now) {
		t.Fatal("idle link must resend")
	}
	suspended := &hidServer{channels: [2]int{7, 8}, suspended: true, lastReport: now.Add(-60 * time.Second)}
	if suspended.shouldResend(now) {
		t.Fatal("suspended link must stay quiet")
	}
	halfOpen := &hidServer{channels: [2]int{7, -1}, lastReport: now.Add(-60 * time.Second)}
	if halfOpen.shouldResend(now) {
		t.Fatal("half-open link must stay quiet")
	}
	down := &hidServer{channels: [2]int{-1, -1}, lastReport: now.Add(-60 * time.Second)}
	if down.shouldResend(now) {
		t.Fatal("dead link must stay quiet")
	}
}
