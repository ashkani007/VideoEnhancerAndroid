#!/usr/bin/env bash
# Called inside android-emulator-runner while its emulator is still alive.
set -eu
collect_evidence() {
    mkdir -p ../evidence
    adb pull /sdcard/Android/data/com.lensprompt.app/files/store-screenshots ../evidence/ || true
    adb logcat -d -s AndroidRuntime:E > ../evidence/android-runtime-errors.txt || true
}
trap collect_evidence EXIT
adb shell svc power stayon true
adb shell wm size 1080x1920
adb shell settings put system screen_off_timeout 1800000
adb shell input keyevent 82
./gradlew --no-daemon connectedDebugAndroidTest \
    -Pandroid.testInstrumentationRunnerArguments.class=com.lensprompt.app.StoreScreenshotTest,com.lensprompt.app.SmokeTest,com.lensprompt.app.FloatingOverlayTest,com.lensprompt.app.AvMuxerTest
