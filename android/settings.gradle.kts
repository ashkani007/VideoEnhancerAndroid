pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
    plugins {
        // AGP 8.13.0 (needs Gradle >= 8.13; KSP 2.3.x needs AGP >= 8.12).
        id("com.android.application") version "8.13.0"
        // Kotlin 2.3.x supports AGP 8.2.2–8.13 and can read Kotlin 2.2 metadata (Media3 1.11).
        id("org.jetbrains.kotlin.android") version "2.3.21"
        id("org.jetbrains.kotlin.jvm") version "2.3.21"
        id("org.jetbrains.kotlin.plugin.compose") version "2.3.21"
        // KSP2 (versioned independently of Kotlin since 2.3.0), used by Room.
        id("com.google.devtools.ksp") version "2.3.12"
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "VRVision"

// Pure-Kotlin logic (stereo mapping, projection, calibration, head tracking, planning,
// routing, tiling, pixel math). Builds and tests with only a JDK.
include(":core")

// The Android app needs an Android SDK. Skip it (with a warning) when none is
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
    logger.warn("VRVision: no Android SDK found (sdk.dir / ANDROID_HOME); building :core only.")
}
