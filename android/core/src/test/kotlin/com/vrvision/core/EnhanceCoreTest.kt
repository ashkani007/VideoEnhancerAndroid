package com.vrvision.core

import com.vrvision.core.enhance.ColorMatrix
import com.vrvision.core.enhance.PixelOps
import com.vrvision.core.enhance.PreviewSegment
import com.vrvision.core.enhance.Rect
import com.vrvision.core.enhance.TilePlanner
import com.vrvision.core.enhance.Yuv420
import com.vrvision.core.stereo.StereoLayout
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class EnhanceCoreTest {

    @Test fun coresPartitionEveryRegionExactly() {
        for (layout in StereoLayout.entries) for ((w, h) in listOf(1920 to 1080, 200 to 90, 3840 to 1920, 129 to 257)) {
            val tiles = TilePlanner.tiles(w, h, layout, window = 128, overlap = 16)
            val cover = IntArray(w * h)
            for (t in tiles) {
                assertEquals(128, t.window.w); assertEquals(128, t.window.h)
                for (y in t.core.y until t.core.bottom) for (x in t.core.x until t.core.right) cover[y * w + x]++
            }
            assertTrue(cover.all { it == 1 }, "cores must cover $layout ${w}x$h exactly once")
        }
    }

    @Test fun coresKeepDistanceFromInteriorWindowEdges() {
        val tiles = TilePlanner.tiles(1000, 600, StereoLayout.MONO, 128, 16)
        for (t in tiles) {
            if (t.core.x > t.region.x) assertTrue(t.core.x - t.window.x >= 16)
            if (t.core.right < t.region.right) assertTrue(t.window.right - t.core.right >= 16)
            if (t.core.y > t.region.y) assertTrue(t.core.y - t.window.y >= 16)
        }
    }

    @Test fun stereoCoresNeverCrossTheSeam() {
        val w = 1000; val h = 400
        for (t in TilePlanner.tiles(w, h, StereoLayout.SIDE_BY_SIDE, 128, 16)) {
            assertTrue(t.core.right <= w / 2 || t.core.x >= w / 2)
            assertTrue(t.core.x >= t.region.x && t.core.right <= t.region.right)
        }
    }

    @Test fun windowExtractionReplicatesInsideRegionOnly() {
        // 4x2 frame: left eye red, right eye blue (SBS).
        val w = 4; val h = 2
        val rgb = ByteArray(w * h * 3)
        for (y in 0 until h) for (x in 0 until w) {
            val i = (y * w + x) * 3
            if (x < 2) rgb[i] = 255.toByte() else rgb[i + 2] = 255.toByte()
        }
        val left = Rect(0, 0, 2, 2)
        // A window extending into the right half must still contain only left-eye pixels.
        val t = PixelOps.extractWindow(rgb, w, Rect(0, 0, 4, 4), left)
        val plane = 16
        for (i in 0 until plane) {
            assertEquals(1f, t[i]); assertEquals(0f, t[2 * plane + i])
        }
    }

    @Test fun yuvRgbRoundTripPreservesColors() {
        val w = 8; val h = 8
        val colors = listOf(floatArrayOf(1f, 0f, 0f), floatArrayOf(0f, 1f, 0f), floatArrayOf(0f, 0f, 1f), floatArrayOf(0.5f, 0.5f, 0.5f), floatArrayOf(1f, 1f, 1f))
        for (m in ColorMatrix.entries) for (c in colors) {
            val planar = FloatArray(3 * w * h) { i -> c[i / (w * h)] }
            val yuv = Yuv420.i420(w, h)
            PixelOps.rgbPlanarToYuv(planar, w, h, yuv, 0, 0, m)
            val rgb = PixelOps.yuvToRgb(yuv, m)
            for (k in 0 until 3) {
                val got = (rgb[k].toInt() and 0xFF) / 255f
                assertTrue(abs(got - c[k]) < 0.02f, "$m ${c.toList()} channel $k got $got")
            }
        }
    }

    @Test fun rgbToYuvAtOffsetWritesOnlyTarget() {
        val dst = Yuv420.i420(8, 8)
        dst.y.fill(16)
        PixelOps.rgbPlanarToYuv(FloatArray(3 * 4 * 4) { 1f }, 4, 4, dst, 4, 4, ColorMatrix.BT709)
        assertEquals(235, dst.y[4 * 8 + 4].toInt() and 0xFF)
        assertEquals(16, dst.y[0].toInt() and 0xFF)
        assertEquals(16, dst.y[3 * 8 + 3].toInt() and 0xFF)
    }

    @Test fun areaResizeAveragesExactly() {
        // 4x4 -> 2x2: each output = mean of a 2x2 block.
        val src = FloatArray(3 * 16) { (it % 16).toFloat() }
        val out = PixelOps.areaResize(src, 4, 4, 2, 2)
        assertEquals((0 + 1 + 4 + 5) / 4f, out[0], 1e-5f)
        assertEquals((10 + 11 + 14 + 15) / 4f, out[3], 1e-5f)
        // Non-integer factor keeps the mean of a constant image.
        val flat = PixelOps.areaResize(FloatArray(3 * 30 * 30) { 0.25f }, 30, 30, 21, 21)
        assertTrue(flat.all { abs(it - 0.25f) < 1e-5f })
    }

    @Test fun unsharpSharpensEdgesButLeavesFlatAreas() {
        val img = Yuv420.i420(16, 16)
        for (y in 0 until 16) for (x in 0 until 16) img.y[y * 16 + x] = (if (x < 8) 60 else 180).toByte()
        PixelOps.unsharpLuma(img, 0.5f)
        val flat = img.y[8 * 16 + 2].toInt() and 0xFF
        val edgeDark = img.y[8 * 16 + 7].toInt() and 0xFF
        val edgeBright = img.y[8 * 16 + 8].toInt() and 0xFF
        assertEquals(60, flat)
        assertTrue(edgeDark < 60 && edgeBright > 180)
    }

    @Test fun previewSegmentFitsInsideVideo() {
        assertEquals(20_000, PreviewSegment.suggestedStart(60_000))
        assertEquals(50_000, PreviewSegment.clampStart(58_000, 60_000))
        assertEquals(0, PreviewSegment.clampStart(5_000, 6_000))
        assertEquals(6_000, PreviewSegment.length(6_000))
    }
}
