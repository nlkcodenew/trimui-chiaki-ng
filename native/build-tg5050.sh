#!/bin/sh
set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SDK_ROOT="${SDK_ROOT:-$REPO_ROOT/../sdk-tg5050/sdk_tg5050_linux_v1.0.0}"
CHIAKI_SOURCE="${CHIAKI_SOURCE:-/tmp/trimui-chiaki-ng-upstream}"
CHIAKI_COMMIT="a9a2805884cfa83865fdfcc09ca3ddfcd628aa42"
BUILD_DIR="${BUILD_DIR:-/tmp/chiaki-build}"
TOOLCHAIN_FILE="${TOOLCHAIN_FILE:-$REPO_ROOT/native/tg5050-toolchain.cmake}"
MINIUPNPC_SOURCE="${MINIUPNPC_SOURCE:-$REPO_ROOT/../miniupnp-src}"
PROTOC="${PROTOC:-$REPO_ROOT/native/protoc-wrapper.py}"
PROJECT_NATIVE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

test -x "$SDK_ROOT/host/bin/aarch64-none-linux-gnu-gcc" || {
  echo "Không tìm thấy SDK TG5050 tại: $SDK_ROOT" >&2
  exit 1
}
if test ! -d "$CHIAKI_SOURCE/.git"; then
  git clone https://github.com/streetpea/chiaki-ng.git "$CHIAKI_SOURCE"
fi
if test "$(git -C "$CHIAKI_SOURCE" rev-parse HEAD 2>/dev/null || true)" != "$CHIAKI_COMMIT"; then
  git -C "$CHIAKI_SOURCE" fetch origin "$CHIAKI_COMMIT" --depth 1
  git -C "$CHIAKI_SOURCE" checkout --detach "$CHIAKI_COMMIT"
fi
if test ! -d "$MINIUPNPC_SOURCE/.git"; then
  git clone --depth 1 --branch miniupnpc_2_2_8 https://github.com/miniupnp/miniupnp.git "$MINIUPNPC_SOURCE"
fi
git -C "$CHIAKI_SOURCE" submodule update --init --depth 1 \
  third-party/curl third-party/nanopb third-party/gf-complete third-party/jerasure
if ! grep -q 'TRIMUI_NATIVE_SOURCE' "$CHIAKI_SOURCE/CMakeLists.txt"; then
  cat >> "$CHIAKI_SOURCE/CMakeLists.txt" <<'EOF'

if(DEFINED TRIMUI_NATIVE_SOURCE)
  add_subdirectory("${TRIMUI_NATIVE_SOURCE}" "${CMAKE_BINARY_DIR}/trimui-native")
endif()
EOF
fi

ln -sfn "$SDK_ROOT" /tmp/tg5050-sdk
ln -sfn "$CHIAKI_SOURCE" /tmp/chiaki-src
PATH="/tmp:/tmp/tg5050-sdk/host/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

cmake -S /tmp/chiaki-src -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN_FILE" \
  -DPROTOC="$PROTOC" -DPYTHON_EXECUTABLE=/usr/bin/python3 -DPython_EXECUTABLE=/usr/bin/python3 \
  -DFETCHCONTENT_SOURCE_DIR_MINIUPNPC="$MINIUPNPC_SOURCE" \
  -DTRIMUI_NATIVE_SOURCE="$PROJECT_NATIVE" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
  -DCHIAKI_ENABLE_GUI=OFF -DCHIAKI_ENABLE_CLI=OFF -DCHIAKI_ENABLE_TESTS=OFF \
  -DCHIAKI_ENABLE_ANDROID=OFF -DCHIAKI_ENABLE_BOREALIS=OFF \
  -DCHIAKI_ENABLE_SETSU=OFF -DCHIAKI_ENABLE_STEAMDECK_NATIVE=OFF \
  -DCHIAKI_ENABLE_STEAM_SHORTCUT=OFF -DCHIAKI_ENABLE_SPEEX=OFF \
  -DCHIAKI_ENABLE_RUDP=OFF -DCHIAKI_ENABLE_FFMPEG_DECODER=ON \
  -DCHIAKI_ENABLE_PI_DECODER=OFF -DCHIAKI_LIB_ENABLE_OPUS=ON \
  -DCHIAKI_USE_SYSTEM_JERASURE=OFF -DCHIAKI_USE_SYSTEM_NANOPB=OFF \
  -DCHIAKI_USE_SYSTEM_CURL=OFF -DCHIAKI_LIB_MINIUPNPC_EXTERNAL_PROJECT=ON
cmake --build "$BUILD_DIR" --target chiaki-stream chiaki-regist -j "${JOBS:-8}"
"/tmp/tg5050-sdk/host/bin/aarch64-none-linux-gnu-strip" --strip-unneeded \
  "$BUILD_DIR/trimui-native/chiaki-stream" \
  "$BUILD_DIR/trimui-native/chiaki-regist"
cp "$BUILD_DIR/trimui-native/chiaki-stream" "$REPO_ROOT/files/bin/chiaki-stream"
cp "$BUILD_DIR/trimui-native/chiaki-regist" "$REPO_ROOT/files/bin/chiaki-regist"
chmod +x "$REPO_ROOT/files/bin/chiaki-stream"
chmod +x "$REPO_ROOT/files/bin/chiaki-regist"
