package com.lensprompt.app

import android.Manifest
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import com.lensprompt.app.data.ScriptRepository
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Launch-level smoke test: the app starts, shows the library with the welcome
 * script, opens the prompter, and runs both manual scrolling and Smart Follow
 * (with simulated speech, since emulators have no real microphone input)
 * without crashing.
 */
@RunWith(AndroidJUnit4::class)
class SmokeTest {

    @get:Rule(order = 0)
    val permissions: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA)

    @get:Rule(order = 1)
    val compose = createAndroidComposeRule<MainActivity>()

    @Before
    fun setUp() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as LensPromptApplication
        app.settings.update { it.copy(firstRunDone = true, countdownSeconds = 0, showCamera = false) }
    }

    @Test
    fun libraryShowsWelcomeScript() {
        compose.waitUntil(10_000) {
            compose.onAllNodesWithContentDescription("Start prompting").fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithText(ScriptRepository.WELCOME_TITLE).assertIsDisplayed()
        compose.onNodeWithText("New script").assertIsDisplayed()
    }

    @Test
    fun manualAndSimulatedSmartFollowRunWithoutCrashing() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as LensPromptApplication
        compose.waitUntil(10_000) {
            compose.onAllNodesWithContentDescription("Start prompting").fetchSemanticsNodes().isNotEmpty()
        }

        // Manual mode
        app.settings.update { it.copy(smartFollow = false) }
        compose.onAllNodesWithContentDescription("Start prompting").onFirst().performClick()
        compose.onNodeWithContentDescription("Start").performClick()
        compose.waitUntil(5_000) { compose.onAllNodesWithContentDescription("Pause").fetchSemanticsNodes().isNotEmpty() }
        Thread.sleep(1_500)
        compose.onNodeWithContentDescription("Pause").performClick()

        // Smart Follow driven by the debug speech simulator
        app.settings.update { it.copy(smartFollow = true, debugMode = true) }
        compose.onNodeWithContentDescription("Display settings").performClick()
        compose.onNodeWithText("Debug: simulated speech (no mic)").performClick()
        InstrumentationRegistry.getInstrumentation().uiAutomation.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK)
        compose.waitForIdle()
        compose.onNodeWithContentDescription("Resume").performClick()
        Thread.sleep(4_000)
        // The debug HUD shows live Smart Follow internals once the controller runs.
        compose.onNodeWithText("Matched index", substring = true).assertIsDisplayed()
        compose.onNodeWithText("Recognizer", substring = true).assertIsDisplayed()
    }
}
