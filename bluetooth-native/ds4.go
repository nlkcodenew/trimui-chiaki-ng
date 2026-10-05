package main

import (
	"encoding/binary"
	"hash/crc32"
)

// DualShock 4 emulation profile ("ds4") for hosts that only accept real
// controllers, notably iOS. A generic HID gamepad pairs with an iPhone but
// never becomes a controller; a DS4-shaped device does.
//
// Sources (read for wire-format facts, implementation is original):
//   - Linux kernel drivers/hid/hid-playstation.c (GPL-2.0-or-later): exact BT
//     input report 0x11 layout (78 bytes), button bits, CRC32 seed scheme,
//     feature report IDs and sizes.
//   - controllers.fandom.com Sony DualShock 4 pages (CC-BY-SA community docs):
//     BT report structures, feature reports, VID 0x054C / PID 0x09CC.
//   - esp-cpp/espp hid-rp (Apache-2.0): vendor pages 0xFF00/0xFF80, hat values,
//     touch-inactive flag, CRC seed roles.
//
// Validation, not copying: TestDS4DescriptorMatchesKernelReportMap parses
// these bytes with an independent HID item parser and asserts the report map
// equals the kernel's static_assert sizes (input 0x01/9 + 0x11/77, output
// 0x11/77, features 0x02/36 0xA3/48 0x05/40 0x06/52 ...). The iPhone test on
// real hardware is the final arbiter.
var ds4Descriptor = []byte{
	0x05, 0x01, 0x09, 0x05, 0xA1, 0x01, 0x85, 0x01, 0x09, 0x30, 0x09, 0x31,
	0x09, 0x32, 0x09, 0x35, 0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95,
	0x04, 0x81, 0x02, 0x09, 0x39, 0x15, 0x00, 0x25, 0x07, 0x75, 0x04, 0x95,
	0x01, 0x81, 0x42, 0x05, 0x09, 0x19, 0x01, 0x29, 0x0E, 0x15, 0x00, 0x25,
	0x01, 0x75, 0x01, 0x95, 0x0E, 0x81, 0x02, 0x75, 0x06, 0x95, 0x01, 0x81,
	0x01, 0x05, 0x01, 0x09, 0x33, 0x09, 0x34, 0x15, 0x00, 0x26, 0xFF, 0x00,
	0x75, 0x08, 0x95, 0x02, 0x81, 0x02, 0x06, 0x04, 0xFF, 0x85, 0x02, 0x09,
	0x24, 0x95, 0x24, 0xB1, 0x02, 0x85, 0xA3, 0x09, 0x25, 0x95, 0x30, 0xB1,
	0x02, 0x85, 0x05, 0x09, 0x26, 0x95, 0x28, 0xB1, 0x02, 0x85, 0x06, 0x09,
	0x27, 0x95, 0x34, 0xB1, 0x02, 0x85, 0x07, 0x09, 0x28, 0x95, 0x30, 0xB1,
	0x02, 0x85, 0x08, 0x09, 0x29, 0x95, 0x2F, 0xB1, 0x02, 0x85, 0x09, 0x09,
	0x2A, 0x95, 0x13, 0xB1, 0x02, 0x06, 0x03, 0xFF, 0x85, 0x03, 0x09, 0x21,
	0x95, 0x26, 0xB1, 0x02, 0x85, 0x04, 0x09, 0x22, 0x95, 0x2E, 0xB1, 0x02,
	0x85, 0xF0, 0x09, 0x47, 0x95, 0x3F, 0xB1, 0x02, 0x85, 0xF1, 0x09, 0x48,
	0x95, 0x3F, 0xB1, 0x02, 0x85, 0xF2, 0x09, 0x49, 0x95, 0x0F, 0xB1, 0x02,
	0x06, 0x00, 0xFF, 0x85, 0x11, 0x09, 0x20, 0x15, 0x00, 0x26, 0xFF, 0x00,
	0x75, 0x08, 0x95, 0x4D, 0x81, 0x02, 0x09, 0x21, 0x91, 0x02, 0x85, 0x12,
	0x09, 0x22, 0x95, 0x8D, 0x81, 0x02, 0x09, 0x23, 0x91, 0x02, 0x85, 0x13,
	0x09, 0x24, 0x95, 0xCD, 0x81, 0x02, 0x09, 0x25, 0x91, 0x02, 0x85, 0x14,
	0x09, 0x26, 0x96, 0x0D, 0x01, 0x81, 0x02, 0x09, 0x27, 0x91, 0x02, 0x85,
	0x15, 0x09, 0x28, 0x96, 0x4D, 0x01, 0x81, 0x02, 0x09, 0x29, 0x91, 0x02,
	0x85, 0x16, 0x09, 0x2A, 0x96, 0x8D, 0x01, 0x81, 0x02, 0x09, 0x2B, 0x91,
	0x02, 0x85, 0x17, 0x09, 0x2C, 0x96, 0xCD, 0x01, 0x81, 0x02, 0x09, 0x2D,
	0x91, 0x02, 0x85, 0x18, 0x09, 0x2E, 0x96, 0x0D, 0x02, 0x81, 0x02, 0x09,
	0x2F, 0x91, 0x02, 0x85, 0x19, 0x09, 0x30, 0x96, 0x22, 0x02, 0x81, 0x02,
	0x09, 0x31, 0x91, 0x02, 0x06, 0x80, 0xFF, 0x85, 0x82, 0x09, 0x22, 0x95,
	0x3F, 0xB1, 0x02, 0x85, 0x83, 0x09, 0x23, 0xB1, 0x02, 0x85, 0x84, 0x09,
	0x24, 0xB1, 0x02, 0x85, 0x90, 0x09, 0x30, 0xB1, 0x02, 0x85, 0x91, 0x09,
	0x31, 0xB1, 0x02, 0x85, 0x92, 0x09, 0x32, 0xB1, 0x02, 0x85, 0x93, 0x09,
	0x33, 0xB1, 0x02, 0x85, 0x94, 0x09, 0x34, 0xB1, 0x02, 0x85, 0xA0, 0x09,
	0x40, 0xB1, 0x02, 0x85, 0xA4, 0x09, 0x44, 0xB1, 0x02, 0x85, 0xA7, 0x09,
	0x45, 0xB1, 0x02, 0x85, 0xA8, 0x09, 0x45, 0xB1, 0x02, 0x85, 0xA9, 0x09,
	0x45, 0xB1, 0x02, 0x85, 0xAA, 0x09, 0x45, 0xB1, 0x02, 0x85, 0xAB, 0x09,
	0x45, 0xB1, 0x02, 0x85, 0xAC, 0x09, 0x45, 0xB1, 0x02, 0x85, 0xAD, 0x09,
	0x45, 0xB1, 0x02, 0x85, 0xB3, 0x09, 0x45, 0xB1, 0x02, 0x85, 0xB4, 0x09,
	0x46, 0xB1, 0x02, 0x85, 0xB5, 0x09, 0x47, 0xB1, 0x02, 0x85, 0xD0, 0x09,
	0x40, 0xB1, 0x02, 0x85, 0xD4, 0x09, 0x44, 0xB1, 0x02, 0xC0,
}

const ds4ReportID = 0x11
const ds4ReportSize = 78

// HIDP DATA|INPUT header byte. The DS4 CRC seed for input reports is 0xA1,
// which is exactly this header: the CRC covers header + report ID + payload.
const ds4InputCRCSeed = 0xA1

// HIDP DATA|FEATURE header byte, likewise the feature CRC seed.
const ds4FeatureCRCSeed = 0xA3

const ds4AdapterName = "Wireless Controller"
const ds4ServiceName = "Wireless Controller"
const ds4ServiceDesc = "Sony Wireless Controller compatible gamepad"

// pnpUUID is the Bluetooth PnPInformation service class. iOS learns a
// Bluetooth HID device's VID/PID from this record; without it the phone
// sees vendor 0 and never binds its DualShock driver (observed: paired,
// connected, zero control traffic, no controller).
const pnpUUID = "00001200-0000-1000-8000-00805f9b34fb"

// ds4PnpRecord publishes Sony's VID/PID for the ds4 profile. Attribute IDs
// follow BlueZ lib/bluetooth/sdp.h (Device ID assignments): 0x0200 spec,
// 0x0201 vendor, 0x0202 product, 0x0203 version, 0x0204 primary, 0x0205
// source. Source 0x0002 (USB IF) because Sony's VID lives in the USB
// namespace even over Bluetooth. Version is informational (0x0001).
func ds4PnpRecord() string {
	return `<record>
<attribute id="0x0001"><sequence><uuid value="0x1200"/></sequence></attribute>
<attribute id="0x0004"><sequence><sequence><uuid value="0x0100"/></sequence></sequence></attribute>
<attribute id="0x0005"><sequence><uuid value="0x1002"/></sequence></attribute>
<attribute id="0x0006"><sequence><uint16 value="0x656e"/><uint16 value="0x006a"/><uint16 value="0x0100"/></sequence></attribute>
<attribute id="0x0009"><sequence><sequence><uuid value="0x1200"/><uint16 value="0x0103"/></sequence></sequence></attribute>
<attribute id="0x0100"><text value="PnP Information"/></attribute>
<attribute id="0x0200"><uint16 value="0x0103"/></attribute>
<attribute id="0x0201"><uint16 value="0x054C"/></attribute>
<attribute id="0x0202"><uint16 value="0x09CC"/></attribute>
<attribute id="0x0203"><uint16 value="0x0001"/></attribute>
<attribute id="0x0204"><boolean value="true"/></attribute>
<attribute id="0x0205"><uint16 value="0x0002"/></attribute>
</record>`
}

// ds4CRC returns the IEEE CRC32 over seed followed by data, as the kernel's
// ps_check_crc32 does (crc32_le(0xFFFFFFFF, seed) continued over data,
// inverted at the end — identical to zlib over the concatenation).
func ds4CRC(seed byte, data []byte) uint32 {
	buf := make([]byte, 0, len(data)+1)
	buf = append(buf, seed)
	buf = append(buf, data...)
	return crc32.ChecksumIEEE(buf)
}

// ds4Stick scales one evdev axis to a DS4 stick byte (0..255, center 128).
// Brick Pro sticks report ±32767 ranges like the preflight log shows; the
// deadzone matches the generic stick() (4% of full span).
func ds4Stick(value int32, limits absInfo, ok bool) byte {
	if !ok || limits.max <= limits.min {
		return 128
	}
	span := int64(limits.max) - int64(limits.min)
	center := (int64(limits.min) + int64(limits.max)) / 2
	if span <= 0 {
		return 128
	}
	deadzone := span / 25
	v := int64(value)
	if v >= center-deadzone && v <= center+deadzone {
		return 128
	}
	var fraction float64
	if v < center {
		fraction = float64(v-center) / float64(center-int64(limits.min))
	} else {
		fraction = float64(v-center) / float64(int64(limits.max)-center)
	}
	scaled := 128 + int(fraction*127+0.5*signOf(fraction))
	if scaled < 0 {
		return 0
	}
	if scaled > 255 {
		return 255
	}
	return byte(scaled)
}

func signOf(v float64) float64 {
	if v < 0 {
		return -1
	}
	return 1
}

// ds4Hat encodes the D-pad as a DS4 hat nibble: 0=N .. 7=NW, 8=centered.
func ds4Hat(pad *padState, mapping *padMapping) byte {
	x := pad.hatValue(mapping.axis("hat_x"))
	y := pad.hatValue(mapping.axis("hat_y"))
	if mapping.code("dpad_right") > 0 && mapping.code("dpad_right") < 768 && pad.keys[mapping.code("dpad_right")] {
		x++
	}
	if mapping.code("dpad_left") > 0 && mapping.code("dpad_left") < 768 && pad.keys[mapping.code("dpad_left")] {
		x--
	}
	if mapping.code("dpad_down") > 0 && mapping.code("dpad_down") < 768 && pad.keys[mapping.code("dpad_down")] {
		y++
	}
	if mapping.code("dpad_up") > 0 && mapping.code("dpad_up") < 768 && pad.keys[mapping.code("dpad_up")] {
		y--
	}
	if x < -1 {
		x = -1
	}
	if x > 1 {
		x = 1
	}
	if y < -1 {
		y = -1
	}
	if y > 1 {
		y = 1
	}
	switch {
	case x == 0 && y == -1:
		return 0
	case x == 1 && y == -1:
		return 1
	case x == 1 && y == 0:
		return 2
	case x == 1 && y == 1:
		return 3
	case x == 0 && y == 1:
		return 4
	case x == -1 && y == 1:
		return 5
	case x == -1 && y == 0:
		return 6
	case x == -1 && y == -1:
		return 7
	default:
		return 8
	}
}

// ds4Trigger returns one analog trigger byte (0..255). Same source as the
// generic trigger(): a mapped key code means fully pulled, otherwise the
// axis value scaled by its runtime range.
func ds4Trigger(pad *padState, axis uint16, buttonName string) byte {
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

// ds4Report builds one 78-byte DualShock 4 Bluetooth input report (0x11)
// from the pad state. Buttons follow physical position like the "ps"
// profile: bottom=B→cross, right=A→circle, left=Y→square, top=X→triangle,
// MENU→PS. Everything the Brick has no sensor for stays neutral (zero
// motion, centered touch-inactive points, full-battery status byte).
func ds4Report(pad *padState) []byte {
	mapping := pad.mapping()
	report := make([]byte, ds4ReportSize)
	report[0] = ds4ReportID
	// EnableCRC + EnableHID, no audio (matches the documented header bits).
	report[1] = 0xC0
	report[2] = 0x00
	leftX, okX := pad.ranges[mapping.axis("left_x")]
	leftY, okY := pad.ranges[mapping.axis("left_y")]
	rightX, okRX := pad.ranges[mapping.axis("right_x")]
	rightY, okRY := pad.ranges[mapping.axis("right_y")]
	report[3] = ds4Stick(pad.axes[mapping.axis("left_x")], leftX, okX)
	report[4] = ds4Stick(pad.axes[mapping.axis("left_y")], leftY, okY)
	report[5] = ds4Stick(pad.axes[mapping.axis("right_x")], rightX, okRX)
	report[6] = ds4Stick(pad.axes[mapping.axis("right_y")], rightY, okRY)
	buttons0 := ds4Hat(pad, mapping) & 0x0F
	if mapping.pressed(&pad.keys, "y") {
		buttons0 |= 1 << 4 // square (left)
	}
	if mapping.pressed(&pad.keys, "b") {
		buttons0 |= 1 << 5 // cross (bottom)
	}
	if mapping.pressed(&pad.keys, "a") {
		buttons0 |= 1 << 6 // circle (right)
	}
	if mapping.pressed(&pad.keys, "x") {
		buttons0 |= 1 << 7 // triangle (top)
	}
	report[7] = buttons0
	var buttons1 byte
	if mapping.pressed(&pad.keys, "l1") {
		buttons1 |= 1 << 0
	}
	if mapping.pressed(&pad.keys, "r1") {
		buttons1 |= 1 << 1
	}
	l2 := ds4Trigger(pad, mapping.axis("l2"), "l2")
	r2 := ds4Trigger(pad, mapping.axis("r2"), "r2")
	if l2 > 0 {
		buttons1 |= 1 << 2
	}
	if r2 > 0 {
		buttons1 |= 1 << 3
	}
	if mapping.pressed(&pad.keys, "select") {
		buttons1 |= 1 << 4 // share/create
	}
	if mapping.pressed(&pad.keys, "start") {
		buttons1 |= 1 << 5 // options
	}
	if mapping.pressed(&pad.keys, "l3") {
		buttons1 |= 1 << 6
	}
	if mapping.pressed(&pad.keys, "r3") {
		buttons1 |= 1 << 7
	}
	report[8] = buttons1
	var buttons2 byte
	if mapping.pressed(&pad.keys, "mode") {
		buttons2 |= 1 << 0 // PS
	}
	report[9] = buttons2
	report[10] = l2
	report[11] = r2
	// Sensor timestamp + temperature + gyro + accel: no motion sensors on
	// the Brick, zeros mean "no motion data".
	// Status: full battery, nothing plugged. The Brick has no fuel gauge
	// wired to this report, so report full rather than a dead battery.
	report[32] = 0x0A
	// Touch reports: none active; points marked inactive (0x80).
	report[35] = 0
	for i := 0; i < 4; i++ {
		base := 36 + i*9
		report[base+1] = 0x80
		report[base+5] = 0x80
	}
	crc := ds4CRC(ds4InputCRCSeed, report[:ds4ReportSize-4])
	binary.LittleEndian.PutUint32(report[ds4ReportSize-4:], crc)
	return report
}

// ds4FeaturePayload returns the payload AFTER the report ID for a DS4
// Bluetooth feature report the host may request during init. Sizes follow
// the descriptor (validated by TestDS4DescriptorMatchesKernelReportMap).
// Contents are neutral placeholders: no calibration rig exists on the
// Brick, and the MAC pairing slot is left zeroed. Sizes being right is
// what unblocks the host; contents get revisited if a real iPhone asks
// for more.
func ds4FeaturePayload(id byte) ([]byte, bool) {
	switch id {
	case 0x02:
		return make([]byte, 36), true
	case 0x05:
		return make([]byte, 40), true
	case 0x06:
		return make([]byte, 52), true
	case 0x09:
		return make([]byte, 19), true
	case 0x12:
		return make([]byte, 16), true
	default:
		return nil, false
	}
}

// ds4FeatureReply builds the full control-channel reply for a feature
// GET_REPORT: HIDP DATA|FEATURE header, report ID, payload, CRC32.
func ds4FeatureReply(id byte) ([]byte, bool) {
	payload, ok := ds4FeaturePayload(id)
	if !ok {
		return nil, false
	}
	packet := make([]byte, 0, 2+len(payload)+4)
	packet = append(packet, hidpData|hidpRtypeFeature, id)
	packet = append(packet, payload...)
	crc := ds4CRC(ds4FeatureCRCSeed, packet[1:len(packet)])
	var tail [4]byte
	binary.LittleEndian.PutUint32(tail[:], crc)
	packet = append(packet, tail[:]...)
	return packet, true
}
