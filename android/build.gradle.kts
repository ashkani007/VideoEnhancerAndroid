// Plugin versions are declared once in settings.gradle.kts (pluginManagement).
// The Kotlin plugins are loaded here so :core and :app share one Kotlin Gradle plugin
// instance. AGP and KSP stay in :app so `./gradlew :core:test` works without Google Maven
// or an Android SDK. See docs/DEPENDENCIES.md for how each version was chosen and verified.
plugins {
    id("org.jetbrains.kotlin.jvm") apply false
    id("org.jetbrains.kotlin.android") apply false
    id("org.jetbrains.kotlin.plugin.compose") apply false
}
