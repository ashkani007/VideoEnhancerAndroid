#!/usr/bin/env bash
# Called inside android-emulator-runner while its emulator is still alive.
set -eu
collect_evidence() {
    mkdir -p ../evidence
    adb pull /data/local/tmp/lensprompt-store-screenshots ../evidence/store-screenshots || true
    adb logcat -d -s AndroidRuntime:E > ../evidence/android-runtime-errors.txt || true
}
trap collect_evidence EXIT
adb shell svc power stayon true
adb shell wm size 1080x1920
adb shell settings put system screen_off_timeout 1800000
adb shell input keyevent 82
./gradlew --no-daemon connectedDebugAndroidTest \
    -Pandroid.testInstrumentationRunnerArguments.class=com.lensprompt.app.StoreScreenshotTest,com.lensprompt.app.SmokeTest,com.lensprompt.app.FloatingOverlayTest,com.lensprompt.app.AvMuxerTest
for name in 01-library 02-script-editor 03-manual-prompter 04-settings 05-privacy-and-licenses 06-floating-window; do
    adb shell test -s "/data/local/tmp/lensprompt-store-screenshots/$name.png"
done
