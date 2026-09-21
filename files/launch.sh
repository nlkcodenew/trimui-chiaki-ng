#!/bin/sh
#
# TrimUI Smart Pro S launcher for trimui-chiaki-ng.
#
# Tao khung copy-the-la-chay: giong kieu RetroHub - tim python3, dat LD_LIBRARY_PATH,
# ghi log ra goc the, bao ve may khoi deep-suspend bang /tmp/stay_alive.
#
# Phien ban nay khong can download runtime vi khong dung J2ME; python3 he thong cua
# TrimUI Linux 1.1.1 da co san. Neu mot ban firmware nao do khong co, ta se fallback
# bang cach goi python tu $SDCARD_PATH/System/bin/python3 (PortMaster dat san).
case "$0" in
    */*) cd "${0%/*}" || exit 1 ;;
esac
APP="$(pwd)"

export SDCARD_PATH="${SDCARD_PATH:-/mnt/SDCARD}"
export PATH="$SDCARD_PATH/System/bin:$PATH"
export LD_LIBRARY_PATH="$APP/libs:$SDCARD_PATH/System/lib:/usr/trimui/lib:/usr/lib64:/usr/lib:/lib:$LD_LIBRARY_PATH"

# TrimUI Smart Pro S dat thu vien SDL2 o /usr/lib64 hoac /usr/lib, canh than neu
# sau nay muon them thu vien rieng (libplacebo, libav*, ...) hay dat vao $APP/libs.
export PYSDL2_DLL_PATH="$APP/libs:/usr/trimui/lib:/usr/lib64:/usr/lib"

if [ -n "$LOGS_PATH" ] && [ -d "$LOGS_PATH" ]; then
    ERRLOG="$LOGS_PATH/Chiaki.txt"
else
    ERRLOG="$SDCARD_PATH/Chiaki-loi.txt"
fi
export CHIAKI_STDERR_LOG="$ERRLOG"

log() { echo "[Chiaki] $*"; }

fatal() {
    log "$1"
    {
        echo "trimui-chiaki-ng khong khoi dong duoc"
        echo "$(date 2>/dev/null)"
        echo
        echo "$1"
        echo
        echo "$2"
    } > "$ERRLOG" 2>/dev/null
    exit 1
}

usable() {
    [ -n "$1" ] && [ -f "$1" ] || return 1
    [ -x "$1" ] || chmod +x "$1" 2>/dev/null
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null
}

find_python() {
    for c in \
        "$(command -v python3 2>/dev/null)" \
        "$APP/python/bin/python3" \
        "$SDCARD_PATH/System/bin/python3" \
        "$SDCARD_PATH/Apps/PortMaster/PortMaster/exlibs/python3" \
        /usr/bin/python3 \
        /usr/local/bin/python3
    do
        if usable "$c"; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

PY="$(find_python)"
[ -n "$PY" ] || fatal "Khong tim thay python3 tren may." \
"Hay cap nhat firmware TrimUI len phien ban 1.0.4 tro len (co san python3 trong rootfs) hoac copy python3 vao $SDCARD_PATH/System/bin/python3."

# Neu crash truoc chua gui duoc, giu log cu cho uploader retry o lan khoi dong
# tiep theo. Khi khong co crash pending, log launcher cu co the xoa an toan.
if [ ! -f "$APP/.pending_crash" ]; then
    rm -f "$ERRLOG" 2>/dev/null
fi

# TrimUI Smart Pro S hay bi Kernel Panic khi deep suspend giet app dang chay.
touch /tmp/stay_alive 2>/dev/null

while true; do
    rm -f /tmp/launch_game.sh
    "$PY" app.py 2>> "$ERRLOG"
    APP_EXIT_CODE=$?
    if [ $APP_EXIT_CODE -ne 0 ]; then
        touch "$APP/.pending_crash" 2>/dev/null
        "$PY" -m rh.log_uploader --reason "exit_$APP_EXIT_CODE" >> "$ERRLOG" 2>&1 || true
    fi
    if [ -f /tmp/launch_game.sh ]; then
        sh /tmp/launch_game.sh
        rm -f /tmp/launch_game.sh
        touch /tmp/stay_alive 2>/dev/null
    else
        break
    fi
done

rm -f /tmp/stay_alive 2>/dev/null
