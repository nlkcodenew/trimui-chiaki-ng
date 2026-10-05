package main

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/godbus/dbus/v5"
	"golang.org/x/sys/unix"
)

const properties = "org.freedesktop.DBus.Properties"
const adapterInterface = "org.bluez.Adapter1"
const profilePath dbus.ObjectPath = "/org/trimui/brick/hid"
const agentPath dbus.ObjectPath = "/org/trimui/brick/agent"
const pnpProfilePath dbus.ObjectPath = "/org/trimui/brick/pnp"

type managedObjects map[dbus.ObjectPath]map[string]map[string]dbus.Variant

type bluez struct {
	conn                               *dbus.Conn
	path                               dbus.ObjectPath
	owner                              string
	saved                              map[string]dbus.Variant
	changed                            []string
	pairUntil                          time.Time
	events                             chan string
	profileRegistered, agentRegistered bool
	pnpRegistered                      bool
}

func connectBus() (*bluez, error) {
	c, e := dbus.ConnectSystemBus()
	if e != nil {
		return nil, e
	}
	return &bluez{conn: c, events: make(chan string, 8)}, nil
}
func (b *bluez) call(path dbus.ObjectPath, method string, args ...interface{}) *dbus.Call {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	return b.conn.Object("org.bluez", path).CallWithContext(ctx, method, 0, args...)
}
func (b *bluez) getOwner() (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	var owner string
	e := b.conn.BusObject().CallWithContext(ctx, "org.freedesktop.DBus.GetNameOwner", 0, "org.bluez").Store(&owner)
	return owner, e
}
func (b *bluez) adapter() error {
	var objects managedObjects
	if e := b.call("/", "org.freedesktop.DBus.ObjectManager.GetManagedObjects").Store(&objects); e != nil {
		return e
	}
	for path, ifaces := range objects {
		if props, ok := ifaces[adapterInterface]; ok && strings.HasSuffix(string(path), "/hci0") {
			b.path = path
			b.saved = props
			owner, e := b.getOwner()
			if e != nil {
				return e
			}
			b.owner = owner
			return nil
		}
	}
	return fmt.Errorf("BlueZ has no hci0 adapter")
}
func (b *bluez) set(name string, value interface{}) error {
	if e := b.call(b.path, properties+".Set", adapterInterface, name, dbus.MakeVariant(value)).Err; e != nil {
		return e
	}
	for _, existing := range b.changed {
		if name == existing {
			return nil
		}
	}
	b.changed = append(b.changed, name)
	return nil
}
func (b *bluez) restore() {
	for i := len(b.changed) - 1; i >= 0; i-- {
		key := b.changed[i]
		v, ok := b.saved[key]
		if !ok {
			continue
		}
		if e := b.call(b.path, properties+".Set", adapterInterface, key, v).Err; e != nil {
			fmt.Println("Restore", key, e)
		}
	}
	b.changed = nil
}

// powerOnAdapter makes sure the controller is powered up. The Stock OS boots
// with Bluetooth enabled, but after a session the adapter is frequently left
// down, which is why a later preflight reported BLUETOOTH_OFF even though the
// stock service was running again.
func (b *bluez) powerOnAdapter() error {
	if powered, ok := b.saved["Powered"].Value().(bool); ok && powered {
		return nil
	}
	return b.set("Powered", true)
}

func (b *bluez) isPaired(device dbus.ObjectPath) bool {
	if !strings.HasPrefix(string(device), string(b.path)+"/dev_") {
		return false
	}
	var v dbus.Variant
	if e := b.call(device, properties+".Get", "org.bluez.Device1", "Paired").Store(&v); e != nil {
		return false
	}
	paired, _ := v.Value().(bool)
	return paired
}
func (b *bluez) allowedAddress(address string) bool {
	path := dbus.ObjectPath(string(b.path) + "/dev_" + strings.ReplaceAll(address, ":", "_"))
	return b.isPaired(path)
}
func rejected(why string) *dbus.Error {
	return dbus.NewError("org.bluez.Error.Rejected", []interface{}{why})
}
func (b *bluez) senderOK(sender dbus.Sender) *dbus.Error {
	if string(sender) != b.owner {
		return rejected("Only the active BlueZ service may call this object")
	}
	return nil
}
func (b *bluez) pairGate(sender dbus.Sender, device dbus.ObjectPath) *dbus.Error {
	if e := b.senderOK(sender); e != nil {
		return e
	}
	if time.Now().After(b.pairUntil) || !strings.HasPrefix(string(device), string(b.path)+"/dev_") {
		return rejected("Pairing window closed or wrong adapter")
	}
	return nil
}
func (b *bluez) notify(s string) {
	select {
	case b.events <- s:
	default:
	}
}

type agentObject struct{ b *bluez }

func (a *agentObject) Release(sender dbus.Sender) *dbus.Error { return a.b.senderOK(sender) }
func (a *agentObject) Cancel(sender dbus.Sender) *dbus.Error  { return a.b.senderOK(sender) }
func (a *agentObject) RequestAuthorization(sender dbus.Sender, d dbus.ObjectPath) *dbus.Error {
	return a.b.pairGate(sender, d)
}
func (a *agentObject) RequestConfirmation(sender dbus.Sender, d dbus.ObjectPath, passkey uint32) *dbus.Error {
	return a.b.pairGate(sender, d)
}
func (a *agentObject) AuthorizeService(sender dbus.Sender, d dbus.ObjectPath, uuid string) *dbus.Error {
	if e := a.b.senderOK(sender); e != nil {
		return e
	}
	if strings.ToLower(uuid) != hidUUID || !a.b.isPaired(d) {
		return rejected("Only paired HID hosts are allowed")
	}
	return nil
}
func (a *agentObject) RequestPinCode(sender dbus.Sender, d dbus.ObjectPath) (string, *dbus.Error) {
	return "", rejected("Legacy PIN pairing is unsupported")
}
func (a *agentObject) RequestPasskey(sender dbus.Sender, d dbus.ObjectPath) (uint32, *dbus.Error) {
	return 0, rejected("Passkey entry is unsupported")
}

type profileObject struct{ b *bluez }

func (p *profileObject) Release(sender dbus.Sender) *dbus.Error {
	if e := p.b.senderOK(sender); e != nil {
		return e
	}
	p.b.notify("released")
	return nil
}
func (p *profileObject) NewConnection(sender dbus.Sender, d dbus.ObjectPath, fd dbus.UnixFD, props map[string]dbus.Variant) *dbus.Error {
	unix.Close(int(fd))
	return rejected("This SDP-only profile owns its raw L2CAP channels")
}
func (p *profileObject) RequestDisconnection(sender dbus.Sender, d dbus.ObjectPath) *dbus.Error {
	if e := p.b.senderOK(sender); e != nil {
		return e
	}
	p.b.notify("disconnect")
	return nil
}

// trustDevice marks a remote device as Trusted so a reconnecting phone is not
// asked to authorise the HID service again. Only a device BlueZ already
// reports as Paired is trusted: that means the user confirmed the pairing on
// the phone itself.
func (b *bluez) trustDevice(address string) {
	device := dbus.ObjectPath(string(b.path) + "/dev_" + strings.ReplaceAll(address, ":", "_"))
	if !b.isPaired(device) {
		return
	}
	if e := b.call(device, properties+".Set", "org.bluez.Device1", "Trusted", dbus.MakeVariant(true)).Err; e != nil {
		fmt.Println("Trust device:", e)
		return
	}
	fmt.Println("Trusted paired device", address)
}

func (b *bluez) register() error {
	// Immutable after export: D-Bus callbacks may arrive on another goroutine.
	b.pairUntil = time.Now().Add(120 * time.Second)
	if e := b.conn.Export(&profileObject{b}, profilePath, "org.bluez.Profile1"); e != nil {
		return e
	}
	if e := b.conn.Export(&agentObject{b}, agentPath, "org.bluez.Agent1"); e != nil {
		return e
	}
	// Deliberately omit PSM: BlueZ publishes this SDP record while the process
	// owns BOTH raw HID PSMs. RegisterProfile with PSM would bind a second time.
	opts := map[string]dbus.Variant{
		"Name": dbus.MakeVariant("TrimUI Brick Pro Gamepad"), "Role": dbus.MakeVariant("server"),
		"ServiceRecord": dbus.MakeVariant(serviceRecord()), "AutoConnect": dbus.MakeVariant(false),
		"RequireAuthentication": dbus.MakeVariant(true), "RequireAuthorization": dbus.MakeVariant(true),
	}
	if e := b.call("/org/bluez", "org.bluez.ProfileManager1.RegisterProfile", profilePath, hidUUID, opts).Err; e != nil {
		return e
	}
	b.profileRegistered = true
	if hidProfile == "ds4" {
		// Best effort: the session works without it, but without a PnP
		// record the phone cannot learn Sony's VID/PID and will not bind
		// its DualShock driver.
		if e := b.registerPnp(); e != nil {
			fmt.Println("Optional PnP record:", e)
		}
	}
	if e := b.call("/org/bluez", "org.bluez.AgentManager1.RegisterAgent", agentPath, "NoInputNoOutput").Err; e != nil {
		return e
	}
	b.agentRegistered = true
	if e := b.call("/org/bluez", "org.bluez.AgentManager1.RequestDefaultAgent", agentPath).Err; e != nil {
		return e
	}
	for _, entry := range []struct {
		key   string
		value interface{}
	}{
		{"Alias", "TrimUI Brick Pro Gamepad"}, {"PairableTimeout", uint32(120)},
		{"DiscoverableTimeout", uint32(120)}, {"Pairable", true}, {"Discoverable", true},
	} {
		if e := b.set(entry.key, entry.value); e != nil {
			return e
		}
	}
	return nil
}

// registerPnp publishes a second SDP record with the PnP Device ID info.
// A PnP record takes no connections (hosts only query it), so the same
// profile object path pattern works; anything BlueZ dislikes surfaces as
// an error here and never fails the session.
func (b *bluez) registerPnp() error {
	if e := b.conn.Export(&profileObject{b}, pnpProfilePath, "org.bluez.Profile1"); e != nil {
		return e
	}
	opts := map[string]dbus.Variant{
		"Name": dbus.MakeVariant("PnP Information"), "Role": dbus.MakeVariant("server"),
		"ServiceRecord": dbus.MakeVariant(ds4PnpRecord()), "AutoConnect": dbus.MakeVariant(false),
		"RequireAuthentication": dbus.MakeVariant(false), "RequireAuthorization": dbus.MakeVariant(false),
	}
	if e := b.call("/org/bluez", "org.bluez.ProfileManager1.RegisterProfile", pnpProfilePath, pnpUUID, opts).Err; e != nil {
		return e
	}
	b.pnpRegistered = true
	fmt.Println("PnP Device ID record registered: VID 054C PID 09CC")
	return nil
}
func (b *bluez) unregister() {
	if b.agentRegistered {
		b.call("/org/bluez", "org.bluez.AgentManager1.UnregisterAgent", agentPath)
		b.agentRegistered = false
	}
	if b.pnpRegistered {
		b.call("/org/bluez", "org.bluez.ProfileManager1.UnregisterProfile", pnpProfilePath)
		b.pnpRegistered = false
	}
	if b.profileRegistered {
		b.call("/org/bluez", "org.bluez.ProfileManager1.UnregisterProfile", profilePath)
		b.profileRegistered = false
	}
}
