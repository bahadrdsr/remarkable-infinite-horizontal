#!/bin/sh
set -eu
sdk="${INFINITE_HORIZONTAL_SDK:-$HOME/.local/share/remarkable-infinite-horizontal/sdk/tatsu-5.8.203}"
environment="$sdk/environment-setup-cortexa55-remarkable-linux"
if [ ! -r "$environment" ]; then
    printf '%s\n' "Missing matching tatsu SDK: $environment" >&2
    exit 1
fi
. "$environment"
cmake -S . -B build-device -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_TESTING=OFF -DINFINITE_HORIZONTAL_DEVICE_BUILD=ON \
    -DQt6_DIR="$SDKTARGETSYSROOT/usr/lib/cmake/Qt6"
cmake --build build-device --parallel 2
