package com.lensprompt.core

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class AudioDspTest {

    private fun sine(rate: Int, hz: Double, n: Int, amp: Double = 10_000.0) =
        ShortArray(n) { (amp * sin(2 * PI * hz * it / rate)).toInt().toShort() }

    @Test
    fun `level rises with amplitude and silence is low`() {
        val quiet = AudioDsp.levelDb(ShortArray(480))
        val soft = AudioDsp.levelDb(sine(48_000, 440.0, 480, 300.0))
        val loud = AudioDsp.levelDb(sine(48_000, 440.0, 480, 10_000.0))
        assertTrue(quiet < soft && soft < loud, "$quiet $soft $loud")
        assertEquals(20 * kotlin.math.log10(10_000 / kotlin.math.sqrt(2.0)), loud.toDouble(), 0.5)
    }

    @Test
    fun `48k to 16k keeps duration and frequency`() {
        val r = AudioDsp.To16k(48_000)
        val outA = r.process(sine(48_000, 300.0, 4_800))
        assertEquals(1_600, outA.size)
        // zero crossings of a 300 Hz tone over 0.1 s ≈ 60
        val crossings = outA.toList().zipWithNext().count { (a, b) -> (a < 0) != (b < 0) }
        assertTrue(crossings in 55..65, "crossings $crossings")
    }

    @Test
    fun `44_1k to 16k is continuous across chunks`() {
        val r = AudioDsp.To16k(44_100)
        val full = sine(44_100, 200.0, 44_100)
        var total = 0
        var i = 0
        val chunks = ArrayList<ShortArray>()
        while (i < full.size) {
            val n = minOf(1_024, full.size - i)
            chunks += r.process(full.copyOfRange(i, i + n))
            i += n
        }
        chunks.forEach { total += it.size }
        assertTrue(abs(total - 16_000) <= 2, "total $total")
        val joined = chunks.flatMap { it.toList() }
        val maxJump = joined.zipWithNext().maxOf { (a, b) -> abs(a - b) }
        // natural max slope of a 200 Hz, 10k-amplitude tone at 16 kHz is 2π·200/16000·10000 ≈ 785
        assertTrue(maxJump < 830, "discontinuity $maxJump")
    }

    @Test
    fun `audio alignment to the video timeline`() {
        // audio started 250 ms before video → drop 250 ms of audio
        val a = AudioDsp.alignAudioToVideo(1_000_000_000, 1_250_000_000, 48_000)
        assertEquals(12_000, a.skipFrames)
        assertEquals(0, a.startOffsetUs)
        // audio started 40 ms after video → offset its first sample by 40 ms
        val b = AudioDsp.alignAudioToVideo(1_040_000_000, 1_000_000_000, 48_000)
        assertEquals(0, b.skipFrames)
        assertEquals(40_000, b.startOffsetUs)
    }

    @Test
    fun `video start estimate uses the earliest implied start`() {
        val e = AudioDsp.VideoStartEstimator()
        e.onStarted(5_100_000_000)
        e.onStatus(6_000_000_000, 950_000_000) // implies 5.05 s
        e.onStatus(7_100_000_000, 2_000_000_000) // implies 5.10 s (late callback)
        assertEquals(5_050_000_000, e.estimateNanos)
    }
}
