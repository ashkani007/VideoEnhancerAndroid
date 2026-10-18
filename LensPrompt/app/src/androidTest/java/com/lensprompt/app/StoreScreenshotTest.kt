package com.lensprompt.app

import android.Manifest
import android.graphics.Bitmap
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import com.lensprompt.app.data.ScriptRepository
import com.lensprompt.app.overlay.OverlayService
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Captures the real app UI. No simulated speech or generated camera imagery. */
@RunWith(AndroidJUnit4::class)
class StoreScreenshotTest {
    @get:Rule(order = 0)
    val permissions: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)

    @get:Rule(order = 1)
    val compose = createAndroidComposeRule<MainActivity>()

    private val instr get() = InstrumentationRegistry.getInstrumentation()
    private val app get() = instr.targetContext.applicationContext as LensPromptApplication

    private fun capture(name: String) {
        compose.waitForIdle()
        // Allow compositor/keyboard transitions to settle; this is not a speech test.
        SystemClock.sleep(350)
        val bitmap = requireNotNull(instr.uiAutomation.takeScreenshot()) { "No actual display screenshot" }
        bitmap.setHasAlpha(false)
        val dir = File(instr.targetContext.getExternalFilesDir(null), "store-screenshots").apply { mkdirs() }
        File(dir, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }

    @Test
    fun captureRealScreensAndVerifyPrivacyEntry() {
        compose.runOnUiThread {
            app.settings.update { it.copy(firstRunDone = true, showCamera = false, smartFollow = false, countdownSeconds = 0, debugMode = false) }
        }
        compose.waitUntil(15_000) { app.scripts.loaded.value }
        capture("01-library")
        val script = app.scripts.scripts.value.first { it.title == ScriptRepository.WELCOME_TITLE }
        compose.onNodeWithText(script.title, useUnmergedTree = true).performClick()
        compose.onNodeWithText("Prompt").assertExists()
        capture("02-script-editor")
        compose.onNodeWithText("Prompt").performClick()
        compose.onNodeWithContentDescription("Start").assertExists()
        capture("03-manual-prompter")
        compose.onNodeWithContentDescription("Back").performClick()
        compose.onNodeWithContentDescription("Settings").performClick()
        capture("04-settings")
        compose.onNodeWithText("About, privacy & licenses").performScrollTo().performClick()
        compose.onNodeWithText("Privacy policy").assertExists()
        compose.onNodeWithText("Contact support").assertExists()
        assertTrue(BuildConfig.PRIVACY_POLICY_URL.startsWith("https://"))
        assertTrue(BuildConfig.SUPPORT_EMAIL.isNotBlank())
        capture("05-privacy-and-licenses")
        compose.onNodeWithContentDescription("Back").performClick()
        compose.onNodeWithContentDescription("Back").performClick()

        // Shell app-op is confined to this disposable emulator; the user grants
        // the same permission through Android Settings on a real device.
        ParcelFileDescriptor.AutoCloseInputStream(
            instr.uiAutomation.executeShellCommand("appops set ${instr.targetContext.packageName} SYSTEM_ALERT_WINDOW allow"),
        ).use { it.readBytes() }
        compose.runOnUiThread { OverlayService.start(compose.activity, script.id) }
        compose.waitUntil(10_000) { OverlayService.running }
        SystemClock.sleep(1_000)
        capture("06-floating-window")
        compose.runOnUiThread { OverlayService.stop(compose.activity) }
    }
}
