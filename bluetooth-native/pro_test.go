package main

import (
	"bytes"
	"encoding/binary"
	"os"
	"path/filepath"
	"testing"
)

func encodedEvent(kind, code uint16, value int32) []byte {
	event := make([]byte, 24)
	binary.LittleEndian.PutUint16(event[16:], kind)
	binary.LittleEndian.PutUint16(event[18:], code)
	binary.LittleEndian.PutUint32(event[20:], uint32(value))
	return event
}

func proPad() padState {
	return padState{ranges: map[uint16]absInfo{
		0:  {min: -32768, max: 32767},
		1:  {min: -32768, max: 32767},
		2:  {min: 0, max: 255},
		3:  {min: -32768, max: 32767},
		4:  {min: -32768, max: 32767},
		5:  {min: 0, max: 255},
		16: {min: -1, max: 1},
		17: {min: -1, max: 1},
	}}
}

func neutralReport() []byte {
	pad := proPad()
	return pad.report()
}

func TestNeutralBrickProReport(t *testing.T) {
	want := []byte{1, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}
	pad := proPad()
	if got := pad.report(); !bytes.Equal(got, want) {
		t.Fatalf("neutral report %x != %x", got, want)
	}
}

func TestBrickProReportCarriesBothSticks(t *testing.T) {
	pad := proPad()
	pad.axes[0] = -32768
	pad.axes[1] = 32767
	pad.axes[3] = 16384
	pad.axes[4] = -16384
	report := pad.report()
	if got := int16(binary.LittleEndian.Uint16(report[4:6])); got != -32768 {
		t.Fatalf("left X = %d", got)
	}
	if got := int16(binary.LittleEndian.Uint16(report[6:8])); got != 32767 {
		t.Fatalf("left Y = %d", got)
	}
	if got := int16(binary.LittleEndian.Uint16(report[8:10])); got < 16383 || got > 16385 {
		t.Fatalf("right X = %d", got)
	}
	if got := int16(binary.LittleEndian.Uint16(report[10:12])); got < -16385 || got > -16383 {
		t.Fatalf("right Y = %d", got)
	}
}

func TestBrickProDpadDoesNotReplaceLeftStick(t *testing.T) {
	pad := proPad()
	pad.axes[0] = 12000
	pad.axes[16] = -1
	pad.axes[17] = -1
	report := pad.report()
	if report[3] != 7 {
		t.Fatalf("hat = %d", report[3])
	}
	if got := int16(binary.LittleEndian.Uint16(report[4:6])); got == 0 {
		t.Fatal("left stick was erased by D-pad")
	}
}

func TestBrickProTriggersRemainAnalog(t *testing.T) {
	pad := proPad()
	pad.axes[2] = 64
	pad.axes[5] = 192
	report := pad.report()
	if report[12] != 64 || report[13] != 192 {
		t.Fatalf("triggers = %d, %d", report[12], report[13])
	}
	buttons := binary.LittleEndian.Uint16(report[1:3])
	if buttons&(1<<8) == 0 || buttons&(1<<9) == 0 {
		t.Fatalf("trigger button bits missing: %016b", buttons)
	}
}

// Both sticks must stay independent even when the pad is clamped by its
// own mapping: a test screen that remaps axes must not merge them.
func TestBothSticksStayIndependentWithHatInput(t *testing.T) {
	pad := proPad()
	pad.axes[0] = -20000
	pad.axes[4] = 20000
	pad.axes[16] = 1
	pad.axes[17] = 1
	report := pad.report()
	if report[3] != 3 {
		t.Fatalf("hat = %d", report[3])
	}
	if got := int16(binary.LittleEndian.Uint16(report[4:6])); got > -19000 {
		t.Fatalf("left X = %d", got)
	}
	if got := int16(binary.LittleEndian.Uint16(report[10:12])); got < 19000 {
		t.Fatalf("right Y = %d", got)
	}
}

func TestBrickProStickDeadzoneSuppressesCenterDrift(t *testing.T) {
	pad := proPad()
	pad.axes[0] = 900
	pad.axes[1] = -900
	report := pad.report()
	if binary.LittleEndian.Uint16(report[4:6]) != 0 || binary.LittleEndian.Uint16(report[6:8]) != 0 {
		t.Fatalf("center drift leaked into report: %x", report[4:8])
	}
	pad.axes[0] = 4000
	report = pad.report()
	if int16(binary.LittleEndian.Uint16(report[4:6])) == 0 {
		t.Fatal("real stick movement was swallowed by deadzone")
	}
}

func TestInputScorePrefersTrimUIDualStick(t *testing.T) {
	generic := &inputDevice{name: "Generic Gamepad", ranges: map[uint16]absInfo{16: {}, 17: {}}}
	pro := &inputDevice{name: "TRIMUI Player1", ranges: map[uint16]absInfo{0: {}, 1: {}, 3: {}, 4: {}, 16: {}, 17: {}}}
	if inputScore(pro) <= inputScore(generic) {
		t.Fatalf("pro score %d <= generic %d", inputScore(pro), inputScore(generic))
	}
}

// A Get Report for the input report is answered with a DATA transaction
// carrying the whole dual-stick report.
func TestGetReportReturnsFullDualStickReport(t *testing.T) {
	pad := proPad()
	report := pad.report()
	reply, action := controlResponse([]byte{hidpGetReport | hidpRtypeInput, reportID}, report)
	if action != "" || !bytes.Equal(reply, append([]byte{hidpData | hidpRtypeInput}, report...)) {
		t.Fatalf("reply=%x action=%s", reply, action)
	}
}

func TestGetReportRejectsOtherReportTypes(t *testing.T) {
	report := neutralReport()
	for _, rtype := range []byte{hidpRtypeOutput, hidpRtypeFeature} {
		reply, _ := controlResponse([]byte{hidpGetReport | rtype, reportID}, report)
		if !bytes.Equal(reply, []byte{hidpHandshake | hidpHshkErrUnsupportedReq}) {
			t.Fatalf("report type %d answered %x", rtype, reply)
		}
	}
	reply, _ := controlResponse([]byte{hidpGetReport | hidpRtypeInput, 9}, report)
	if !bytes.Equal(reply, []byte{hidpHandshake | hidpHshkErrInvalidID}) {
		t.Fatalf("unknown report id answered %x", reply)
	}
	reply, _ = controlResponse([]byte{hidpGetReport | hidpRtypeInput}, report)
	if !bytes.Equal(reply, []byte{hidpHandshake | hidpHshkErrInvalidParam}) {
		t.Fatalf("truncated request answered %x", reply)
	}
}

// The host waits for a handshake after Set Report, so it must be sent even
// though this gamepad has no output report to store.
func TestSetReportIsAcknowledged(t *testing.T) {
	report := neutralReport()
	for _, rtype := range []byte{hidpRtypeOutput, hidpRtypeFeature} {
		reply, action := controlResponse([]byte{hidpSetReport | rtype, reportID, 0, 0}, report)
		if action != "" || !bytes.Equal(reply, []byte{hidpHandshake | hidpHshkSuccessful}) {
			t.Fatalf("rtype %d reply=%x action=%s", rtype, reply, action)
		}
	}
}

// Session control: suspend, exit suspend, virtual cable unplug.
func TestHidControlSessionTransitions(t *testing.T) {
	cases := map[byte]string{
		hidpCtrlSuspend:          "suspend",
		hidpCtrlExitSuspend:      "resume",
		hidpCtrlVirtualCablePlug: "disconnect",
		hidpCtrlSoftReset:        "reset",
	}
	report := neutralReport()
	for param, want := range cases {
		reply, action := controlResponse([]byte{hidpHidControl | param}, report)
		if reply != nil {
			t.Fatalf("param %d must not be answered, got %x", param, reply)
		}
		if action != want {
			t.Fatalf("param %d action=%q want %q", param, action, want)
		}
	}
}

func TestProtocolTransactions(t *testing.T) {
	report := neutralReport()
	reply, action := controlResponse([]byte{hidpGetProtocol, hidpProtoBoot}, report)
	if action != "" || !bytes.Equal(reply, []byte{hidpHandshake | hidpHshkSuccessful, hidpProtoReport}) {
		t.Fatalf("get protocol reply=%x action=%s", reply, action)
	}
	reply, action = controlResponse([]byte{hidpSetProtocol | hidpProtoReport}, report)
	if reply != nil || action != "protocol" {
		t.Fatalf("set protocol reply=%x action=%s", reply, action)
	}
	reply, _ = controlResponse([]byte{hidpGetIdle}, report)
	if !bytes.Equal(reply, []byte{hidpHandshake | hidpHshkErrUnsupportedReq}) {
		t.Fatalf("get idle answered %x", reply)
	}
}

// Every reply must be a well formed HIDP frame: a handshake result, a protocol
// handshake pair, or a DATA transaction. The old code answered anything it did
// not recognise with a bare 0x03, which host stacks read as a broken device and
// used as a reason to drop the link.
func TestEveryReplyIsAValidHidpFrame(t *testing.T) {
	report := neutralReport()
	handshakes := map[byte]bool{
		hidpHandshake | hidpHshkSuccessful:        true,
		hidpHandshake | hidpHshkErrInvalidID:      true,
		hidpHandshake | hidpHshkErrUnsupportedReq: true,
		hidpHandshake | hidpHshkErrInvalidParam:   true,
	}
	for header := 0; header <= 0xff; header++ {
		reply, _ := controlResponse([]byte{byte(header), reportID, 0, 0, 0, 0, 0}, report)
		if len(reply) == 0 {
			continue
		}
		if reply[0] == hidpData|hidpRtypeInput {
			if !bytes.Equal(reply, append([]byte{hidpData | hidpRtypeInput}, report...)) {
				t.Fatalf("header 0x%02x answered with a truncated data frame", header)
			}
			continue
		}
		if handshakes[reply[0]] {
			// Get Protocol answers with the handshake plus the mode.
			want := 1
			if header&0xf0 == hidpGetProtocol {
				want = 2
			}
			if len(reply) != want {
				t.Fatalf("header 0x%02x answered with a %d byte handshake %x", header, len(reply), reply)
			}
			continue
		}
		t.Fatalf("header 0x%02x answered with %x, which is not a HIDP frame", header, reply)
	}
}

func TestMappingOverrideMovesButtonsAndAxes(t *testing.T) {
	mapping := defaultMapping()
	mapping.Buttons["l3"] = 318
	mapping.Buttons["r3"] = 319
	mapping.Axes["right_x"] = 6
	mapping.Axes["right_y"] = 7
	pad := padState{padMap: mapping, ranges: map[uint16]absInfo{
		0:  {min: -32768, max: 32767},
		1:  {min: -32768, max: 32767},
		3:  {min: -32768, max: 32767},
		4:  {min: -32768, max: 32767},
		6:  {min: -32768, max: 32767},
		7:  {min: -32768, max: 32767},
		2:  {min: 0, max: 255},
		5:  {min: 0, max: 255},
		16: {min: -1, max: 1},
		17: {min: -1, max: 1},
	}}
	pad.keys[318] = true
	pad.keys[319] = true
	pad.axes[6] = 32767
	report := pad.report()
	buttons := binary.LittleEndian.Uint16(report[1:3])
	if buttons&(1<<13) == 0 {
		t.Fatalf("L3 bit missing from %016b", buttons)
	}
	if buttons&(1<<14) == 0 {
		t.Fatalf("R3 bit missing from %016b", buttons)
	}
	if got := int16(binary.LittleEndian.Uint16(report[8:10])); got != 32767 {
		t.Fatalf("remapped right X = %d", got)
	}
}

// The Stock OS pad reports several physical buttons as Linux keys the built-in
// table knows nothing about. Those must be visible, otherwise a dead button
// looks like a wiring problem.
func TestUnmappedKeysAreReported(t *testing.T) {
	pad := proPad()
	pad.keys[172] = true
	pad.keys[305] = true // 305 la nut A tren may nay
	found := pad.unmappedKeys(8)
	if len(found) != 1 || found[0] != 172 {
		t.Fatalf("unmapped = %v", found)
	}
	pad.keys[305] = false
	mapping := defaultMapping()
	mapping.Buttons["a"] = 172
	pad.padMap = mapping
	if found = pad.unmappedKeys(8); len(found) != 0 {
		t.Fatalf("mapped key still reported unmapped: %v", found)
	}
}

// The map loader must ignore anything it does not recognise instead of
// accepting a nonsense code that would silently kill a button.
func TestLoadMappingRejectsUnknownNamesAndCodes(t *testing.T) {
	path := filepath.Join(t.TempDir(), "bluetooth-map.json")
	body := `{"version":1,
	"buttons":{"a":318,"l3":172,"nonsense":42,"b":9999},
	"axes":{"right_x":6,"left_y":99,"bogus":1}}`
	if err := os.WriteFile(path, []byte(body), 0600); err != nil {
		t.Fatal(err)
	}
	mapping := loadMapping(path)
	if mapping.Buttons["a"] != 318 || mapping.Buttons["l3"] != 172 {
		t.Fatalf("valid button overrides lost: %+v", mapping.Buttons)
	}
	if mapping.Buttons["b"] != 304 {
		t.Fatalf("out of range code accepted: %d", mapping.Buttons["b"])
	}
	if _, ok := mapping.Buttons["nonsense"]; ok {
		t.Fatal("unknown button name accepted")
	}
	if mapping.Axes["right_x"] != 6 || mapping.Axes["left_y"] != 1 {
		t.Fatalf("axes overrides wrong: %+v", mapping.Axes)
	}
	if _, ok := mapping.Axes["bogus"]; ok {
		t.Fatal("unknown axis name accepted")
	}
}

// Every key-coded button must land on its own code. A shared code is what makes
// the phone light several buttons at once, so the built-in table must not have
// one. L2/R2 are analog and carry no code, so they cannot collide.
func TestBuiltInTableHasNoSharedKeyCode(t *testing.T) {
	mapping := defaultMapping()
	if duplicates := mapping.duplicateButtons(); len(duplicates) != 0 {
		t.Fatalf("built-in table shares key codes: %v", duplicates)
	}
	for _, name := range []string{"a", "b", "x", "y", "l1", "r1", "l3", "r3", "select", "start"} {
		if code := mapping.code(name); code == 0 {
			t.Fatalf("%s has no key code", name)
		}
	}
}

// A is 305 and B is 304 on this device: the Stock OS firmware reports the pair
// the other way round from BTN_SOUTH/BTN_EAST. Measured on real hardware.
func TestBuiltInTableMatchesTheMeasuredDevice(t *testing.T) {
	mapping := defaultMapping()
	for _, want := range []struct {
		name string
		code uint16
	}{
		{"a", 305}, {"b", 304}, {"x", 308}, {"y", 307},
		{"l1", 310}, {"r1", 311}, {"l3", 317}, {"r3", 318},
		{"select", 314}, {"start", 315}, {"mode", 316},
	} {
		if got := mapping.code(want.name); got != want.code {
			t.Errorf("%s = %d, want %d", want.name, got, want.code)
		}
	}
	// L2/R2 must stay unmapped so a key code can never fake an analog trigger.
	for _, name := range []string{"l2", "r2"} {
		if got := mapping.code(name); got != 0 {
			t.Errorf("%s = %d, want 0 (analog axis)", name, got)
		}
	}
}

// Bit HID di theo vi tri nut tren vo may (layout Nintendo), khong theo ten:
// B duoi=bit0 (Cross), A phai=bit1 (Circle), Y trai=bit3 (Square),
// X tren=bit4 (Triangle), MENU=bit12 (nut PS). Do bang may that Android
// (Oppo Reno5, PS mode type 1, 2026-10-03): truoc day A/B va X/Y hien nguoc
// nhau vi bit di theo ten.
func TestFaceButtonsFollowPhysicalPosition(t *testing.T) {
	for _, want := range []struct {
		code uint16
		bit  uint
	}{
		{304, 0}, {305, 1}, {307, 3}, {308, 4}, {316, 12},
	} {
		pad := proPad()
		pad.keys[want.code] = true
		buttons := binary.LittleEndian.Uint16(pad.report()[1:3])
		if buttons != 1<<want.bit {
			t.Errorf("key %d lights bits %016b, want only bit %d",
				want.code, buttons, want.bit)
		}
	}
}

// A missing file is the normal case on a fresh install and must fall back to
// the built-in table without an error.
func TestLoadMappingFallsBackWhenFileIsMissing(t *testing.T) {
	mapping := loadMapping(filepath.Join(t.TempDir(), "absent.json"))
	if mapping.Buttons["a"] != 305 || mapping.Buttons["b"] != 304 ||
		mapping.Buttons["x"] != 308 || mapping.Buttons["y"] != 307 ||
		mapping.Axes["hat_x"] != 16 {
		t.Fatalf("defaults not restored: %+v", mapping.Buttons)
	}
	if _, err := os.Stat(filepath.Join(t.TempDir(), "absent.json")); err == nil {
		t.Fatal("unexpected file")
	}
}
