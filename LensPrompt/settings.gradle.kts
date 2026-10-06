pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
    plugins {
        id("com.android.application") version "8.7.3"
        id("org.jetbrains.kotlin.android") version "2.1.20"
        id("org.jetbrains.kotlin.jvm") version "2.1.20"
        id("org.jetbrains.kotlin.plugin.compose") version "2.1.20"
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "LensPrompt"

// The pure-Kotlin Smart Follow engine builds and tests anywhere a JDK exists.
include(":core")

// The Android app needs an Android SDK. Skip it (with a notice) when none is
// configured so `./gradlew :core:test` still works on SDK-less machines.
val localProps = java.util.Properties().apply {
    val f = file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val hasAndroidSdk = listOf(
    localProps.getProperty("sdk.dir"),
    System.getenv("ANDROID_HOME"),
    System.getenv("ANDROID_SDK_ROOT"),
).any { !it.isNullOrBlank() && file(it).exists() }

if (hasAndroidSdk) {
    include(":app")
} else {
    logger.warn("LensPrompt: no Android SDK found (sdk.dir / ANDROID_HOME); building :core only.")
}
