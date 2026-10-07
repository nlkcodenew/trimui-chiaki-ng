package main

import (
	"testing"
	"time"

	"github.com/godbus/dbus/v5"
	"golang.org/x/sys/unix"
)

// Discovery radio shares 2.4 GHz with the HID link, so the server turns it
// off once a host connects. The change must be tracked for restore, or the
// adapter stays invisible after the session.
func TestLockDownDiscoveryRestores(t *testing.T) {
	address := privateBus(t)
	fakeConn, e := dbus.Connect(address)
	if e != nil {
		t.Fatal(e)
	}
	defer fakeConn.Close()
	if _, e = fakeConn.RequestName("org.bluez", dbus.NameFlagDoNotQueue); e != nil {
		t.Fatal(e)
	}
	f := &fakeBluez{props: map[string]dbus.Variant{
		"Address": dbus.MakeVariant("01:23:45:67:89:AB"), "Powered": dbus.MakeVariant(true),
		"Discoverable": dbus.MakeVariant(true),
	}}
	for _, entry := range []struct {
		path  dbus.ObjectPath
		iface string
	}{
		{"/", "org.freedesktop.DBus.ObjectManager"}, {"/org/bluez/hci0", properties},
		{"/org/bluez", "org.bluez.ProfileManager1"}, {"/org/bluez", "org.bluez.AgentManager1"},
	} {
		if e = fakeConn.Export(f, entry.path, entry.iface); e != nil {
			t.Fatal(e)
		}
	}
	client, e := dbus.Connect(address)
	if e != nil {
		t.Fatal(e)
	}
	defer client.Close()
	b := &bluez{conn: client, events: make(chan string, 8)}
	if e = b.adapter(); e != nil {
		t.Fatal(e)
	}
	s := &hidServer{b: b, status: func(string) {}}
	if e = s.lockDownDiscovery(); e != nil {
		t.Fatal(e)
	}
	f.mu.Lock()
	if f.props["Discoverable"].Value() != false {
		f.mu.Unlock()
		t.Fatal("discovery still on after lockdown")
	}
	f.mu.Unlock()
	b.restore()
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.props["Discoverable"].Value() != true {
		t.Fatal("discovery was not restored after lockdown")
	}
}

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

// A stalled peer must shed stale reports but keep the link: dropping the
// session on the first hiccup is what turned GRID races into reconnect
// cycles. Only a stall longer than the whole budget kills the link.
func TestFlushShedsStaleKeepsLink(t *testing.T) {
	old := time.Now().Add(-time.Second)
	q := packetQueue{
		{data: []byte{1, 2, 3}, created: old},
		{data: []byte{4, 5, 6}, created: time.Now()},
	}
	eagain := unix.EAGAIN
	stalled, err := q.flush(time.Now(), func([]byte) (int, error) {
		return 0, eagain
	})
	if err != nil {
		t.Fatalf("shed must not error: %v", err)
	}
	if !stalled {
		t.Fatal("shed stale packet must report stalled")
	}
	if len(q) != 1 {
		t.Fatalf("queue has %d packets, want 1 fresh left", len(q))
	}
	sent := 0
	stalled, err = q.flush(time.Now(), func(data []byte) (int, error) {
		sent++
		return len(data), nil
	})
	if err != nil || stalled || sent != 1 || len(q) != 0 {
		t.Fatalf("fresh flush: err=%v stalled=%v sent=%d left=%d",
			err, stalled, sent, len(q))
	}
}

func TestTrackStallBudget(t *testing.T) {
	s := &hidServer{}
	now := time.Now()
	if s.trackStall(false, now) {
		t.Fatal("healthy link must not disconnect")
	}
	if s.trackStall(true, now) {
		t.Fatal("first stall must not disconnect")
	}
	if s.trackStall(true, now.Add(stallBudget-time.Second)) {
		t.Fatal("stall inside budget must not disconnect")
	}
	if !s.trackStall(true, now.Add(stallBudget+time.Second)) {
		t.Fatal("stall past budget must disconnect")
	}
	if s.trackStall(false, now.Add(stallBudget+2*time.Second)) {
		t.Fatal("recovered link must not disconnect")
	}
	if !s.stallStart.IsZero() {
		t.Fatal("recovery must clear the stall clock")
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
