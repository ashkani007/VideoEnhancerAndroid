package com.vrvision.core

import com.vrvision.core.enhance.FrameUpscaler
import com.vrvision.core.enhance.NearestEngine
import com.vrvision.core.stereo.StereoLayout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class FrameUpscalerTest {

    private fun frame(w: Int, h: Int) = ByteArray(w * h * 3) { i -> ((i * 31 + i / 7) % 251).toByte() }

    @Test fun tiledNearestEqualsWholeFrameNearestAtNativeScale() {
        // With an exact engine, tiling must be invisible: every output pixel equals the
        // source pixel it maps to, including at tile seams and the stereo seam.
        for (layout in StereoLayout.entries) {
            val w = 150; val h = 94
            val src = frame(w, h)
            val out = ByteArray(w * 4 * h * 4 * 3)
            FrameUpscaler(NearestEngine(4, 48), overlap = 8).upscale(src, w, h, layout, out, w * 4, h * 4)
            for (y in 0 until h * 4) for (x in 0 until w * 4) for (c in 0 until 3) {
                assertEquals(src[((y / 4) * w + x / 4) * 3 + c], out[(y * w * 4 + x) * 3 + c], "$layout ($x,$y,$c)")
            }
        }
    }

    @Test fun twoXOutputIsAreaAverageOfNativeOutput() {
        val w = 100; val h = 60
        val src = frame(w, h)
        val out = ByteArray(w * 2 * h * 2 * 3)
        FrameUpscaler(NearestEngine(4, 48), overlap = 8).upscale(src, w, h, StereoLayout.SIDE_BY_SIDE, out, w * 2, h * 2)
        // Nearest 4x then area 2x == nearest 2x exactly.
        var maxErr = 0
        for (y in 0 until h * 2) for (x in 0 until w * 2) for (c in 0 until 3) {
            val e = (src[((y / 2) * w + x / 2) * 3 + c].toInt() and 0xFF) - (out[(y * w * 2 + x) * 3 + c].toInt() and 0xFF)
            maxErr = maxOf(maxErr, kotlin.math.abs(e))
        }
        assertTrue(maxErr <= 1, "max error $maxErr")
    }

    @Test fun everyOutputPixelIsWritten() {
        val w = 77; val h = 41
        val out = ByteArray(154 * 82 * 3) { 7 }
        val src = ByteArray(w * h * 3) { 100 }
        FrameUpscaler(NearestEngine(4, 32), overlap = 6).upscale(src, w, h, StereoLayout.TOP_BOTTOM, out, 154, 82)
        assertTrue(out.all { it == 100.toByte() })
    }
}
