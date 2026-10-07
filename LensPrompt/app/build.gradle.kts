import org.jetbrains.kotlin.gradle.dsl.JvmTarget

/*
 * Release signing comes ONLY from the environment (CI secrets or a developer's
 * shell). Nothing secret is ever read from, or written to, the repository.
 * Without these variables the release build is produced unsigned (CI keeps
 * working); see docs/RELEASE_SIGNING.md.
 */
val uploadKeystore: String? = System.getenv("LENSPROMPT_UPLOAD_KEYSTORE")?.takeIf { it.isNotBlank() && file(it).exists() }
val uploadStorePassword: String? = System.getenv("LENSPROMPT_UPLOAD_STORE_PASSWORD")
val uploadKeyAlias: String? = System.getenv("LENSPROMPT_UPLOAD_KEY_ALIAS")
val uploadKeyPassword: String? = System.getenv("LENSPROMPT_UPLOAD_KEY_PASSWORD")
val hasUploadKey = uploadKeystore != null && !uploadStorePassword.isNullOrEmpty() &&
    !uploadKeyAlias.isNullOrEmpty() && !uploadKeyPassword.isNullOrEmpty()

/** Play requires a strictly increasing versionCode; CI passes its run number. */
val ciVersionCode: Int = System.getenv("LENSPROMPT_VERSION_CODE")?.toIntOrNull() ?: 1

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.lensprompt.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.lensprompt.app"
        minSdk = 26
        targetSdk = 35
        // com.lensprompt.app is the permanent production application ID.
        versionCode = ciVersionCode
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // Offline speech (Vosk) ships a native library per ABI (~10 MB each).
        // Phones are arm64/armv7; x86_64 is kept for the emulator tests.
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64") }

        // LensPrompt Pro purchases. OFF for 1.0: no Play Billing connection, no
        // purchases, Pro never granted. Turn on only for a Play testing track with
        // -Plensprompt.billingEnabled=true once the products exist in Play Console.
        buildConfigField("boolean", "BILLING_ENABLED", (findProperty("lensprompt.billingEnabled") ?: "false").toString())
        // Public URLs filled in when they exist (-Plensprompt.privacyPolicyUrl=…).
        buildConfigField("String", "PRIVACY_POLICY_URL", "\"${findProperty("lensprompt.privacyPolicyUrl") ?: ""}\"")
        buildConfigField("String", "SUPPORT_EMAIL", "\"${findProperty("lensprompt.supportEmail") ?: ""}\"")
    }

    signingConfigs {
        if (hasUploadKey) {
            create("upload") {
                storeFile = file(uploadKeystore!!)
                storePassword = uploadStorePassword
                keyAlias = uploadKeyAlias
                keyPassword = uploadKeyPassword
            }
        }
    }

    buildTypes {
        release {
            // Signed with the upload key when it is provided; otherwise unsigned.
            signingConfig = if (hasUploadKey) signingConfigs.getByName("upload") else null
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
        // Same code as release (R8, shrinking) but signed with the debug key, so CI
        // can install and launch the minified app on the emulator. Never uploaded.
        create("qa") {
            initWith(getByName("release"))
            signingConfig = signingConfigs.getByName("debug")
            matchingFallbacks += listOf("release")
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

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

dependencies {
    implementation(project(":core"))

    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-service:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    val camerax = "1.4.1"
    implementation("androidx.camera:camera-core:$camerax")
    implementation("androidx.camera:camera-camera2:$camerax")
    implementation("androidx.camera:camera-lifecycle:$camerax")
    implementation("androidx.camera:camera-video:$camerax")
    implementation("androidx.camera:camera-view:$camerax")

    // Google Play Billing for LensPrompt Pro (inactive unless BILLING_ENABLED).
    implementation("com.android.billingclient:billing:8.0.0")

    // Offline streaming speech recognition on LensPrompt's own PCM (Vosk / Kaldi).
    // Models are not bundled; they are downloaded or imported per language.
    implementation("com.alphacephei:vosk-android:0.3.75@aar")
    implementation("net.java.dev.jna:jna:5.18.1@aar")

    // On-device face contours for lip-movement detection (bundled model, no network).
    implementation("com.google.mlkit:face-detection:16.1.7")

    testImplementation("junit:junit:4.13.2")
    testImplementation(kotlin("test"))

    androidTestImplementation(composeBom)
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:rules:1.6.1")
}
