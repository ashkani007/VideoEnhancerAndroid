package com.lensprompt.core

import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * End-to-end Smart Follow scenarios from the product spec, run through the
 * deterministic simulator (recognizer events → controller → scroll at 60 fps).
 */
class SmartFollowScenarioTest {

    private val config = SmartFollowConfig()
    private val frameDt = 0.016
    private val script = TestScripts.MACHINING

    private fun scenario() = SpeechScenario(script)
    private fun simulate(s: SpeechScenario, tail: Long = 3_000, startToken: Int = 0): List<SimFrame> =
        SmartFollowSimulator(script, config = config).run(s.events(), s.durationMs + tail, startToken)

    // --------------------------------------------------------------- helpers

    private fun assertNoVisualJumps(frames: List<SimFrame>) {
        val maxStep = frames.zipWithNext { a, b -> abs(b.scrollPx - a.scrollPx) }.maxOrNull() ?: 0.0
        assertTrue(maxStep <= config.maxScrollVelocityPx * frameDt + 1e-6, "visual jump of ${"%.1f".format(maxStep)} px in one frame")
        val maxAccel = frames.zipWithNext { a, b -> abs(b.scrollVelocityPx - a.scrollVelocityPx) / frameDt }.maxOrNull() ?: 0.0
        // + stop-snap epsilon (0.5 px/s) of the scroll controller
        assertTrue(maxAccel <= config.maxDecelerationPx + 0.5 / frameDt + 1e-6, "acceleration ${"%.0f".format(maxAccel)} px/s²")
    }

    private fun maxBackwardTravel(frames: List<SimFrame>): Double {
        var peak = Double.NEGATIVE_INFINITY
        var worst = 0.0
        for (f in frames) {
            peak = maxOf(peak, f.scrollPx)
            worst = maxOf(worst, peak - f.scrollPx)
        }
        return worst
    }

    private fun frameAt(frames: List<SimFrame>, t: Long) = frames.first { it.timeMs >= t }

    private fun matchedNeverJumpsMoreThan(frames: List<SimFrame>, maxJump: Int, from: Long = 0, to: Long = Long.MAX_VALUE) {
        frames.filter { it.timeMs in from..to }.zipWithNext { a, b ->
            val d = b.matchedIndex - a.matchedIndex
            if (d > maxJump || d < 0) fail("matched index moved ${a.matchedIndex} → ${b.matchedIndex} at ${b.timeMs} ms")
        }
    }

    private fun summary(frames: List<SimFrame>, every: Long = 500): String =
        frames.filter { it.timeMs % every < 16 }.joinToString("\n") {
            "%6d %-14s match=%3d tgt=%6.2f disp=%6.2f conf=%.2f v=%.2f sv=%.0f".format(
                it.timeMs, it.state, it.matchedIndex, it.targetProgress, it.displayedProgress,
                it.confidence, it.readingVelocity, it.scrollVelocityPx,
            )
        }

    // -------------------------------------------------------------- scenarios

    @Test
    fun `normal reading produces stable continuous forward progress`() {
        val s = scenario().read(0, 100, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        assertTrue(maxBackwardTravel(frames) < 1.0, "text moved backwards\n${summary(frames)}")

        val firstTracking = frames.first { it.state == FollowState.TRACKING }.timeMs
        assertTrue(firstTracking < 2_500, "located speaker only at $firstTracking ms")

        // While speaking, the text keeps moving (no word-by-word stop-and-go).
        val speaking = frames.filter { it.timeMs in 6_000..(s.durationMs - 500) }
        val stalled = speaking.count { it.scrollVelocityPx < 10.0 }
        assertTrue(stalled < speaking.size * 0.05, "stalled in $stalled/${speaking.size} frames\n${summary(frames)}")

        // Velocity steady: frame-to-frame speed changes are small.
        val speeds = speaking.map { it.scrollVelocityPx }
        val meanSpeed = speeds.average()
        assertEquals(2.5 * 30, meanSpeed, 15.0, "mean scroll speed")

        // Ends close to where the speaker stopped.
        val end = frames.last()
        assertEquals(99.0, end.matchedIndex.toDouble(), 1.0)
        assertTrue(abs(end.displayedProgress - 100) < 3.5, "display ${end.displayedProgress}\n${summary(frames)}")

        matchedNeverJumpsMoreThan(frames, config.smallJumpTokens)
    }

    @Test
    fun `reader keeps up with speech during reading`() {
        val s = scenario().read(0, 100, 2.5)
        val frames = simulate(s)
        // At several moments the displayed position is within a few words of the actual speaker.
        for (k in listOf(10, 30, 50, 80)) {
            val t = (k * 400L)
            val f = frameAt(frames, t)
            assertTrue(abs(f.displayedProgress - k) < 4.0, "at word $k display=${"%.2f".format(f.displayedProgress)}\n${summary(frames)}")
        }
    }

    @Test
    fun `fast reading raises velocity smoothly`() {
        val s = scenario().readRamp(0, 140, 2.0, 4.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        val early = frameAt(frames, 8_000).readingVelocity
        val late = frameAt(frames, s.durationMs - 1_000).readingVelocity
        assertTrue(late > early + 1.0, "velocity early=$early late=$late")
        val jumps = frames.zipWithNext { a, b -> abs(b.readingVelocity - a.readingVelocity) }.maxOrNull()!!
        assertTrue(jumps < 0.6, "velocity estimate jumped by $jumps")
        assertTrue(abs(frames.last().displayedProgress - 140) < 4.0)
    }

    @Test
    fun `slow reading lowers velocity smoothly`() {
        val s = scenario().readRamp(0, 90, 4.0, 1.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        val early = frameAt(frames, 6_000).readingVelocity
        val late = frameAt(frames, s.durationMs - 1_000).readingVelocity
        assertTrue(late < early - 1.0, "velocity early=$early late=$late\n${summary(frames)}")
        assertTrue(maxBackwardTravel(frames) < 1.0)
    }

    @Test
    fun `sudden speed change adapts within a few seconds without jitter`() {
        val s = scenario().read(0, 40, 2.0)
        val switchAt = s.durationMs
        s.read(40, 110, 4.0)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        val before = frameAt(frames, switchAt).readingVelocity
        val after = frameAt(frames, switchAt + 4_000).readingVelocity
        assertTrue(before in 1.6..2.4, "before=$before")
        assertTrue(after > 3.3, "velocity 4 s after the switch: $after\n${summary(frames)}")
        // Display keeps up with the faster reader.
        val f = frameAt(frames, switchAt + 8_000)
        val spoken = 40 + 8 * 4
        assertTrue(abs(f.displayedProgress - spoken) < 4.5, "display ${f.displayedProgress} vs spoken $spoken")
    }

    @Test
    fun `pause stops the text and keeps it stopped`() {
        val s = scenario().read(0, 40, 2.5)
        val pauseStart = s.durationMs
        s.silence(5_000)
        val pauseEnd = s.durationMs
        s.read(40, 80, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)

        // After debounce (+ recognizer latency) the text must be stopped for the rest of the pause.
        val stopAfter = pauseStart + 300 + config.pauseMs + 1_200
        val pauseFrames = frames.filter { it.timeMs in stopAfter..pauseEnd }
        assertTrue(pauseFrames.all { it.state == FollowState.PAUSED }, "states during pause: ${pauseFrames.map { it.state }.toSet()}")
        assertTrue(pauseFrames.all { abs(it.scrollVelocityPx) < 0.5 }, "still moving in pause\n${summary(frames)}")
        val drift = pauseFrames.last().scrollPx - pauseFrames.first().scrollPx
        assertTrue(abs(drift) < 0.5, "drifted $drift px while paused")
        // It stopped near the last spoken word, not far beyond it.
        assertTrue(abs(pauseFrames.last().displayedProgress - 40) < 4.0, "stopped at ${pauseFrames.last().displayedProgress}")
    }

    @Test
    fun `resume after pause reacquires and accelerates smoothly`() {
        val s = scenario().read(0, 40, 2.5).silence(5_000)
        val resumeAt = s.durationMs
        s.read(40, 90, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        val tracking = frames.first { it.timeMs > resumeAt && it.state == FollowState.TRACKING }
        assertTrue(tracking.timeMs - resumeAt < 2_000, "resumed tracking after ${tracking.timeMs - resumeAt} ms")
        assertTrue(maxBackwardTravel(frames) < 1.0)
        assertTrue(abs(frames.last().displayedProgress - 90) < 4.0, summary(frames))
        // velocity after resume comes back to reading speed
        val later = frameAt(frames, resumeAt + 6_000)
        assertTrue(later.scrollVelocityPx > 40, "scroll speed after resume ${later.scrollVelocityPx}")
    }

    @Test
    fun `misrecognized words cause no jumps`() {
        val subs = mapOf(12 to "tomato", 13 to "slowly", 25 to "quantum", 33 to "the", 47 to "banana", 48 to "rocket")
        val s = scenario().read(0, 90, 2.5, subs)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        assertTrue(maxBackwardTravel(frames) < 1.0)
        matchedNeverJumpsMoreThan(frames, config.smallJumpTokens)
        assertTrue(abs(frames.last().displayedProgress - 90) < 4.0, summary(frames))
    }

    @Test
    fun `repeating words does not oscillate or scroll back`() {
        val s = scenario().read(0, 30, 2.5).read(26, 30, 2.5).read(26, 60, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        assertTrue(maxBackwardTravel(frames) < 1.0, "scrolled back\n${summary(frames)}")
        matchedNeverJumpsMoreThan(frames, config.smallJumpTokens)
        assertTrue(abs(frames.last().displayedProgress - 60) < 4.0, summary(frames))
    }

    @Test
    fun `correction - speaker restarts the previous phrase`() {
        val s = scenario().read(0, 22, 2.5).silence(500).read(16, 50, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        assertTrue(maxBackwardTravel(frames) < config.backwardDeadZonePx, "scrolled back ${maxBackwardTravel(frames)}")
        assertTrue(abs(frames.last().displayedProgress - 50) < 4.0, summary(frames))
    }

    @Test
    fun `skipped sentence is eventually reacquired`() {
        // Skip "Operators watch ... vibration appears." (tokens 33..46)
        val words = scenario().words
        val skipFrom = words.indexOf("Operators")
        val skipTo = skipFrom + words.drop(skipFrom).indexOf("The")
        val s = scenario().read(0, skipFrom, 2.5).read(skipTo, skipTo + 40, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        val end = frames.last()
        assertTrue(end.matchedIndex >= skipTo + 37, "matched ${end.matchedIndex}\n${summary(frames)}")
        assertTrue(abs(end.displayedProgress - (skipTo + 40)) < 4.0)
    }

    @Test
    fun `off-script speech holds the last reliable position`() {
        val s = scenario().read(0, 30, 2.5)
        val offStart = s.durationMs
        s.say("um so let me tell you a quick story about my weekend at the lake with friends", 2.8)
        val offEnd = s.durationMs
        s.read(30, 70, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        val during = frames.filter { it.timeMs in offStart..offEnd + 300 }
        val maxDuring = during.maxOf { it.displayedProgress }
        assertTrue(maxDuring < 30 + 4.5, "drifted to $maxDuring during off-script speech\n${summary(frames)}")
        assertTrue(during.all { it.matchedIndex <= 31 }, "matched index moved during off-script speech")
        assertTrue(abs(frames.last().displayedProgress - 70) < 4.0, summary(frames))
    }

    @Test
    fun `repeated phrases never jump to another occurrence`() {
        val s = scenario().read(0, 70, 3.0)
        val frames = simulate(s)
        matchedNeverJumpsMoreThan(frames, config.smallJumpTokens)
        assertTrue(maxBackwardTravel(frames) < 1.0)
    }

    @Test
    fun `speaker starting elsewhere is located`() {
        val s = scenario().read(60, 110, 2.5)
        val frames = simulate(s, startToken = 0)
        assertNoVisualJumps(frames)
        val end = frames.last()
        assertTrue(end.matchedIndex >= 105, "matched ${end.matchedIndex}\n${summary(frames)}")
    }

    @Test
    fun `persian script is followed`() {
        val fa = TestScripts.PERSIAN
        val sc = SpeechScenario(fa, "fa")
        sc.read(0, sc.words.size, 2.2)
        val frames = SmartFollowSimulator(fa, "fa", config).run(sc.events(), sc.durationMs + 3_000)
        assertNoVisualJumps(frames)
        val tokens = ScriptIndex(fa, TextNormalizer("fa")).size
        assertTrue(frames.last().matchedIndex >= tokens - 2, "matched ${frames.last().matchedIndex}/$tokens\n${summary(frames)}")
    }

    @Test
    fun `without audio levels reading stays smooth and pauses still stop`() {
        val s = SpeechScenario(script, emitAudioLevels = false).read(0, 50, 2.5)
        val pauseStart = s.durationMs
        s.silence(4_000)
        val pauseEnd = s.durationMs
        s.read(50, 80, 2.5)
        val frames = simulate(s)
        assertNoVisualJumps(frames)
        val speaking = frames.filter { it.timeMs in 6_000..(pauseStart - 300) }
        assertTrue(speaking.count { it.scrollVelocityPx < 10.0 } < speaking.size * 0.05, summary(frames))
        val paused = frames.filter { it.timeMs in (pauseStart + 300 + config.pauseMs + 1_200)..pauseEnd }
        assertTrue(paused.all { it.state == FollowState.PAUSED && abs(it.scrollVelocityPx) < 0.5 }, summary(frames))
        assertTrue(abs(frames.last().displayedProgress - 80) < 4.0)
    }

    @Test
    fun `stop returns to idle and ignores further speech`() {
        val c = SmartFollowController(script)
        c.start(0)
        c.onPartialResult("steel enters the cutting zone", 1_000)
        assertEquals(FollowState.TRACKING, c.tick(1_010).state)
        c.stop()
        c.onPartialResult("steel enters the cutting zone and the tool removes", 2_000)
        val out = c.tick(2_010)
        assertEquals(FollowState.IDLE, out.state)
        assertEquals(0.0, out.targetVelocity)
    }

    @Test
    fun `recognition error state is explicit and recoverable`() {
        val c = SmartFollowController(script)
        c.start(0)
        c.fail("Speech recognition unavailable")
        assertEquals(FollowState.ERROR, c.tick(100).state)
        c.clearError(200)
        assertEquals(FollowState.LISTENING, c.tick(300).state)
    }
}
