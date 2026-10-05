package main

import (
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"sort"
	"time"
)

const hidUUID = "00001124-0000-1000-8000-00805f9b34fb"
const reportID = 1

var descriptor, _ = hex.DecodeString("05010905a10185010509190129101500250175019510810205010939150025073500463b0165147504950181426500750495018103093009310932093516018026ff7f360000460000751095048102050209c509c4150026ff00750895028102c0")

func serviceRecord() string {
	return serviceRecordFor(hidProfile)
}

// serviceRecordFor builds the BlueZ HID service record. The ds4 profile
// advertises the DualShock descriptor and name; every other profile keeps
// the generic gamepad record byte-identical.
func serviceRecordFor(profile string) string {
	name := "TrimUI Brick Pro Gamepad"
	description := "Dual-stick Bluetooth HID gamepad"
	desc := descriptor
	if profile == "ds4" {
		name = ds4ServiceName
		description = ds4ServiceDesc
		desc = ds4Descriptor
	}
	return fmt.Sprintf(`<record>
<attribute id="0x0001"><sequence><uuid value="0x1124"/></sequence></attribute>
<attribute id="0x0004"><sequence><sequence><uuid value="0x0100"/><uint16 value="0x0011"/></sequence><sequence><uuid value="0x0011"/></sequence></sequence></attribute>
<attribute id="0x0005"><sequence><uuid value="0x1002"/></sequence></attribute>
<attribute id="0x0006"><sequence><uint16 value="0x656e"/><uint16 value="0x006a"/><uint16 value="0x0100"/></sequence></attribute>
<attribute id="0x0009"><sequence><sequence><uuid value="0x1124"/><uint16 value="0x0101"/></sequence></sequence></attribute>
<attribute id="0x000d"><sequence><sequence><sequence><uuid value="0x0100"/><uint16 value="0x0013"/></sequence><sequence><uuid value="0x0011"/></sequence></sequence></sequence></attribute>
<attribute id="0x0100"><text value="%s"/></attribute>
<attribute id="0x0101"><text value="%s"/></attribute>
<attribute id="0x0200"><uint16 value="0x0100"/></attribute>
<attribute id="0x0201"><uint16 value="0x0111"/></attribute>
<attribute id="0x0202"><uint8 value="0x08"/></attribute>
<attribute id="0x0203"><uint8 value="0x00"/></attribute>
<attribute id="0x0204"><boolean value="false"/></attribute>
<attribute id="0x0205"><boolean value="false"/></attribute>
<attribute id="0x0206"><sequence><sequence><uint8 value="0x22"/><text encoding="hex" value="%x"/></sequence></sequence></attribute>
<attribute id="0x0207"><sequence><sequence><uint16 value="0x0409"/><uint16 value="0x0100"/></sequence></sequence></attribute>
<attribute id="0x0209"><boolean value="true"/></attribute>
<attribute id="0x020a"><boolean value="false"/></attribute>
<attribute id="0x020b"><uint16 value="0x0101"/></attribute>
<attribute id="0x020d"><boolean value="true"/></attribute>
<attribute id="0x020e"><boolean value="false"/></attribute>
</record>`, name, description, desc)
}

type padState struct {
	keys   [768]bool
	axes   [64]int32
	ranges map[uint16]absInfo
	padMap *padMapping
}

func (pad *padState) mapping() *padMapping {
	if pad.padMap == nil {
		return builtinMapping
	}
	return pad.padMap
}

func (pad *padState) apply(event inputEvent) {
	switch event.kind {
	case 1:
		if event.code < 768 && (event.value == 0 || event.value == 1) {
			pad.keys[event.code] = event.value == 1
		}
	case 3:
		if event.code < 64 {
			pad.axes[event.code] = event.value
		}
	}
}

func clampDirection(value int) int {
	if value > 1 {
		return 1
	}
	if value < -1 {
		return -1
	}
	return value
}

// trigger returns one analog trigger value. A mapped key code, when the map
// has one, means "fully pulled" so a digital-only report still works. L2/R2 have
// no key code on this device and always fall through to the axis value.
func (pad *padState) trigger(axis uint16, buttonName string) byte {
	mapping := pad.mapping()
	if buttonCode := mapping.code(buttonName); buttonCode > 0 && buttonCode < 768 && pad.keys[buttonCode] {
		return 255
	}
	value := pad.axes[axis]
	limits, ok := pad.ranges[axis]
	if !ok || limits.max <= limits.min || limits.max <= 1 {
		if value > 0 {
			return 255
		}
		return 0
	}
	scaled := (int64(value) - int64(limits.min)) * 255 / (int64(limits.max) - int64(limits.min))
	if scaled < 0 {
		return 0
	}
	if scaled > 255 {
		return 255
	}
	return byte(scaled)
}

func (pad *padState) stick(axis uint16) int16 {
	limits, ok := pad.ranges[axis]
	if !ok || limits.max <= limits.min {
		return 0
	}
	value := int64(pad.axes[axis])
	center := (int64(limits.min) + int64(limits.max)) / 2
	fullSpan := int64(limits.max) - int64(limits.min)
	deadzone := fullSpan / 25
	if value >= center-deadzone && value <= center+deadzone {
		return 0
	}
	var scaled int64
	if value < center {
		span := center - int64(limits.min)
		if span <= 0 {
			return 0
		}
		scaled = (value - center) * 32768 / span
	} else {
		span := int64(limits.max) - center
		if span <= 0 {
			return 0
		}
		scaled = (value - center) * 32767 / span
	}
	if scaled < -32768 {
		scaled = -32768
	}
	if scaled > 32767 {
		scaled = 32767
	}
	return int16(scaled)
}

// hatValue reads one D-pad axis and returns -1, 0 or 1. The hat axes and the
// arrow keys are independent inputs, so both are summed and clamped later.
func (pad *padState) hatValue(axis uint16) int {
	limits, ok := pad.ranges[axis]
	if !ok || limits.max <= limits.min {
		return 0
	}
	center := (limits.min + limits.max) / 2
	value := pad.axes[axis]
	if value < center {
		return -1
	}
	if value > center {
		return 1
	}
	return 0
}

func (pad *padState) dpad() byte {
	mapping := pad.mapping()
	x := pad.hatValue(mapping.axis("hat_x"))
	y := pad.hatValue(mapping.axis("hat_y"))
	for _, code := range append([]uint16{mapping.code("dpad_right")}, dpadAliases["dpad_right"]...) {
		if code > 0 && code < 768 && pad.keys[code] {
			x++
		}
	}
	for _, code := range append([]uint16{mapping.code("dpad_left")}, dpadAliases["dpad_left"]...) {
		if code > 0 && code < 768 && pad.keys[code] {
			x--
		}
	}
	for _, code := range append([]uint16{mapping.code("dpad_down")}, dpadAliases["dpad_down"]...) {
		if code > 0 && code < 768 && pad.keys[code] {
			y++
		}
	}
	for _, code := range append([]uint16{mapping.code("dpad_up")}, dpadAliases["dpad_up"]...) {
		if code > 0 && code < 768 && pad.keys[code] {
			y--
		}
	}
	x, y = clampDirection(x), clampDirection(y)
	hats := map[[2]int]byte{{0, -1}: 0, {1, -1}: 1, {1, 0}: 2, {1, 1}: 3, {0, 1}: 4, {-1, 1}: 5, {-1, 0}: 6, {-1, -1}: 7, {0, 0}: 8}
	return hats[[2]int{x, y}]
}

func (pad *padState) report() []byte {
	if hidProfile == "ds4" {
		return ds4Report(pad)
	}
	report := make([]byte, 14)
	report[0] = reportID
	mapping := pad.mapping()
	buttons := uint16(0)
	for _, button := range hidButtons() {
		if mapping.pressed(&pad.keys, button.name) {
			buttons |= 1 << button.bit
		}
	}
	report[12] = pad.trigger(mapping.axis("l2"), "l2")
	report[13] = pad.trigger(mapping.axis("r2"), "r2")
	if report[12] > 0 {
		buttons |= 1 << 8
	}
	if report[13] > 0 {
		buttons |= 1 << 9
	}
	binary.LittleEndian.PutUint16(report[1:3], buttons)
	report[3] = pad.dpad()
	for index, name := range []string{"left_x", "left_y", "right_x", "right_y"} {
		binary.LittleEndian.PutUint16(report[4+index*2:6+index*2], uint16(pad.stick(mapping.axis(name))))
	}
	return report
}

// unmappedKeys lists the pressed Linux key codes the active mapping has no
// entry for, lowest first. A limit of zero or less means no limit.
func (pad *padState) unmappedKeys(limit int) []uint16 {
	used := pad.mapping().usedKeys()
	found := []uint16{}
	for code, down := range pad.keys {
		if !down || used[uint16(code)] {
			continue
		}
		found = append(found, uint16(code))
		if limit > 0 && len(found) >= limit {
			break
		}
	}
	sort.Slice(found, func(i, j int) bool { return found[i] < found[j] })
	return found
}

// HIDP control transaction header, matching the Bluetooth HID profile
// (net/bluetooth/hidp/hidp.h in the Linux kernel). The transaction type is the
// high nibble; the low nibble carries either a report type or a parameter.
const (
	hidpHandshake   = 0x00
	hidpHidControl  = 0x10
	hidpGetReport   = 0x40
	hidpSetReport   = 0x50
	hidpGetProtocol = 0x60
	hidpSetProtocol = 0x70
	hidpGetIdle     = 0x80
	hidpSetIdle     = 0x90
	hidpData        = 0xa0
)

const (
	hidpHshkSuccessful        = 0x00
	hidpHshkErrInvalidID      = 0x02
	hidpHshkErrUnsupportedReq = 0x03
	hidpHshkErrInvalidParam   = 0x04
)

const (
	hidpRtypeInput   = 0x01
	hidpRtypeOutput  = 0x02
	hidpRtypeFeature = 0x03
)

const (
	hidpCtrlHardReset        = 0x01
	hidpCtrlSoftReset        = 0x02
	hidpCtrlSuspend          = 0x03
	hidpCtrlExitSuspend      = 0x04
	hidpCtrlVirtualCablePlug = 0x05
)

const (
	hidpProtoBoot   = 0x00
	hidpProtoReport = 0x01
)

// controlResponse answers one HIDP control transaction and reports the session
// action it implies. A nil reply means the transaction takes no answer.
func controlResponse(packet, report []byte) ([]byte, string) {
	if len(packet) == 0 {
		return nil, "disconnect"
	}
	header := packet[0]
	switch header & 0xf0 {
	case hidpHandshake:
		// A handshake is normally device to host, so anything the host sends
		// here is not a request.
		return nil, ""

	case hidpHidControl:
		// Defined for these: suspend, exit suspend and virtual cable unplug.
		// None of them is answered, so send nothing rather than a byte the host
		// would read as a handshake.
		switch header & 0x0f {
		case hidpCtrlSuspend:
			return nil, "suspend"
		case hidpCtrlExitSuspend:
			return nil, "resume"
		case hidpCtrlVirtualCablePlug:
			return nil, "disconnect"
		case hidpCtrlSoftReset, hidpCtrlHardReset:
			return nil, "reset"
		}
		return nil, ""

	case hidpSetReport:
		// No output or feature report is advertised, so there is nothing to
		// store. The host waits for a handshake after a Set Report, so that
		// acknowledgement is mandatory.
		switch header & 0x03 {
		case hidpRtypeOutput, hidpRtypeFeature:
			return []byte{hidpHandshake | hidpHshkSuccessful}, ""
		}
		return []byte{hidpHandshake | hidpHshkErrUnsupportedReq}, ""

	case hidpGetReport:
		if header&0x03 == hidpRtypeFeature && hidProfile == "ds4" {
			// A DualShock host reads feature reports while pairing up
			// (calibration 0x05 unlocks the full input reports on a real
			// DS4). Answer the known ones with the right sizes; anything
			// else stays an error so unknown queries stay visible.
			if len(packet) < 2 {
				return []byte{hidpHandshake | hidpHshkErrInvalidParam}, ""
			}
			if reply, ok := ds4FeatureReply(packet[1]); ok {
				return reply, ""
			}
			return []byte{hidpHandshake | hidpHshkErrUnsupportedReq}, ""
		}
		if header&0x03 != hidpRtypeInput {
			return []byte{hidpHandshake | hidpHshkErrUnsupportedReq}, ""
		}
		if len(packet) < 2 {
			return []byte{hidpHandshake | hidpHshkErrInvalidParam}, ""
		}
		if int(packet[1]) != reportID {
			return []byte{hidpHandshake | hidpHshkErrInvalidID}, ""
		}
		return append([]byte{hidpData | hidpRtypeInput}, report...), ""

	case hidpGetProtocol:
		return []byte{hidpHandshake | hidpHshkSuccessful, hidpProtoReport}, ""

	case hidpSetProtocol:
		// Report mode is the only mode this descriptor supports. No reply is
		// defined, and the host learns the state from the next interrupt report.
		return nil, "protocol"

	case hidpGetIdle:
		return []byte{hidpHandshake | hidpHshkErrUnsupportedReq}, ""
	case hidpSetIdle:
		return nil, ""
	}
	return []byte{hidpHandshake | hidpHshkErrUnsupportedReq}, ""
}

type exitGesture struct{ since time.Time }

func (gesture *exitGesture) held(keys [768]bool, now time.Time) bool {
	if !keys[314] || !keys[315] {
		gesture.since = time.Time{}
		return false
	}
	if gesture.since.IsZero() {
		gesture.since = now
	}
	return now.Sub(gesture.since) >= 2*time.Second
}
