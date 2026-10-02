#!/bin/sh
set -u

case "$0" in
    */*) cd "${0%/*}" || exit 1 ;;
esac
APP="$(pwd)"
BACKEND="$APP/bin/brick-pro-bt"
RUN_DIR="${1:-/tmp/chiaki-brick-pro-bt.$$}"
STATUS_FILE="$RUN_DIR/status"
HEARTBEAT_FILE="$RUN_DIR/heartbeat"
CANCEL_FILE="$RUN_DIR/cancel"
GUARD_FILE="$RUN_DIR/guard"
RECOVERY_FILE="$RUN_DIR/restore-bluez"
RESULT_FILE="$RUN_DIR/result"
LOG_FILE="$APP/BrickBluetooth.log"
WORKER_PID=""
GUARD_PID=""
APP_PARENT_PID="${CHIAKI_PARENT_PID:-0}"

umask 077
mkdir -p "$RUN_DIR" || exit 1

# BrickBluetooth.log nam tren the nho nen phai xoay vong. Phien moi ghi them vai
# KB; giu mot ban .1 de doc chieu cuoi ma khong lam day the.
rotate_log() {
    [ -f "$LOG_FILE" ] || return 0
    size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
    [ "${size:-0}" -gt 524288 ] || return 0
    mv -f "$LOG_FILE" "$LOG_FILE.1" 2>/dev/null || rm -f "$LOG_FILE" 2>/dev/null
    : > "$LOG_FILE" 2>/dev/null || true
}

alive() {
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

app_parent_alive() {
    case "$APP_PARENT_PID" in
        ''|0|*[!0-9]*) return 0 ;;
    esac
    kill -0 "$APP_PARENT_PID" 2>/dev/null
}

stop_child() {
    child_pid="$1"
    [ -n "$child_pid" ] || return 0
    kill -TERM "$child_pid" 2>/dev/null || true
    count=0
    while alive "$child_pid" && [ "$count" -lt 40 ]; do
        sleep 0.1
        count=$((count + 1))
    done
    if alive "$child_pid"; then
        kill -KILL "$child_pid" 2>/dev/null || true
    fi
    wait "$child_pid" 2>/dev/null || true
}

cleanup() {
    trap - 0 INT TERM HUP
    stop_child "$WORKER_PID"
    stop_child "$GUARD_PID"
    if [ -f "$RECOVERY_FILE" ]; then
        "$BACKEND" --recover --recovery-file "$RECOVERY_FILE" >> "$LOG_FILE" 2>&1 || true
    fi
}

trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP

chmod +x "$BACKEND" 2>/dev/null || true
if [ ! -x "$BACKEND" ]; then
    echo "backend_missing" > "$STATUS_FILE"
    echo "backend_missing" > "$RESULT_FILE"
    exit 1
fi

rotate_log

{
    echo ""
    echo "=== Brick Pro Bluetooth session ==="
    date 2>/dev/null || true
    uname -a 2>/dev/null || true
    "$BACKEND" --version 2>&1 || true
    echo "=== Bluetooth tools ==="
    for tool in bluetoothd bluetoothctl btmgmt hciconfig rfkill dbus-send; do
        command -v "$tool" 2>/dev/null || true
    done
    echo "=== Bluetooth paths ==="
    ls -l /run/dbus/system_bus_socket /var/run/dbus/system_bus_socket 2>/dev/null || true
    ls -l /sys/class/bluetooth/hci* 2>/dev/null || true
    ls -l /etc/init.d/*bluetooth* /etc/init.d/*bluez* /etc/bluetooth/*init*.sh 2>/dev/null || true
    echo "=== Bluetooth processes ==="
    ps 2>/dev/null | grep -E 'bluetoothd|hciattach|bluealsa' | grep -v grep || true
    echo "=== Input devices ==="
    if [ -r /proc/bus/input/devices ]; then
        sed -n '1,220p' /proc/bus/input/devices
    fi
} >> "$LOG_FILE" 2>&1

if [ -f "$RECOVERY_FILE" ]; then
    "$BACKEND" --recover --recovery-file "$RECOVERY_FILE" >> "$LOG_FILE" 2>&1 || {
        echo "recovery_failed" > "$STATUS_FILE"
        echo "recovery_failed" > "$RESULT_FILE"
        exit 1
    }
fi

"$BACKEND" --guard --guard-state "$GUARD_FILE" --cancel-file "$CANCEL_FILE" --parent-pid $$ >> "$LOG_FILE" 2>&1 &
GUARD_PID=$!

count=0
while [ "$count" -lt 50 ]; do
    app_parent_alive || {
        echo "app_parent_lost" > "$STATUS_FILE"
        echo "app_parent_lost" > "$RESULT_FILE"
        exit 1
    }
    case "$(cat "$GUARD_FILE" 2>/dev/null || true)" in
        ready*) break ;;
        error*) echo "input_guard_error" > "$STATUS_FILE"; echo "input_guard_error" > "$RESULT_FILE"; exit 1 ;;
    esac
    alive "$GUARD_PID" || {
        echo "input_guard_error" > "$STATUS_FILE"
        echo "input_guard_error" > "$RESULT_FILE"
        exit 1
    }
    sleep 0.1
    count=$((count + 1))
done
case "$(cat "$GUARD_FILE" 2>/dev/null || true)" in
    ready*) ;;
    *) echo "input_guard_timeout" > "$STATUS_FILE"; echo "input_guard_timeout" > "$RESULT_FILE"; exit 1 ;;
esac

"$BACKEND" --run --status-file "$STATUS_FILE" --heartbeat-file "$HEARTBEAT_FILE" --recovery-file "$RECOVERY_FILE" --parent-pid $$ >> "$LOG_FILE" 2>&1 &
WORKER_PID=$!

while alive "$WORKER_PID"; do
    if ! app_parent_alive; then
        echo "app_parent_lost" > "$STATUS_FILE"
        stop_child "$WORKER_PID"
        WORKER_PID=""
        echo "app_parent_lost" > "$RESULT_FILE"
        exit 1
    fi
    if [ -f "$CANCEL_FILE" ]; then
        echo "stopping" > "$STATUS_FILE"
        stop_child "$WORKER_PID"
        WORKER_PID=""
        echo "stopped" > "$RESULT_FILE"
        exit 0
    fi
    alive "$GUARD_PID" || {
        echo "input_guard_lost" > "$STATUS_FILE"
        stop_child "$WORKER_PID"
        WORKER_PID=""
        echo "input_guard_lost" > "$RESULT_FILE"
        exit 1
    }
    sleep 0.1
done

wait "$WORKER_PID"
result=$?
WORKER_PID=""
if [ "$result" -eq 0 ]; then
    echo "stopped" > "$RESULT_FILE"
else
    echo "backend_error_$result" > "$RESULT_FILE"
fi
exit "$result"
