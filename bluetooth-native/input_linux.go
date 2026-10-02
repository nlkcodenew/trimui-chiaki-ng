package main

import (
	"encoding/binary"
	"errors"
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"unsafe"

	"golang.org/x/sys/unix"
)

type inputEvent struct {
	kind, code uint16
	value      int32
}

type absInfo struct {
	value, min, max int32
}

type inputDevice struct {
	fd         int
	path, name string
	absBits    []byte
	ranges     map[uint16]absInfo
	dropped    bool
}

func evRead(fd int, nr uint, data []byte) error {
	if len(data) == 0 {
		return errors.New("empty ioctl buffer")
	}
	_, _, syscallErr := unix.Syscall(unix.SYS_IOCTL, uintptr(fd), uintptr(0x80000000|uint(len(data))<<16|0x45<<8|nr), uintptr(unsafe.Pointer(&data[0])))
	if syscallErr != 0 {
		return syscallErr
	}
	return nil
}

func hasBit(data []byte, bit int) bool {
	return bit/8 < len(data) && data[bit/8]&(1<<uint(bit%8)) != 0
}

func absQuery(fd int, code uint16) (absInfo, error) {
	data := make([]byte, 24)
	if err := evRead(fd, 0x40+uint(code), data); err != nil {
		return absInfo{}, err
	}
	return absInfo{value: int32(binary.LittleEndian.Uint32(data)), min: int32(binary.LittleEndian.Uint32(data[4:])), max: int32(binary.LittleEndian.Uint32(data[8:]))}, nil
}

func openInput(path string) (*inputDevice, error) {
	fd, err := unix.Open(path, unix.O_RDONLY|unix.O_NONBLOCK|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, err
	}
	device := &inputDevice{fd: fd, path: path, absBits: make([]byte, 8), ranges: map[uint16]absInfo{}}
	name := make([]byte, 256)
	if err = evRead(fd, 0x06, name); err != nil {
		device.close()
		return nil, err
	}
	device.name = strings.TrimRight(string(name), "\x00")
	keys := make([]byte, 96)
	if err = evRead(fd, 0x21, keys); err != nil {
		device.close()
		return nil, err
	}
	if !hasBit(keys, 304) || !hasBit(keys, 305) {
		device.close()
		return nil, errors.New("not a gamepad")
	}
	if err = evRead(fd, 0x23, device.absBits); err != nil {
		device.close()
		return nil, err
	}
	if !hasBit(device.absBits, 16) && !hasBit(keys, 103) && !hasBit(keys, 544) {
		device.close()
		return nil, errors.New("no D-pad")
	}
	for _, code := range []uint16{0, 1, 2, 3, 4, 5, 16, 17} {
		if !hasBit(device.absBits, int(code)) {
			continue
		}
		info, queryErr := absQuery(fd, code)
		if queryErr != nil {
			device.close()
			return nil, queryErr
		}
		device.ranges[code] = info
	}
	return device, nil
}

func inputScore(device *inputDevice) int {
	score := 0
	name := strings.ToLower(device.name)
	if strings.Contains(name, "trimui") {
		score += 100
	}
	if strings.Contains(name, "player1") || strings.Contains(name, "gamepad") {
		score += 30
	}
	for _, code := range []uint16{0, 1, 3, 4} {
		if _, ok := device.ranges[code]; ok {
			score += 10
		}
	}
	if _, ok := device.ranges[16]; ok {
		score += 2
	}
	if _, ok := device.ranges[17]; ok {
		score += 2
	}
	return score
}

func chooseInput() (*inputDevice, error) {
	paths, _ := filepath.Glob("/dev/input/event*")
	var devices []*inputDevice
	for _, path := range paths {
		if device, err := openInput(path); err == nil {
			devices = append(devices, device)
		}
	}
	if len(devices) == 0 {
		return nil, errors.New("no Linux gamepad input device found")
	}
	sort.SliceStable(devices, func(i, j int) bool { return inputScore(devices[i]) > inputScore(devices[j]) })
	selected := devices[0]
	if len(devices) > 1 && inputScore(selected) == inputScore(devices[1]) && inputScore(selected) < 100 {
		for _, device := range devices {
			device.close()
		}
		return nil, fmt.Errorf("ambiguous gamepad input: found %d candidates", len(devices))
	}
	for _, device := range devices[1:] {
		device.close()
	}
	return selected, nil
}

func (device *inputDevice) close() {
	if device.fd >= 0 {
		unix.Close(device.fd)
		device.fd = -1
	}
}

func (device *inputDevice) snapshot(pad *padState) error {
	keys, err := device.keySnapshot()
	if err != nil {
		return err
	}
	pad.keys = [768]bool{}
	pad.axes = [64]int32{}
	pad.ranges = device.ranges
	pad.keys = keys
	for code := range device.ranges {
		info, queryErr := absQuery(device.fd, code)
		if queryErr != nil {
			return queryErr
		}
		pad.axes[code] = info.value
	}
	return nil
}

func (device *inputDevice) keySnapshot() ([768]bool, error) {
	var result [768]bool
	bits := make([]byte, 96)
	if err := evRead(device.fd, 0x18, bits); err != nil {
		return result, err
	}
	for key := range result {
		result[key] = hasBit(bits, key)
	}
	return result, nil
}

func parseEvents(data []byte) ([]inputEvent, error) {
	if len(data)%24 != 0 {
		return nil, errors.New("input_event must be 24 bytes on ARM64")
	}
	events := make([]inputEvent, 0, len(data)/24)
	for len(data) > 0 {
		events = append(events, inputEvent{kind: binary.LittleEndian.Uint16(data[16:18]), code: binary.LittleEndian.Uint16(data[18:20]), value: int32(binary.LittleEndian.Uint32(data[20:24]))})
		data = data[24:]
	}
	return events, nil
}

func (device *inputDevice) read(pad *padState, emit func([]byte)) error {
	buffer := make([]byte, 24*64)
	for batch := 0; batch < 8; batch++ {
		readCount, err := unix.Read(device.fd, buffer)
		if err == unix.EAGAIN {
			return nil
		}
		if err == unix.EINTR {
			continue
		}
		if err != nil {
			return err
		}
		if readCount == 0 {
			return errors.New("input device disconnected")
		}
		events, parseErr := parseEvents(buffer[:readCount])
		if parseErr != nil {
			return parseErr
		}
		for _, event := range events {
			if event.kind == 0 && event.code == 3 {
				device.dropped = true
				pad.keys = [768]bool{}
				pad.axes = [64]int32{}
				emit(pad.report())
				continue
			}
			if device.dropped {
				if event.kind == 0 && event.code == 0 {
					if err = device.snapshot(pad); err != nil {
						return err
					}
					device.dropped = false
					emit(pad.report())
				}
				continue
			}
			if event.kind == 0 && event.code == 0 {
				emit(pad.report())
			} else {
				pad.apply(event)
			}
		}
	}
	return nil
}
