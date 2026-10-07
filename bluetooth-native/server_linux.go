package main

import (
	"bytes"
	"context"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/godbus/dbus/v5"
	"golang.org/x/sys/unix"
)

func btAddress(s string) ([6]byte, error) {
	var addr [6]byte
	raw, e := hex.DecodeString(strings.ReplaceAll(s, ":", ""))
	if e != nil || len(raw) != 6 {
		return addr, fmt.Errorf("invalid Bluetooth address %q", s)
	}
	copy(addr[:], raw)
	return addr, nil
}
func addressText(addr [6]byte) string {
	return fmt.Sprintf("%02X:%02X:%02X:%02X:%02X:%02X", addr[0], addr[1], addr[2], addr[3], addr[4], addr[5])
}
func acceptedAddress(addr [6]byte) string {
	// x/sys/unix v0.33.0 reverses Addr for Bind, but Accept4's
	// anyToSockaddr copies kernel bdaddr_t unchanged (least significant byte
	// first). Convert only incoming addresses before querying BlueZ Device1.
	return addressText([6]byte{addr[5], addr[4], addr[3], addr[2], addr[1], addr[0]})
}
func bindHID(address string, listen bool) ([2]int, error) {
	fds := [2]int{-1, -1}
	addr, e := btAddress(address)
	if e != nil {
		return fds, e
	}
	for i, psm := range []uint16{17, 19} {
		fd, err := unix.Socket(unix.AF_BLUETOOTH, unix.SOCK_SEQPACKET|unix.SOCK_NONBLOCK|unix.SOCK_CLOEXEC, unix.BTPROTO_L2CAP)
		if err == nil {
			fds[i] = fd
			// struct bt_security { uint8_t level, key_size; }; MEDIUM requires
			// authentication/encryption. Binary string keeps the exact 2-byte ABI.
			err = unix.SetsockoptString(fd, 274, 4, string([]byte{2, 0}))
		}
		if err == nil {
			err = unix.Bind(fd, &unix.SockaddrL2{PSM: psm, Addr: addr})
		}
		if err == nil && listen {
			err = unix.Listen(fd, 1)
		}
		if err != nil {
			closeFDs(fds)
			return [2]int{-1, -1}, fmt.Errorf("HID PSM %d: %w", psm, err)
		}
	}
	return fds, nil
}
func closeFDs(fds [2]int) {
	for _, fd := range fds {
		if fd >= 0 {
			unix.Close(fd)
		}
	}
}

type queuedPacket struct {
	data    []byte
	created time.Time
}
type packetQueue []queuedPacket

// stallBudget is how long the peer may leave reports unread before the link
// is declared dead. Short stalls happen on a busy phone (a game hiccup
// while racing); killing the session on the first one turns a hiccup into
// a full disconnect-reconnect cycle. Anything older than stalePacket is
// shed so a recovering link never replays ancient button states.
const stallBudget = 15 * time.Second
const stalePacket = 250 * time.Millisecond

func (q *packetQueue) push(data []byte, now time.Time) error {
	if len(*q) >= 64 {
		return errors.New("HID queue overflow")
	}
	*q = append(*q, queuedPacket{append([]byte(nil), data...), now})
	return nil
}
func (q *packetQueue) flush(now time.Time, send func([]byte) (int, error)) (bool, error) {
	stalled := false
	for len(*q) > 0 {
		item := (*q)[0]
		if now.Sub(item.created) > stalePacket {
			// The peer stopped reading: shed the stale report and keep
			// the link. Fresh state keeps arriving (plus the resend
			// timer), so nothing the phone shows goes stale for long.
			*q = (*q)[1:]
			stalled = true
			continue
		}
		n, e := send(item.data)
		if errors.Is(e, unix.EAGAIN) {
			return stalled, nil
		}
		if errors.Is(e, unix.EINTR) {
			continue
		}
		if e != nil {
			return stalled, e
		}
		if n != len(item.data) {
			return stalled, errors.New("short L2CAP packet")
		}
		*q = (*q)[1:]
	}
	return stalled, nil
}

type hidServer struct {
	b                     *bluez
	input                 *inputDevice
	mapping               *padMapping
	listeners, channels   [2]int
	queues                [2]packetQueue
	pad                   padState
	current               []byte
	peer                  string
	accepted              time.Time
	suspended, pairClosed bool
	status                func(string)
	heartbeat             func()
	gesture               guardGesture
	controlMessages       int
	unmappedLogged        map[uint16]bool
	// lastReport remembers when the current report last went out, so the
	// server can resend it on a timer. lastDropReason names the last
	// channel loss for the log; the phone never explains itself.
	// stallStart marks when the current unread episode began.
	lastReport     time.Time
	stallStart     time.Time
	lastDropReason string
}

// noteUnmappedKeys reports physical buttons the active mapping has no entry
// for. The Stock OS pad emits several of them, and each one is a button the
// phone never sees, so they are named once per session to make the gap
// obvious instead of leaving the user with a dead button.
func (s *hidServer) noteUnmappedKeys() {
	for _, code := range s.pad.unmappedKeys(0) {
		if s.unmappedLogged[code] {
			continue
		}
		if s.unmappedLogged == nil {
			s.unmappedLogged = map[uint16]bool{}
		}
		s.unmappedLogged[code] = true
		fmt.Printf("Unmapped input key %d: this physical button is not sent to the phone. Run THU BUT in the app to map it.\n", code)
	}
}

func (s *hidServer) waiting() {
	if s.pairClosed {
		s.status("waiting_closed")
	} else {
		s.status("waiting")
	}
}
func (s *hidServer) disconnect(reason string) {
	s.lastDropReason = reason
	fmt.Println("HID channels dropped:", reason)
	closeFDs(s.channels)
	s.channels = [2]int{-1, -1}
	s.queues = [2]packetQueue{}
	s.peer = ""
	s.suspended = false
	s.waiting()
}

// lockDownDiscovery turns adapter discovery off once a host is connected.
// b.set records the change, so the deferred b.restore() puts it back when
// the session ends, whatever way it ends.
func (s *hidServer) lockDownDiscovery() error {
	return s.b.set("Discoverable", false)
}
func (s *hidServer) queue(which int, data []byte) {
	if s.channels[which] < 0 {
		return
	}
	if e := s.queues[which].push(data, time.Now()); e != nil {
		s.disconnect("report queue: " + e.Error())
	}
}
func (s *hidServer) emit(report []byte) {
	if bytes.Equal(s.current, report) {
		return
	}
	s.current = append([]byte(nil), report...)
	s.lastReport = time.Now()
	if s.channels[0] >= 0 && s.channels[1] >= 0 && !s.suspended {
		s.queue(1, append([]byte{hidpData | hidpRtypeInput}, report...))
	}
}

// shouldResend is true when the link is up but nothing changed for a
// while. A real DualShock streams reports continuously; resending the
// current state every few seconds keeps an idle link provably alive and
// tells "phone went quiet" apart from "we went quiet".
func (s *hidServer) shouldResend(now time.Time) bool {
	return s.channels[0] >= 0 && s.channels[1] >= 0 && !s.suspended &&
		now.Sub(s.lastReport) >= 4*time.Second
}
func (s *hidServer) accept(which int) {
	fd, sa, e := unix.Accept4(s.listeners[which], unix.SOCK_NONBLOCK|unix.SOCK_CLOEXEC)
	if e != nil {
		if e != unix.EAGAIN {
			fmt.Println("Accept:", e)
		}
		return
	}
	remote, ok := sa.(*unix.SockaddrL2)
	if !ok {
		unix.Close(fd)
		return
	}
	address := acceptedAddress(remote.Addr)
	if s.channels[which] >= 0 || (s.peer != "" && s.peer != address) || !s.b.allowedAddress(address) {
		fmt.Println("Rejected unpaired, duplicate or different peer", address)
		unix.Close(fd)
		return
	}
	if s.peer == "" {
		s.accepted = time.Now()
	}
	s.peer = address
	s.b.trustDevice(address)
	s.channels[which] = fd
	fmt.Printf("Accepted HID PSM %d from %s (control=%t interrupt=%t)\n", []int{17, 19}[which], address, s.channels[0] >= 0, s.channels[1] >= 0)
	if s.channels[0] >= 0 && s.channels[1] >= 0 {
		// Release anything the host is still holding down, then hand over the
		// real state. Without the neutral report a button that was pressed
		// before pairing stays pressed on the phone.
		s.suspended = false
		var neutral padState
		neutral.padMap = s.mapping
		s.queue(1, append([]byte{hidpData | hidpRtypeInput}, neutral.report()...))
		s.queue(1, append([]byte{hidpData | hidpRtypeInput}, s.current...))
		fmt.Println("HID connected:", address)
		s.status("connected")
		// The phone found us, so stop being findable: discovery radio
		// traffic shares 2.4 GHz with the HID link itself. b.restore()
		// in the session cleanup puts discoverability back afterwards.
		if e := s.lockDownDiscovery(); e != nil {
			fmt.Println("Optional discovery lockdown:", e)
		}
	}
}
func (s *hidServer) receive(which int) {
	buf := make([]byte, 1024)
	n, _, flags, _, e := unix.Recvmsg(s.channels[which], buf, nil, unix.MSG_DONTWAIT)
	if e == unix.EAGAIN || e == unix.EINTR {
		return
	}
	if e != nil || n == 0 || flags&unix.MSG_TRUNC != 0 {
		if n == 0 && e == nil {
			s.disconnect("peer closed HID channel")
		} else {
			s.disconnect(fmt.Sprintf("HID channel read: %v", e))
		}
		return
	}
	if which != 0 {
		return
	} // No interrupt Output reports (e.g. rumble) advertised.
	reply, action := controlResponse(buf[:n], s.current)
	if s.controlMessages < 8 {
		fmt.Printf("HID control: %x => %x action=%s\n", buf[:n], reply, action)
		s.controlMessages++
	}
	if reply != nil {
		s.queue(0, reply)
	}
	switch action {
	case "disconnect":
		s.disconnect("host requested virtual cable unplug")
	case "suspend":
		s.suspended = true
		s.queues[1] = nil
	case "resume", "protocol", "reset":
		// The host negotiated the protocol or asked for a reset: the state has
		// not changed, so hand it the current report again.
		s.suspended = false
		s.queue(1, append([]byte{hidpData | hidpRtypeInput}, s.current...))
	}
}
func (s *hidServer) flush() {
	stalled := false
	for i := range s.channels {
		fd := s.channels[i]
		if fd < 0 {
			continue
		}
		stuck, e := s.queues[i].flush(time.Now(), func(data []byte) (int, error) {
			return unix.SendmsgN(fd, data, nil, nil, unix.MSG_DONTWAIT|unix.MSG_NOSIGNAL)
		})
		if e != nil {
			s.disconnect(fmt.Sprintf("HID channel send: %v", e))
			return
		}
		stalled = stalled || stuck
	}
	if s.trackStall(stalled, time.Now()) {
		s.disconnect("HID link stalled")
	}
}

// trackStall budgets stalled sending: ride out hiccups, give up only if the
// peer reads nothing for the whole budget. Returns true to disconnect.
func (s *hidServer) trackStall(stalled bool, now time.Time) bool {
	if !stalled {
		s.stallStart = time.Time{}
		return false
	}
	if s.stallStart.IsZero() {
		s.stallStart = now
		fmt.Println("HID link stalling: shedding stale reports, keeping the link")
		return false
	}
	return now.Sub(s.stallStart) > stallBudget
}
func (s *hidServer) loop(ctx context.Context) error {
	// Do not exclusively grab evdev: the Chiaki UI and independent exit guard
	// must remain usable while this service mirrors the controls over Bluetooth.
	s.status("input_snapshot")
	if e := s.input.snapshot(&s.pad); e != nil {
		return e
	}
	s.pad.padMap = s.mapping
	s.current = s.pad.report()
	s.noteUnmappedKeys()
	s.waiting()
	signals := make(chan *dbus.Signal, 8)
	s.b.conn.Signal(signals)
	defer s.b.conn.RemoveSignal(signals)
	matchCtx, matchCancel := context.WithTimeout(ctx, 2*time.Second)
	matchErr := s.b.conn.AddMatchSignalContext(matchCtx, dbus.WithMatchInterface("org.freedesktop.DBus"), dbus.WithMatchMember("NameOwnerChanged"), dbus.WithMatchArg(0, "org.bluez"))
	matchCancel()
	if e := matchErr; e != nil {
		return e
	}
	for {
		if s.heartbeat != nil {
			s.heartbeat()
		}
		select {
		case <-ctx.Done():
			return nil
		case action := <-s.b.events:
			if action == "released" {
				return errors.New("BlueZ released the HID profile")
			}
			s.disconnect("BlueZ event: " + action)
		case sig := <-signals:
			if sig != nil && len(sig.Body) == 3 && sig.Body[0] == "org.bluez" && sig.Body[1] == s.b.owner {
				return errors.New("BlueZ service stopped")
			}
		default:
		}
		if !s.b.conn.Connected() {
			return errors.New("system D-Bus disconnected")
		}
		polls := []unix.PollFd{{Fd: int32(s.input.fd), Events: unix.POLLIN}, {Fd: int32(s.listeners[0]), Events: unix.POLLIN}, {Fd: int32(s.listeners[1]), Events: unix.POLLIN}}
		for i, fd := range s.channels {
			events := int16(unix.POLLIN)
			if len(s.queues[i]) > 0 {
				events |= unix.POLLOUT
			}
			polls = append(polls, unix.PollFd{Fd: int32(fd), Events: events})
		}
		_, e := unix.Poll(polls, 8)
		if e == unix.EINTR {
			continue
		}
		if e != nil {
			return e
		}
		if polls[0].Revents&(unix.POLLERR|unix.POLLHUP|unix.POLLNVAL) != 0 {
			return errors.New("Brick input device lost")
		}
		if polls[0].Revents&unix.POLLIN != 0 {
			if e = s.input.read(&s.pad, s.emit); e != nil {
				return e
			}
			s.noteUnmappedKeys()
		}
		for i := 0; i < 2; i++ {
			if polls[i+1].Revents&unix.POLLIN != 0 {
				s.accept(i)
			}
		}
		for i := 0; i < 2; i++ {
			// Accept/disconnect may have changed fd ownership since poll().
			if s.channels[i] < 0 || int32(s.channels[i]) != polls[i+3].Fd {
				continue
			}
			if polls[i+3].Revents&(unix.POLLERR|unix.POLLHUP|unix.POLLNVAL) != 0 {
				s.disconnect("HID channel poll error")
				break
			}
			if polls[i+3].Revents&unix.POLLIN != 0 {
				s.receive(i)
			}
		}
		now := time.Now()
		if s.gesture.update(s.pad.keys, now) != "" {
			return nil
		}
		if (s.channels[0] >= 0) != (s.channels[1] >= 0) && now.Sub(s.accepted) > 5*time.Second {
			fmt.Printf("Incomplete HID channel pair timed out (control=%t interrupt=%t)\n", s.channels[0] >= 0, s.channels[1] >= 0)
			s.disconnect("incomplete HID channel pair")
		}
		if !s.pairClosed && now.After(s.b.pairUntil) {
			s.pairClosed = true
			if e = s.b.set("Discoverable", false); e != nil {
				return e
			}
			if e = s.b.set("Pairable", false); e != nil {
				return e
			}
			if s.peer == "" {
				return errors.New("pairing window ended without a complete HID connection")
			}
		}
		s.flush()
		if s.shouldResend(now) {
			s.lastReport = now
			s.queue(1, append([]byte{hidpData | hidpRtypeInput}, s.current...))
		}
	}
}
func (s *hidServer) close() {
	if s.channels[1] >= 0 {
		// Let go of every button before the channels close, so the phone does
		// not keep a menu held down after the session ends.
		var neutral padState
		neutral.padMap = s.mapping
		s.queues[1] = nil
		s.queue(1, append([]byte{hidpData | hidpRtypeInput}, neutral.report()...))
		s.flush()
	}
	closeFDs(s.channels)
	closeFDs(s.listeners)
	s.input.close()
}
