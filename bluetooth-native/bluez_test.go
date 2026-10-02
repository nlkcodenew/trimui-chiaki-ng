package main

import (
	"bufio"
	"bytes"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/godbus/dbus/v5"
	"github.com/godbus/dbus/v5/introspect"
)

type fakeBluez struct {
	mu             sync.Mutex
	props          map[string]dbus.Variant
	options        map[string]dbus.Variant
	profile, agent bool
}

func (f *fakeBluez) GetManagedObjects() (managedObjects, *dbus.Error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	copyProps := map[string]dbus.Variant{}
	for k, v := range f.props {
		copyProps[k] = v
	}
	return managedObjects{"/org/bluez/hci0": {adapterInterface: copyProps}}, nil
}
func (f *fakeBluez) Set(iface, key string, v dbus.Variant) *dbus.Error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if iface != adapterInterface {
		return rejected("wrong interface")
	}
	f.props[key] = v
	return nil
}
func (f *fakeBluez) Get(iface, key string) (dbus.Variant, *dbus.Error) {
	if iface == "org.bluez.Device1" && key == "Paired" {
		return dbus.MakeVariant(true), nil
	}
	return dbus.Variant{}, rejected("unknown property")
}
func (f *fakeBluez) RegisterProfile(path dbus.ObjectPath, uuid string, opts map[string]dbus.Variant) *dbus.Error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if path != profilePath || uuid != hidUUID {
		return rejected("bad profile identity")
	}
	f.options = opts
	f.profile = true
	return nil
}
func (f *fakeBluez) UnregisterProfile(path dbus.ObjectPath) *dbus.Error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.profile = false
	return nil
}
func (f *fakeBluez) RegisterAgent(path dbus.ObjectPath, capability string) *dbus.Error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if path != agentPath || capability != "NoInputNoOutput" {
		return rejected("wrong agent")
	}
	f.agent = true
	return nil
}
func (f *fakeBluez) RequestDefaultAgent(path dbus.ObjectPath) *dbus.Error { return nil }
func (f *fakeBluez) UnregisterAgent(path dbus.ObjectPath) *dbus.Error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.agent = false
	return nil
}

func privateBus(t *testing.T) string {
	t.Helper()
	if _, e := exec.LookPath("dbus-daemon"); e != nil {
		t.Skip("dbus-daemon not installed")
	}
	cmd := exec.Command("dbus-daemon", "--session", "--nofork", "--print-address=1", "--address=unix:path="+filepath.Join(t.TempDir(), "bus"))
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, e := cmd.StdoutPipe()
	if e != nil {
		t.Fatal(e)
	}
	if e = cmd.Start(); e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { cmd.Process.Kill(); cmd.Wait() })
	address, e := bufio.NewReader(out).ReadString('\n')
	if e != nil {
		cmd.Wait()
		if strings.Contains(stderr.String(), "Operation not permitted") {
			t.Skip("Execution environment does not permit a private D-Bus listening socket")
		}
		t.Fatalf("private D-Bus: %v: %s", e, stderr.String())
	}
	return strings.TrimSpace(address)
}

func TestDBusWireSignatures(t *testing.T) {
	methods := introspect.Methods(&agentObject{})
	want := map[string]string{"RequestConfirmation": "ou", "RequestAuthorization": "o", "AuthorizeService": "os"}
	for _, method := range methods {
		if expected, ok := want[method.Name]; ok {
			actual := ""
			for _, arg := range method.Args {
				if arg.Direction == "in" {
					actual += arg.Type
				}
			}
			if actual != expected {
				t.Fatalf("%s signature %q != %q", method.Name, actual, expected)
			}
			delete(want, method.Name)
		}
	}
	if len(want) != 0 {
		t.Fatal("missing exported methods", want)
	}
	for _, method := range introspect.Methods(&profileObject{}) {
		if method.Name == "NewConnection" {
			actual := ""
			for _, arg := range method.Args {
				if arg.Direction == "in" {
					actual += arg.Type
				}
			}
			if actual != "oha{sv}" {
				t.Fatal(actual)
			}
			return
		}
	}
	t.Fatal("NewConnection not exported")
}
func TestManagedObjectsDecode(t *testing.T) {
	wire := map[dbus.ObjectPath]map[string]map[string]dbus.Variant{
		"/org/bluez/hci0": {adapterInterface: {"Powered": dbus.MakeVariant(true)}},
	}
	var target managedObjects
	if e := dbus.Store([]interface{}{wire}, &target); e != nil {
		t.Fatal(e)
	}
	if target["/org/bluez/hci0"][adapterInterface]["Powered"].Value() != true {
		t.Fatal("managed objects decode failed")
	}
}
func TestDBusRegistrationAgentAndPropertyRestore(t *testing.T) {
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
		"Alias": dbus.MakeVariant("Brick (NextUI)"), "Pairable": dbus.MakeVariant(false),
		"Discoverable": dbus.MakeVariant(false), "PairableTimeout": dbus.MakeVariant(uint32(0)), "DiscoverableTimeout": dbus.MakeVariant(uint32(180)),
	}}
	phone := dbus.ObjectPath("/org/bluez/hci0/dev_12_34_56_78_9A_BC")
	for _, entry := range []struct {
		path  dbus.ObjectPath
		iface string
	}{
		{"/", "org.freedesktop.DBus.ObjectManager"}, {"/org/bluez/hci0", properties},
		{phone, properties}, {"/org/bluez", "org.bluez.ProfileManager1"}, {"/org/bluez", "org.bluez.AgentManager1"},
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
	if e = b.register(); e != nil {
		t.Fatal(e)
	}
	f.mu.Lock()
	if _, present := f.options["PSM"]; present {
		t.Error("PSM would double-bind the raw HID socket")
	}
	if !f.profile || !f.agent || f.props["Alias"].Value() != "TrimUI Brick Pro Gamepad" {
		t.Error("registration was incomplete")
	}
	f.mu.Unlock()
	proxy := fakeConn.Object(client.Names()[0], agentPath)
	if e = proxy.Call("org.bluez.Agent1.RequestConfirmation", 0, phone, uint32(123456)).Err; e != nil {
		t.Fatal("valid BlueZ callback:", e)
	}
	if e = proxy.Call("org.bluez.Agent1.AuthorizeService", 0, phone, hidUUID).Err; e != nil {
		t.Fatal(e)
	}
	if e = proxy.Call("org.bluez.Agent1.AuthorizeService", 0, phone, "0000110b-0000-1000-8000-00805f9b34fb").Err; e == nil {
		t.Fatal("non-HID service allowed")
	}
	outsider, e := dbus.Connect(address)
	if e != nil {
		t.Fatal(e)
	}
	defer outsider.Close()
	if e = outsider.Object(client.Names()[0], agentPath).Call("org.bluez.Agent1.RequestAuthorization", 0, phone).Err; e == nil {
		t.Fatal("non-BlueZ sender allowed")
	}
	b.unregister()
	b.restore()
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.profile || f.agent || f.props["Alias"].Value() != "Brick (NextUI)" || f.props["Discoverable"].Value() != false {
		t.Fatal("BlueZ state was not restored")
	}
}
func TestPairingWindowAndAdapterRestriction(t *testing.T) {
	b := &bluez{owner: ":1.2", path: "/org/bluez/hci0", pairUntil: time.Now().Add(time.Minute)}
	if e := b.pairGate(":1.2", "/org/bluez/hci0/dev_01_23_45_67_89_AB"); e != nil {
		t.Fatal(e)
	}
	if e := b.pairGate(":1.2", "/org/bluez/hci1/dev_01_23_45_67_89_AB"); e == nil {
		t.Fatal("wrong adapter allowed")
	}
	b.pairUntil = time.Now().Add(-time.Second)
	if e := b.pairGate(":1.2", "/org/bluez/hci0/dev_01_23_45_67_89_AB"); e == nil {
		t.Fatal("expired pairing window accepted")
	}
}
