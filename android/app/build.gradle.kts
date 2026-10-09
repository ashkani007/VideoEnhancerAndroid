import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

/** CI passes its run number so every uploaded APK has a strictly increasing versionCode. */
val ciVersionCode: Int = System.getenv("VRVISION_VERSION_CODE")?.toIntOrNull() ?: 1

android {
    namespace = "com.vrvision.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.vrvision.app"
        minSdk = 29
        targetSdk = 36
        versionCode = ciVersionCode
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // ONNX Runtime ships native code per ABI. Phones are arm64; x86_64 for emulators.
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }

        // Cloud processing is opt-in and has no default server: the user enters the URL of
        // a backend they run (see backend/README.md). Nothing is uploaded without consent.
        buildConfigField("String", "DEFAULT_CLOUD_URL", "\"${findProperty("vrvision.cloudUrl") ?: ""}\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    androidResources {
        // The ONNX model must stay uncompressed so it can be memory-mapped/read quickly.
        noCompress += "onnx"
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
        jniLibs.useLegacyPackaging = false
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }

    lint {
        // Lint runs in CI; real errors fail the build, the report is uploaded as an artifact.
        abortOnError = true
        checkReleaseBuilds = false
        warningsAsErrors = false
    }
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    implementation(project(":core"))

    val composeBom = platform("androidx.compose:compose-bom:2026.06.01") // Compose 1.11.x; 1.12 needs compileSdk 37 + AGP 9.1
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core:1.7.8")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")

    val media3 = "1.11.1"
    implementation("androidx.media3:media3-exoplayer:$media3")
    implementation("androidx.media3:media3-common:$media3")
    implementation("androidx.media3:media3-transformer:$media3")
    implementation("androidx.media3:media3-effect:$media3")

    val room = "2.8.5"
    implementation("androidx.room:room-runtime:$room")
    ksp("androidx.room:room-compiler:$room")

    implementation("androidx.work:work-runtime-ktx:2.10.1")

    // On-device inference for the Real-ESRGAN compact model (see docs/MODELS.md for why
    // ONNX Runtime Mobile rather than LiteRT).
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.31.0")

    // Cloud client (only used after explicit consent, against a user-configured server).
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation(kotlin("test"))
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")

    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:core:1.6.1")
}
