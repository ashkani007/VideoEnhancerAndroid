package com.lensprompt.core

import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Smart Follow while video is being recorded with sound: recognized words may
 * stop arriving (the recorder owns the microphone) while the app's own audio
 * capture and the front camera still report whether the speaker is talking.
 */
class HybridFollowTest {

    private val config = SmartFollowConfig()
    private val frameDt = 0.016
    private val script = TestScripts.MACHINING

    private fun run(events: List<RecognitionEvent>, durationMs: Long): List<SimFrame> =
        SmartFollowSimulator(script, config = config).run(events.sortedBy { it.timeMs }, durationMs)

    private fun frameAt(frames: List<SimFrame>, t: Long) = frames.first { it.timeMs >= t }

    private fun assertSmooth(frames: List<SimFrame>) {
        val maxStep = frames.zipWithNext { a, b -> abs(b.scrollPx - a.scrollPx) }.maxOrNull() ?: 0.0
        assertTrue(maxStep <= config.maxScrollVelocityPx * frameDt + 1e-6, "visual jump $maxStep px")
        var peak = Double.NEGATIVE_INFINITY
        for (f in frames) {
            peak = maxOf(peak, f.scrollPx)
            if (peak - f.scrollPx > config.backwardDeadZonePx) fail("scrolled back ${peak - f.scrollPx} px at ${f.timeMs}")
        }
    }

    private fun summary(frames: List<SimFrame>): String = frames.filter { it.timeMs % 1000 < 16 }.joinToString("\n") {
        "%6d %-14s pace=%-5s match=%3d tgt=%6.2f disp=%6.2f v=%.2f sv=%.0f".format(
            it.timeMs, it.state, it.pacing, it.matchedIndex, it.targetProgress, it.displayedProgress, it.readingVelocity, it.scrollVelocityPx,
        )
    }

    @Test
    fun `recording starts - recognition announced unavailable - text keeps following by voice`() {
        val s = SpeechScenario(script).read(0, 100, 2.5)
        val recordAt = 10_000L
        val events = s.events().withRecognitionOutage(recordAt)
        val frames = run(events, s.durationMs + 3_000)
        assertSmooth(frames)

        val during = frames.filter { it.timeMs > recordAt + 500 }
        assertTrue(during.all { it.pacing && it.state == FollowState.PACING }, summary(frames))
        // While reading continues, the text keeps moving with the speaker.
        for (k in listOf(40, 60, 80, 95)) {
            val f = frameAt(frames, k * 400L)
            assertTrue(abs(f.displayedProgress - k) < 6.0, "word $k: display ${f.displayedProgress}\n${summary(frames)}")
        }
        val moving = frames.filter { it.timeMs in (recordAt + 2_000)..(s.durationMs - 500) }
        assertTrue(moving.count { it.scrollVelocityPx < 10 } < moving.size * 0.05, "stalled while speaking\n${summary(frames)}")
    }

    @Test
    fun `while recording, a pause stops the text and resume restarts it`() {
        val s = SpeechScenario(script).read(0, 40, 2.5)
        val pauseStart = s.durationMs
        s.silence(5_000)
        val pauseEnd = s.durationMs
        s.read(40, 80, 2.5)
        val frames = run(s.events().withRecognitionOutage(8_000), s.durationMs + 2_000)
        assertSmooth(frames)
        val paused = frames.filter { it.timeMs in (pauseStart + 1_200)..pauseEnd }
        assertTrue(paused.all { abs(it.scrollVelocityPx) < 0.5 }, "moving during pause\n${summary(frames)}")
        assertTrue(abs(paused.last().displayedProgress - 40) < 4.0, "stopped at ${paused.last().displayedProgress}")
        val after = frameAt(frames, pauseEnd + 4_000)
        assertTrue(after.scrollVelocityPx > 40, "did not resume: ${after.scrollVelocityPx}\n${summary(frames)}")
        assertTrue(abs(frames.last().displayedProgress - 80) < 6.0, summary(frames))
    }

    @Test
    fun `unannounced recognizer stall is detected and paced`() {
        val s = SpeechScenario(script).read(0, 100, 2.5)
        val outageAt = 12_000L
        // Recognition silently dies; levels keep coming (app-owned capture).
        val frames = run(s.events().withRecognitionOutage(outageAt, announce = false), s.durationMs + 2_000)
        assertSmooth(frames)
        val firstPacing = frames.firstOrNull { it.pacing }?.timeMs ?: fail("never paced\n${summary(frames)}")
        assertTrue(firstPacing - outageAt <= config.recognitionStallVoicedMs + 1_500, "stall detected after ${firstPacing - outageAt} ms")
        assertTrue(abs(frames.last().displayedProgress - 100) < 7.0, summary(frames))
    }

    @Test
    fun `recognition returning after pacing re-locks on the spoken words`() {
        val s = SpeechScenario(script).read(0, 110, 2.5)
        val frames = run(s.events().withRecognitionOutage(8_000, 24_000), s.durationMs + 2_000)
        assertSmooth(frames)
        val after = frames.filter { it.timeMs > 27_000 }
        assertTrue(after.none { it.pacing }, "still pacing after words returned\n${summary(frames)}")
        val end = frames.last()
        assertTrue(end.matchedIndex >= 105, "matched ${end.matchedIndex}\n${summary(frames)}")
        assertTrue(abs(end.displayedProgress - 110) < 4.0, summary(frames))
    }

    @Test
    fun `lip movement alone drives pacing when audio levels are unavailable`() {
        val s = SpeechScenario(script, emitAudioLevels = false).read(0, 60, 2.5)
        val events = s.events().withRecognitionOutage(6_000) + s.mouthFrames()
        val frames = run(events, s.durationMs + 2_000)
        assertSmooth(frames)
        val f = frameAt(frames, 20_000)
        assertTrue(abs(f.displayedProgress - 50) < 7.0, "display ${f.displayedProgress}\n${summary(frames)}")
    }

    @Test
    fun `voice with a still mouth only creeps - someone else is talking`() {
        val s = SpeechScenario(script).read(0, 20, 2.5)
        val readEnd = s.durationMs
        s.say("this is somebody else talking in the room for quite a while now really", 2.5)
        val events = s.events().withRecognitionOutage(readEnd + 500) +
            // speaker visible but silent: mouth closed the whole time after reading
            (0..s.durationMs step 66).map { RecognitionEvent.MouthFrame(it, if (it < readEnd) (if ((it / 66) % 2 == 0L) 0.09 else 0.02) else 0.01) }
        val frames = run(events, s.durationMs)
        val start = frameAt(frames, readEnd + 1_500).displayedProgress
        val end = frames.last().displayedProgress
        val fullSpeed = 2.5 * (s.durationMs - readEnd - 1_500) / 1000.0
        assertTrue(end - start < fullSpeed * 0.5, "moved ${end - start} tokens (full speed would be $fullSpeed)\n${summary(frames)}")
    }

    @Test
    fun `learned reading speed is kept across an audio route change`() {
        val c = SmartFollowController(script, config = config)
        c.start(0)
        val s = SpeechScenario(script).read(0, 40, 3.5)
        for (e in s.events()) when (e) {
            is RecognitionEvent.Partial -> c.onPartialResult(e.text, e.timeMs)
            is RecognitionEvent.Final -> c.onFinalResult(e.text, e.timeMs)
            is RecognitionEvent.AudioLevel -> c.onAudioLevel(e.rmsDb, e.timeMs)
            else -> Unit
        }
        val learned = c.tick(s.durationMs).readingVelocity
        assertTrue(learned > 3.0, "learned $learned")
        c.continueFrom(s.durationMs + 100, 40)
        assertEquals(learned, c.tick(s.durationMs + 200).readingVelocity, 0.2)
    }

    // ------------------------------------------------------------ components

    @Test
    fun `mouth detector distinguishes articulation from a still mouth`() {
        val d = MouthActivityDetector()
        var t = 0L
        repeat(15) { d.onFrame(if (it % 2 == 0) 0.08 else 0.02, t); t += 66 }
        assertEquals(VisualState.SPEAKING, d.state(t))
        repeat(15) { d.onFrame(0.015, t); t += 66 }
        assertEquals(VisualState.STILL, d.state(t))
        repeat(15) { d.onFrame(null, t); t += 66 }
        assertEquals(VisualState.UNKNOWN, d.state(t))
    }

    @Test
    fun `voice detector recovers when reset in the middle of speech`() {
        val v = VoiceActivityDetector()
        var t = 0L
        // reset happened while talking: first samples are speech with brief dips
        repeat(60) { k -> v.onLevel(if (k % 4 == 3) 1.5 else 7.0, t); t += 40 }
        assertEquals(VoiceState.VOICE, v.state(t))
        repeat(40) { v.onLevel(0.5, t); t += 40 }
        assertEquals(VoiceState.SILENCE, v.state(t))
        // and when reset during silence it settles to SILENCE within ~1.5 s
        val q = VoiceActivityDetector()
        t = 0
        repeat(40) { q.onLevel(-50.0, t); t += 40 }
        assertEquals(VoiceState.SILENCE, q.state(t))
    }

    @Test
    fun `fusion rules`() {
        assertEquals(0.0, SpeakingFusion.rate(VoiceState.SILENCE, VisualState.SPEAKING))
        assertEquals(1.0, SpeakingFusion.rate(VoiceState.VOICE, VisualState.SPEAKING))
        assertEquals(1.0, SpeakingFusion.rate(VoiceState.VOICE, VisualState.UNKNOWN))
        assertTrue(SpeakingFusion.rate(VoiceState.VOICE, VisualState.STILL) < 0.5)
        assertEquals(1.0, SpeakingFusion.rate(VoiceState.UNKNOWN, VisualState.SPEAKING))
        assertEquals(0.0, SpeakingFusion.rate(VoiceState.UNKNOWN, VisualState.UNKNOWN))
    }
}
