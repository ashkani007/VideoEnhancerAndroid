package com.lensprompt.app

import android.Manifest
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import com.lensprompt.app.data.ScriptRepository
import com.lensprompt.app.prompter.PrompterViewModel
import com.lensprompt.app.prompter.RunState
import com.lensprompt.core.FollowState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Launch-level smoke test on a real Android runtime: the app starts, shows the
 * library, opens the prompter, scrolls in manual mode, and runs Smart Follow
 * end to end (with the debug speech simulator, because emulators have no real
 * microphone input) without crashing.
 *
 * The prompter animates every frame while running, so the test drives the
 * Compose frame clock manually (autoAdvance = false) for determinism.
 */
@RunWith(AndroidJUnit4::class)
class SmokeTest {

    @get:Rule(order = 0)
    val permissions: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA)

    @get:Rule(order = 1)
    val compose = createAndroidComposeRule<MainActivity>()

    private val app get() = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as LensPromptApplication

    @Before
    fun setUp() {
        compose.runOnUiThread {
            app.settings.update {
                it.copy(firstRunDone = true, countdownSeconds = 0, showCamera = false, smartFollow = false, debugMode = false)
            }
        }
        compose.waitUntil(10_000) {
            compose.onAllNodesWithContentDescription("Start prompting").fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test
    fun libraryListsScriptsAndCreatesNew() {
        compose.onNodeWithText(ScriptRepository.WELCOME_TITLE, useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Search scripts").assertExists()
        val before = app.scripts.scripts.value.size
        // Creating a script opens the editor with autosave.
        compose.onNodeWithText("New script").performClick()
        compose.waitUntil(5_000) { compose.onAllNodesWithText("Type or paste your script…").fetchSemanticsNodes().isNotEmpty() }
        assertEquals(before + 1, app.scripts.scripts.value.size)
        compose.onNodeWithContentDescription("Back").performClick()
        compose.waitUntil(5_000) {
            compose.onAllNodesWithContentDescription("Start prompting").fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test
    fun manualScrollAndSmartFollowRunWithoutCrashing() {
        val scriptId = app.scripts.scripts.value.first().id
        compose.onAllNodesWithContentDescription("Start prompting").onFirst().performClick()
        compose.waitForIdle() // prompter is settled → no frames requested → idle
        val vm = ViewModelProvider(compose.activity.viewModelStore, PrompterViewModel.Factory(app, scriptId))[
            "prompter-$scriptId", PrompterViewModel::class.java,
        ]

        // ---- Manual mode: the text moves continuously while running.
        compose.mainClock.autoAdvance = false
        compose.onNodeWithContentDescription("Start").performClick()
        compose.mainClock.advanceTimeBy(2_000)
        assertEquals(RunState.RUNNING, vm.ui.value.runState)
        val moved = vm.scrollPositionPx()
        assertTrue("manual mode did not scroll (pos=$moved)", moved > 20.0)
        compose.onNodeWithContentDescription("Pause").performClick()
        compose.mainClock.advanceTimeBy(1_000) // decelerate to a stop
        assertEquals(RunState.PAUSED, vm.ui.value.runState)
        assertEquals(0.0, vm.scrollVelocityPx(), 0.0)

        // ---- Smart Follow fed by the debug speech simulator.
        compose.runOnUiThread {
            app.settings.update { it.copy(smartFollow = true, debugMode = true) }
            vm.resetToStart()
            vm.setSimulation(true)
            vm.play()
        }
        // Simulated speech runs in real time on the Smart Follow worker; frames on the test clock.
        repeat(40) {
            Thread.sleep(100)
            compose.mainClock.advanceTimeBy(100)
        }
        val follow = vm.debug.value.follow
        assertNotNull("no Smart Follow output", follow)
        assertTrue("Smart Follow never aligned (matched=${follow!!.matchedIndex})", follow.matchedIndex >= 4)
        assertTrue("unexpected state ${follow.state}", follow.state != FollowState.ERROR && follow.state != FollowState.IDLE)
        assertTrue("text did not follow (pos=${vm.scrollPositionPx()})", vm.scrollPositionPx() > 20.0)
        compose.onNodeWithText("Matched index", substring = true).assertExists()

        compose.runOnUiThread { vm.stop() }
        compose.mainClock.advanceTimeBy(1_000)
        assertEquals(RunState.STOPPED, vm.ui.value.runState)
    }
}
