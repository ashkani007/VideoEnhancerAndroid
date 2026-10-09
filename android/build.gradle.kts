// Plugin versions are declared once in settings.gradle.kts (pluginManagement).
// They are intentionally not hoisted here: AGP can only be resolved from Google Maven, and
// keeping it scoped to :app lets `./gradlew :core:test` run on machines without Google Maven
// or an Android SDK. (Gradle prints a harmless "Kotlin plugin loaded multiple times" notice.)
// See docs/DEPENDENCIES.md for how each version was chosen and verified.
