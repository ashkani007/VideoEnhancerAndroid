package com.lensprompt.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class OverlayGeometryTest {
    private val g = OverlayGeometry(minWidth = 400, minHeight = 250)
    private val portraitW = 1080
    private val portraitH = 2340

    private fun assertOnScreen(r: WindowRect, w: Int, h: Int) {
        assertTrue(r.x >= 0 && r.y >= 0, "off top/left: $r")
        assertTrue(r.x + r.width <= w && r.y + r.height <= h, "off right/bottom: $r on ${w}x$h")
    }

    @Test
    fun windowNeverLeavesTheScreen() {
        val r = g.clamp(WindowRect(900, 2200, 600, 500), portraitW, portraitH)
        assertOnScreen(r, portraitW, portraitH)
        assertEquals(600, r.width)
        assertEquals(500, r.height)
        val moved = g.move(r, -5000, 9000, portraitW, portraitH)
        assertOnScreen(moved, portraitW, portraitH)
        assertEquals(0, moved.x)
    }

    @Test
    fun resizeIsContinuousAndRespectsMinimumAndScreen() {
        val start = WindowRect(100, 300, 600, 400)
        assertEquals(WindowRect(100, 300, 637, 419), g.resize(start, 37, 19, portraitW, portraitH))
        val tiny = g.resize(start, -10_000, -10_000, portraitW, portraitH)
        assertEquals(400, tiny.width)
        assertEquals(250, tiny.height)
        val huge = g.resize(start, 10_000, 10_000, portraitW, portraitH)
        assertEquals(portraitW - 100, huge.width) // grows to the screen edge, not past it
        assertEquals(portraitH - 300, huge.height)
        assertOnScreen(huge, portraitW, portraitH)
    }

    @Test
    fun rotationKeepsTheWindowVisibleAndRoughlyInPlace() {
        val tall = WindowRect(40, 1600, 1000, 700) // lower part of a portrait screen
        val land = g.reorient(tall, portraitW, portraitH, portraitH, portraitW)
        assertOnScreen(land, portraitH, portraitW)
        assertEquals(1000, land.width)
        assertEquals(700, land.height)
        assertTrue(land.y > portraitW / 3, "should stay in the lower part: $land")
        val back = g.reorient(land, portraitH, portraitW, portraitW, portraitH)
        assertOnScreen(back, portraitW, portraitH)
        // A window wider than the new screen is shrunk to fit.
        val wide = g.reorient(WindowRect(0, 0, 2200, 600), portraitH, portraitW, portraitW, portraitH)
        assertEquals(portraitW, wide.width)
    }

    @Test
    fun presetsFitBothOrientations() {
        for ((w, h) in listOf(portraitW to portraitH, portraitH to portraitW)) {
            val near = g.nearCamera(w, h, topInset = 80, lineHeight = 90, toolbar = 110)
            assertOnScreen(near, w, h)
            assertTrue(near.width < w, "near-camera should be narrow")
            assertTrue(near.height <= 110 + 90 * 4, "about three lines: $near")
            assertOnScreen(g.defaultRect(w, h, 80), w, h)
            assertOnScreen(g.large(w, h, 80), w, h)
        }
    }

    @Test
    fun restoredLayoutFromABiggerScreenIsClamped() {
        val r = g.clamp(WindowRect(-50, 3000, 5000, 5000), portraitW, portraitH)
        assertEquals(WindowRect(0, 0, portraitW, portraitH), r)
    }
}
