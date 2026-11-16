#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")" && pwd)"
sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:?Set ANDROID_HOME or ANDROID_SDK_ROOT}}"
android_jar="$sdk/platforms/android-35/android.jar"
tools="$sdk/build-tools/35.0.0"
output="${1:-$project/build}"
mkdir -p "$output"
output="$(cd "$output" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/generated" "$work/classes" "$work/dex"
"$tools/aapt2" compile --dir "$project/res" -o "$work/resources.zip"
"$tools/aapt2" link -I "$android_jar" --manifest "$project/AndroidManifest.xml" --java "$work/generated" \
  -o "$work/resources.apk" "$work/resources.zip"
find "$project/src" "$work/generated" -name '*.java' -print > "$work/sources"
javac -encoding UTF-8 --release 8 -classpath "$android_jar" -d "$work/classes" @"$work/sources"
jar cf "$work/widget.jar" -C "$work/classes" .
"$tools/d8" --min-api 26 --lib "$android_jar" --output "$work/dex" "$work/widget.jar"
(cd "$work/dex" && zip -q "$work/resources.apk" classes.dex)
"$tools/zipalign" -P 16 -f 4 "$work/resources.apk" "$output/hwarang-month-widget-unsigned.apk"
if [[ -n "${WIDGET_KEYSTORE:-}" ]]; then
  "$tools/apksigner" sign --ks "$WIDGET_KEYSTORE" --ks-key-alias "${WIDGET_KEY_ALIAS:?Set WIDGET_KEY_ALIAS}" \
    --ks-pass env:WIDGET_KEYSTORE_PASSWORD --key-pass env:WIDGET_KEY_PASSWORD \
    --out "$output/hwarang-month-widget.apk" "$output/hwarang-month-widget-unsigned.apk"
  "$tools/apksigner" verify --verbose "$output/hwarang-month-widget.apk"
fi
