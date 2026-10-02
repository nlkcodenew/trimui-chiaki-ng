package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// The Stock OS exposes the Brick Pro pad as one evdev node whose Linux key
// codes do not have to follow BTN_GAMEPAD. Every variant so far reports the
// face buttons and shoulders at 304..315, but the stick clicks and the small
// buttons below the case move around, so the whole table can be replaced by
// bluetooth-map.json, written by the in-app button test screen.
type padMapping struct {
	Buttons map[string]uint16 `json:"buttons"`
	Axes    map[string]uint16 `json:"axes"`
	Source  string            `json:"-"`
}

// HID report descriptor usages 1..16, so the report bit is usage-1. L2/R2 are
// analog triggers: their bit only says "pulled", the value lives in the report
// tail.
var hidButtons = []struct {
	name string
	bit  uint
}{
	{"a", 0}, {"b", 1}, {"x", 3}, {"y", 4},
	{"l1", 6}, {"r1", 7}, {"l2", 8}, {"r2", 9},
	{"select", 10}, {"start", 11}, {"l3", 13}, {"r3", 14},
}

var analogTriggers = map[string]bool{"l2": true, "r2": true}

// BTN_DPAD_* aliases are always honoured next to the mapped arrow keys, so a
// driver that reports either form works without a map file.
var dpadAliases = map[string][]uint16{
	"dpad_left":  {105, 546},
	"dpad_right": {106, 547},
	"dpad_up":    {103, 544},
	"dpad_down":  {108, 545},
}

func defaultMapping() *padMapping {
	return &padMapping{
		Buttons: map[string]uint16{
			"a": 304, "b": 305, "x": 307, "y": 308,
			"l1": 310, "r1": 311, "l2": 312, "r2": 313,
			"select": 314, "start": 315, "mode": 316,
			"l3": 317, "r3": 318,
			"dpad_up": 103, "dpad_down": 108,
			"dpad_left": 105, "dpad_right": 106,
		},
		Axes: map[string]uint16{
			"left_x": 0, "left_y": 1, "l2": 2,
			"right_x": 3, "right_y": 4, "r2": 5,
			"hat_x": 16, "hat_y": 17,
		},
	}
}

// builtinMapping backs pad states built without an explicit table, so the
// package keeps working in tests and before the session loads a map.
var builtinMapping = defaultMapping()

func (m *padMapping) code(name string) uint16 {
	if m == nil {
		return builtinMapping.Buttons[name]
	}
	if value, ok := m.Buttons[name]; ok && value > 0 {
		return value
	}
	return builtinMapping.Buttons[name]
}

func (m *padMapping) axis(name string) uint16 {
	if m == nil {
		return builtinMapping.Axes[name]
	}
	if value, ok := m.Axes[name]; ok && value < 64 {
		return value
	}
	return builtinMapping.Axes[name]
}

// pressed reports the current state of a mapped key. Both callers must be
// inside padState, which owns the [768]bool key bitmap.
func (m *padMapping) pressed(keys *[768]bool, name string) bool {
	code := m.code(name)
	return code > 0 && code < 768 && keys[code]
}

// duplicateButtons lists HID buttons that share one Linux key code. A map like
// that makes the phone see several buttons at once, so it is reported loudly
// instead of being used quietly.
func (m *padMapping) duplicateButtons() [][2]string {
	seen := map[uint16]string{}
	dupes := [][2]string{}
	for _, button := range hidButtons {
		code := m.code(button.name)
		if other, taken := seen[code]; taken {
			dupes = append(dupes, [2]string{other, button.name})
			continue
		}
		seen[code] = button.name
	}
	sort.Slice(dupes, func(i, j int) bool { return dupes[i][0] < dupes[j][0] })
	return dupes
}

func (m *padMapping) usedKeys() map[uint16]bool {
	used := map[uint16]bool{}
	for _, code := range m.Buttons {
		if code > 0 && code < 768 {
			used[code] = true
		}
	}
	for _, codes := range dpadAliases {
		for _, code := range codes {
			used[code] = true
		}
	}
	return used
}

func (m *padMapping) describe() string {
	names := make([]string, 0, len(m.Buttons))
	for name := range m.Buttons {
		names = append(names, name)
	}
	sort.Strings(names)
	text := ""
	for i, name := range names {
		if i > 0 {
			text += " "
		}
		text += fmt.Sprintf("%s=%d", name, m.Buttons[name])
	}
	return text
}

// defaultMapPath puts the map next to the app root, because the backend lives
// in <app>/bin and the launcher never passes an absolute path.
func defaultMapPath() string {
	executable, err := os.Executable()
	if err != nil {
		return ""
	}
	return filepath.Clean(filepath.Join(filepath.Dir(executable), "..", "bluetooth-map.json"))
}

func loadMapping(path string) *padMapping {
	mapping := defaultMapping()
	mapping.Source = "built-in defaults"
	if path == "" {
		return mapping
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if !os.IsNotExist(err) {
			fmt.Println("Button map: cannot read", path, "-", err)
		}
		return mapping
	}
	var file struct {
		Version int            `json:"version"`
		Buttons map[string]int `json:"buttons"`
		Axes    map[string]int `json:"axes"`
	}
	if err = json.Unmarshal(data, &file); err != nil {
		fmt.Println("Button map: ignoring malformed", path, "-", err)
		return mapping
	}
	applied, rejected := 0, 0
	for name, code := range file.Buttons {
		if code <= 0 || code >= 768 {
			rejected++
			continue
		}
		if _, known := builtinMapping.Buttons[name]; !known {
			rejected++
			continue
		}
		mapping.Buttons[name] = uint16(code)
		applied++
	}
	for name, code := range file.Axes {
		if code < 0 || code >= 64 {
			rejected++
			continue
		}
		if _, known := builtinMapping.Axes[name]; !known {
			rejected++
			continue
		}
		mapping.Axes[name] = uint16(code)
		applied++
	}
	mapping.Source = path
	fmt.Printf("Button map: %s (version %d, %d override(s), %d rejected)\n",
		path, file.Version, applied, rejected)
	if duplicates := mapping.duplicateButtons(); len(duplicates) > 0 {
		// Two HID buttons sharing one key code is exactly what makes several
		// buttons light up on the phone at once. Name them loudly instead of
		// sending a report that cannot be right.
		names := make([]string, 0, len(duplicates))
		for _, pair := range duplicates {
			names = append(names, fmt.Sprintf("%s=%s", pair[0], pair[1]))
		}
		fmt.Printf("WARNING: several buttons share one key code: %s\n", strings.Join(names, ", "))
		fmt.Println("Re-run THU BUT and press only the button that is asked for.")
	}
	return mapping
}
