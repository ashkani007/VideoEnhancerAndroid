package com.lensprompt.app

import com.lensprompt.app.data.AppSettings
import com.lensprompt.app.data.Script
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AppLogicTest {

    @Test
    fun screensRoundTripThroughSavedState() {
        val screens = listOf(Screen.Library, Screen.Settings, Screen.Pro, Screen.About, Screen.Editor("a-1"), Screen.Prompter("b-2"))
        for (s in screens) assertEquals(s, Screen.decode(s.encode()))
    }

    @Test
    fun defaultSettingsProduceDefaultSmartFollowTuning() {
        val cfg = AppSettings().smartFollowConfig()
        assertTrue(cfg.pauseMs in 1_000..2_000)
        assertTrue(cfg.minConfidence in 0.3..0.45)
    }

    @Test
    fun manualSpeedIncreasesWithSetting() {
        assertTrue(AppSettings(manualSpeed = 8f).manualSpeedDp > AppSettings(manualSpeed = 2f).manualSpeedDp)
    }

    @Test
    fun wordCountIgnoresWhitespace() {
        val s = Script("id", "t", "  one two\n\nthree   ", 0, 0)
        assertEquals(3, s.wordCount)
    }
}
