package main

import (
	"encoding/binary"
	"testing"
)

// The DS4 Bluetooth descriptor below is validated against the Linux kernel,
// not copied from any controller app: parse it and require the report map
// to equal the hid-playstation.c static_assert sizes (input 0x01/9 +
// 0x11/77, output 0x11/77, features 0x02/36 0xA3/48 0x05/40 0x06/52 ...).
func ds4ReportMap(t *testing.T, desc []byte) map[[3]int]int {
	t.Helper()
	out := map[[3]int]int{}
	rid, size, count := 0, 0, 0
	for i := 0; i < len(desc); {
		b := desc[i]
		i++
		if b == 0xFE {
			i += 1 + int(desc[i])
			continue
		}
		tag, typ, n := (b>>4)&15, (b>>2)&3, []int{0, 1, 2, 4}[b&3]
		val := 0
		for k := 0; k < n; k++ {
			val |= int(desc[i+k]) << (8 * k)
		}
		i += n
		switch {
		case typ == 1 && tag == 8:
			rid = val
		case typ == 1 && tag == 7:
			size = val
		case typ == 1 && tag == 9:
			count = val
		case typ == 0 && (tag == 8 || tag == 9 || tag == 11):
			out[[3]int{int(tag), rid}] += size * count
		}
	}
	return out
}

func TestDS4DescriptorMatchesKernelReportMap(t *testing.T) {
	got := ds4ReportMap(t, ds4Descriptor)
	if len(ds4Descriptor) != 442 {
		t.Fatalf("descriptor is %d bytes, want 442", len(ds4Descriptor))
	}
	// kind tag: 8=input, 9=output, 11=feature. Values are payload BYTES
	// (report ID excluded), matching the kernel's report SIZE constants
	// minus one (input 0x11/78, feature 0x05/41, ...).
	want := map[[3]int]int{
		{8, 0x01}:  9,
		{8, 0x11}:  77,
		{9, 0x11}:  77,
		{11, 0x02}: 36,
		{11, 0xA3}: 48,
		{11, 0x05}: 40,
		{11, 0x06}: 52,
		{11, 0x07}: 48,
		{11, 0x08}: 47,
		{11, 0x09}: 19,
		{11, 0x03}: 38,
		{11, 0x04}: 46,
		{11, 0xF0}: 63,
		{11, 0xF1}: 63,
		{11, 0xF2}: 15,
	}
	for key, size := range want {
		if got[key] != size*8 {
			t.Errorf("report %d/0x%02X is %d bits, want %d bytes",
				key[0], key[1], got[key], size)
		}
	}
}

// expectedDS4 builds the 78-byte report by hand for one logical state, so
// the test pins the wire layout instead of re-running the builder.
func expectedDS4(buttons0 byte) []byte {
	rep := []byte{0x11, 0xC0, 0x00, 128, 128, 128, 128, buttons0, 0x00, 0x00,
		0, 0, 0, 0, 0,
		0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
		0, 0, 0, 0, 0,
		0x0A, 0x00,
		0, 0}
	for i := 0; i < 4; i++ {
		rep = append(rep, 0, 0x80, 0, 0, 0, 0x80, 0, 0, 0)
	}
	rep = append(rep, 0, 0)
	if len(rep) != ds4ReportSize-4 {
		panic("test vector has wrong length")
	}
	return rep
}

func TestDS4ReportBytesAndCRC(t *testing.T) {
	old := hidProfile
	hidProfile = "ds4"
	defer func() { hidProfile = old }()
	// CRC oracles computed independently with Python binascii.crc32
	// (IEEE, same polynomial the kernel documents) over 0xA1 + payload.
	for _, tc := range []struct {
		name    string
		keys    []uint16
		buttons byte
		crc     uint32
	}{
		{"neutral", nil, 0x08, 0x7f08d39e},
		{"B-cross", []uint16{304}, 0x28, 0xd63f0445},
	} {
		pad := proPad()
		for _, code := range tc.keys {
			pad.keys[code] = true
		}
		got := pad.report()
		want := append(expectedDS4(tc.buttons), 0, 0, 0, 0)
		binary.LittleEndian.PutUint32(want[ds4ReportSize-4:], tc.crc)
		if len(got) != ds4ReportSize {
			t.Fatalf("%s: report is %d bytes, want %d", tc.name, len(got), ds4ReportSize)
		}
		for i := range want {
			if got[i] != want[i] {
				t.Fatalf("%s: byte %d is %02x, want %02x (full %x)",
					tc.name, i, got[i], want[i], got)
			}
		}
	}
}

func TestDS4ButtonsAndHat(t *testing.T) {
	old := hidProfile
	hidProfile = "ds4"
	defer func() { hidProfile = old }()
	pad := proPad()
	pad.keys[305] = true // A (right) -> circle
	pad.keys[307] = true // Y (left) -> square
	pad.keys[310] = true // L1
	pad.keys[314] = true // select -> share/create
	pad.keys[316] = true // MENU -> PS
	pad.axes[2] = 255    // L2 pulled
	report := pad.report()
	if report[7] != 0x58 {
		t.Fatalf("buttons0 = %02x, want 0x58 (square+circle, hat center)", report[7])
	}
	// L1 b0, L2-digital b2, share b4.
	if report[8] != 0x15 {
		t.Fatalf("buttons1 = %02x, want 0x15", report[8])
	}
	if report[9] != 0x01 {
		t.Fatalf("buttons2 = %02x, want 0x01 (PS)", report[9])
	}
	if report[10] != 255 {
		t.Fatalf("L2 analog = %d, want 255", report[10])
	}
	// D-pad right via hat axis -> hat nibble 2, buttons0 low nibble 2.
	pad2 := proPad()
	pad2.axes[16] = 1
	report2 := pad2.report()
	if report2[7]&0x0F != 2 {
		t.Fatalf("hat = %x, want 2 (right)", report2[7]&0x0F)
	}
}

func TestDS4FeatureReplies(t *testing.T) {
	for id, payloadSize := range map[byte]int{
		0x02: 36, 0x05: 40, 0x06: 52, 0x09: 19, 0x12: 16,
	} {
		reply, ok := ds4FeatureReply(id)
		if !ok {
			t.Fatalf("feature 0x%02X not answered", id)
		}
		// Header + ID + payload + CRC.
		if len(reply) != 2+payloadSize+4 {
			t.Fatalf("feature 0x%02X reply is %d bytes, want %d",
				id, len(reply), 2+payloadSize+4)
		}
		if reply[0] != hidpData|hidpRtypeFeature || reply[1] != id {
			t.Fatalf("feature 0x%02X header = %x %x", id, reply[0], reply[1])
		}
		crc := binary.LittleEndian.Uint32(reply[len(reply)-4:])
		if want := ds4CRC(ds4FeatureCRCSeed, reply[1:len(reply)-4]); crc != want {
			t.Fatalf("feature 0x%02X CRC mismatch", id)
		}
	}
	if _, ok := ds4FeatureReply(0x77); ok {
		t.Fatal("unknown feature 0x77 answered")
	}
}
