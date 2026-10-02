# Build Brick Pro Bluetooth backend

The backend is a static Linux AArch64 executable. It reads the Brick Pro
evdev gamepad, including both analog sticks, and exposes a Bluetooth Classic
HID gamepad through BlueZ and the system D-Bus.

Build on Linux or WSL with Go 1.23 or newer:

```sh
go mod download
go test ./...
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 GOARM64=v8.0 \
  go build -buildvcs=false -trimpath -ldflags='-s -w' \
  -o ../files/bin/brick-pro-bt .
```

The output must be ELF64 little-endian AArch64, statically linked, and have no
`PT_INTERP` entry. `tools/verify_release.py` checks the architecture before a
release is accepted.

The Stock OS radio layer detects common Buildroot init scripts instead of
requiring NextUI paths. When HID PSM 17/19 are occupied, it stores a recovery
marker, stops the detected service, runs an owned `bluetoothd --noplugin=input`
process, and restores the original service on every normal or signalled exit.

The Brick Pro mapping is confirmed against the Stock OS PortMaster SDL entry:
left stick `ABS_X/ABS_Y` (axes 0/1), analog L2 axis 2, right stick axes 3/4,
analog R2 axis 5 and D-pad hat axes 16/17. Axis ranges are queried at runtime
with `EVIOCGABS`; no fixed calibration range is assumed.
