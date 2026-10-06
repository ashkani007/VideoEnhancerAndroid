package com.lensprompt.core

import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class VelocityAndScrollTest {

    private val config = SmartFollowConfig()

    @Test
    fun `constant reading rate is estimated`() {
        val v = ReadingVelocityEstimator(config)
        var t = 0L
        for (i in 1..40) { t += 333; v.addSample(t, i.toDouble()) } // 3 tokens/s
        assertEquals(3.0, v.velocity, 0.25)
    }

    @Test
    fun `bursty samples do not spike the estimate`() {
        val v = ReadingVelocityEstimator(config)
        var t = 0L
        var p = 0.0
        val seen = ArrayList<Double>()
        repeat(30) { k ->
            // recognizer delivers 3 words every 1.2 s (2.5 tok/s) with jittered timing
            t += if (k % 2 == 0) 900 else 1500
            p += 3
            v.addSample(t, p)
            seen += v.velocity
        }
        assertTrue(seen.drop(8).all { it in 1.6..3.4 }, "estimates $seen")
    }

    @Test
    fun `scroll controller never jumps and converges`() {
        val s = TeleprompterScrollController(config)
        val dt = 1 / 60.0
        var last = s.position
        var maxStep = 0.0
        // target jumps 500px ahead instantly
        repeat(600) {
            s.follow(dt, 500.0, 0.0)
            maxStep = maxOf(maxStep, abs(s.position - last))
            last = s.position
        }
        assertTrue(maxStep <= config.maxScrollVelocityPx * dt + 1e-9, "max step $maxStep")
        assertEquals(500.0, s.position, 3.0)
        assertTrue(abs(s.velocity) < 5)
    }

    @Test
    fun `small backward target does not reverse the text`() {
        val s = TeleprompterScrollController(config)
        s.snapTo(1000.0)
        repeat(120) { s.follow(1 / 60.0, 1000.0 - config.backwardDeadZonePx * 0.8, 0.0) }
        assertEquals(1000.0, s.position, 1e-6)
    }

    @Test
    fun `feed forward tracks a steadily moving target with small lag`() {
        val s = TeleprompterScrollController(config)
        val dt = 1 / 60.0
        var target = 0.0
        repeat(600) {
            target += 80.0 * dt
            s.follow(dt, target, 80.0)
        }
        assertEquals(80.0, s.velocity, 3.0)
        assertTrue(abs(target - s.position) < 10, "lag ${target - s.position}")
    }

    @Test
    fun `progress mapper is continuous and invertible`() {
        val m = ProgressMapper(floatArrayOf(0f, 0f, 0f, 40f, 40f, 80f), 120f)
        var prev = -1.0
        var p = 0.0
        while (p < 6.0) {
            val y = m.yAt(p)
            assertTrue(y >= prev)
            prev = y
            p += 0.05
        }
        assertEquals(4.5, m.progressAt(m.yAt(4.5)), 1e-6)
    }

    @Test
    fun `user settings map into the config`() {
        val calm = SmartFollowConfig.fromUserSettings(0f, 0f, 0f)
        val snappy = SmartFollowConfig.fromUserSettings(1f, 1f, 1f)
        assertTrue(calm.scrollGain < snappy.scrollGain)
        assertTrue(calm.pauseMs > snappy.pauseMs)
        assertTrue(calm.minTokenSimilarity < snappy.minTokenSimilarity)
    }
}
