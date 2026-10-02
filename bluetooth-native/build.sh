#!/bin/sh
set -eu

ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT/bluetooth-native"

GOTOOLCHAIN="${GOTOOLCHAIN:-auto}" go test ./...
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 GOARM64=v8.0 \
GOTOOLCHAIN="${GOTOOLCHAIN:-auto}" \
    go build -buildvcs=false -trimpath -ldflags='-s -w' \
    -o "$ROOT/files/bin/brick-pro-bt" .
chmod +x "$ROOT/files/bin/brick-pro-bt"
