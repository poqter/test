#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")" && pwd)"
sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:?Set ANDROID_HOME or ANDROID_SDK_ROOT}}"
output="${1:?Provide a release output directory}"
export ANDROID_SDK_ROOT="$sdk"
export WIDGET_KEYSTORE="${WIDGET_KEYSTORE:?Set the release keystore path}"
export WIDGET_KEY_ALIAS=hwarang-widget-release
expected=924513f70eb3c2ac5e535c12cd7af8fdc29a27f39642ebff2d9be9d777978569
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
bash "$project/build.sh" "$work"
certificates="$("$sdk/build-tools/35.0.0/apksigner" verify --print-certs "$work/hwarang-month-widget.apk")"
actual="$(awk '/certificate SHA-256 digest:/ {print $NF}' <<< "$certificates")"
if [[ "$actual" != "$expected" ]]; then
    echo "Release certificate does not match the v0.1.12 release key. No release APK was exported." >&2
    exit 1
fi
mkdir -p "$output"
install -m 644 "$work/hwarang-month-widget.apk" "$output/hwarang-month-widget.apk"
