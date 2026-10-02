package main

import (
	"encoding/xml"
	"strings"
	"testing"
)

// BlueZ parses the ServiceRecord string with sdp_xml_parse(). A record that
// does not parse is rejected with "Unable to parse record for <name>" and the
// profile never reaches SDP, so the phone cannot discover the gamepad.
func TestServiceRecordIsWellFormedXML(t *testing.T) {
	record := serviceRecord()
	decoder := xml.NewDecoder(strings.NewReader(record))
	for {
		_, err := decoder.Token()
		if err != nil {
			if err.Error() == "EOF" {
				break
			}
			t.Fatalf("ServiceRecord is not well-formed XML: %v", err)
		}
	}
	for _, required := range []string{
		`id="0x0001"`, `id="0x0004"`, `id="0x000d"`,
		`id="0x0100"`, `id="0x0206"`,
	} {
		if !strings.Contains(record, required) {
			t.Fatalf("ServiceRecord is missing %s", required)
		}
	}
	if !strings.Contains(record, "TrimUI Brick Pro Gamepad") {
		t.Fatal("ServiceRecord lost its advertised name")
	}
}

// A map that assigns one Linux key to two HID buttons would make the phone see
// several buttons at once, which is exactly what a mis-recorded calibration
// produced. Reject it instead of sending a broken report.
func TestMappingRejectsDuplicateButtonCodes(t *testing.T) {
	mapping := defaultMapping()
	duplicates := mapping.duplicateButtons()
	if len(duplicates) != 0 {
		t.Fatalf("built-in mapping already has duplicates: %v", duplicates)
	}
	mapping.Buttons["l3"] = mapping.Buttons["r3"]
	duplicates = mapping.duplicateButtons()
	if len(duplicates) != 1 {
		t.Fatalf("duplicate not detected: %v", duplicates)
	}
}
