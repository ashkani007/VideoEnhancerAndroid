package com.lensprompt.core

import kotlin.math.exp

/**
 * Estimates the speaker's current reading speed, d(progress)/dt, in tokens/s.
 *
 * Samples are (time, script progress) pairs from accepted alignment
 * measurements. The raw estimate is a recency-weighted least-squares slope over
 * the last [SmartFollowConfig.velocityWindowMs], which uses every recent sample
 * instead of the last two, so a single late or bursty recognition result cannot
 * spike the speed. The slope is clamped to a plausible range and then
 * low-pass filtered (EMA) so the teleprompter never jitters.
 */
class ReadingVelocityEstimator(private val config: SmartFollowConfig) {

    private val times = LongArray(MAX_SAMPLES)
    private val values = DoubleArray(MAX_SAMPLES)
    private var count = 0
    private var head = 0 // index of the oldest sample

    /** Smoothed reading velocity in tokens/s. */
    var velocity: Double = config.defaultTokensPerSec
        private set

    /** Unsmoothed regression slope from the latest update (debug only). */
    var rawVelocity: Double = 0.0
        private set

    /** True once enough samples exist for a real (non-default) estimate. */
    var hasEstimate: Boolean = false
        private set

    fun addSample(timeMs: Long, progress: Double) {
        if (count > 0) {
            val last = (head + count - 1) % MAX_SAMPLES
            // Collapse samples that arrive within the same millisecond.
            if (times[last] == timeMs) { values[last] = progress; recompute(timeMs); return }
        }
        if (count == MAX_SAMPLES) { head = (head + 1) % MAX_SAMPLES; count-- }
        val idx = (head + count) % MAX_SAMPLES
        times[idx] = timeMs
        values[idx] = progress
        count++
        recompute(timeMs)
    }

    /**
     * Forget the sample history but keep the smoothed velocity as a prior.
     * Called after a pause (so the silent gap does not drag the slope down) and
     * after a position jump (so the jump is not read as a burst of speed).
     */
    fun resetHistory() {
        count = 0
        head = 0
    }

    /** Start from a known reading speed (e.g. learned before the audio route changed). */
    fun seed(tokensPerSec: Double) {
        resetHistory()
        velocity = tokensPerSec.coerceIn(0.0, config.maxReadingTokensPerSec)
        hasEstimate = true
    }

    fun resetAll() {
        resetHistory()
        velocity = config.defaultTokensPerSec
        rawVelocity = 0.0
        hasEstimate = false
    }

    private fun recompute(nowMs: Long) {
        // drop samples outside the window (keep at least two)
        while (count > 2 && nowMs - times[head] > config.velocityWindowMs) {
            head = (head + 1) % MAX_SAMPLES
            count--
        }
        if (count < 2) return
        val first = times[head]
        val span = nowMs - first
        if (span < MIN_SPAN_MS) return

        val tau = config.velocityWindowMs / 2.0
        var sw = 0.0; var st = 0.0; var sv = 0.0; var stt = 0.0; var stv = 0.0
        for (k in 0 until count) {
            val idx = (head + k) % MAX_SAMPLES
            val t = (times[idx] - first) / 1000.0
            val v = values[idx]
            val w = exp(-(nowMs - times[idx]) / tau)
            sw += w; st += w * t; sv += w * v; stt += w * t * t; stv += w * t * v
        }
        val denom = sw * stt - st * st
        if (denom <= 1e-9) return
        val slope = (sw * stv - st * sv) / denom
        rawVelocity = slope
        val clamped = slope.coerceIn(0.0, config.maxReadingTokensPerSec)
        velocity += config.velocitySmoothing * (clamped - velocity)
        hasEstimate = true
    }

    private companion object {
        const val MAX_SAMPLES = 64
        const val MIN_SPAN_MS = 300L
    }
}

/** Speech-activity phases derived from the time since the last real progress. */
enum class SpeechPhase { ACTIVE, SHORT_GAP, PAUSED }

/** Real-time voice presence from audio level; UNKNOWN when no levels are arriving. */
enum class VoiceState { VOICE, SILENCE, UNKNOWN }

/**
 * Voice-activity detection from the recognizer's audio level (Android
 * `onRmsChanged`). Unlike recognized words, the level has no recognition
 * latency, so it tells quickly whether the speaker is still talking.
 *
 * The threshold adapts to the room: a noise floor follows quiet levels and
 * voice is declared when the level exceeds floor + [marginDb]. A hang time
 * bridges the short gaps between words.
 */
class VoiceActivityDetector(
    private val marginDb: Double = 3.0,
    private val hangMs: Long = 350,
    private val staleMs: Long = 1_000,
) {
    private var floor = Double.NaN
    private var lastLevelMs = Long.MIN_VALUE
    var lastVoiceMs = Long.MIN_VALUE
        private set

    fun onLevel(db: Double, nowMs: Long) {
        // Minimum-statistics noise floor. Start below the first sample: after a
        // reset we may be in the middle of speech, and the floor must not learn
        // the speech level as "noise". It falls quickly on quieter input (natural
        // gaps between words) and rises slowly otherwise, so it converges on the
        // room noise whether the reset happened during speech or silence.
        if (floor.isNaN()) floor = db - INITIAL_HEADROOM_DB
        floor += if (db < floor) (db - floor) * FALL_RATE else (db - floor) * RISE_RATE
        if (db >= floor + marginDb) lastVoiceMs = nowMs
        lastLevelMs = nowMs
    }

    fun reset() {
        floor = Double.NaN
        lastLevelMs = Long.MIN_VALUE
        lastVoiceMs = Long.MIN_VALUE
    }

    /** Current noise-floor estimate (debug). */
    val noiseFloor: Double get() = floor

    fun state(nowMs: Long): VoiceState = when {
        lastLevelMs == Long.MIN_VALUE || nowMs - lastLevelMs > staleMs -> VoiceState.UNKNOWN
        lastVoiceMs != Long.MIN_VALUE && nowMs - lastVoiceMs <= hangMs -> VoiceState.VOICE
        else -> VoiceState.SILENCE
    }

    private companion object {
        const val INITIAL_HEADROOM_DB = 6.0
        const val FALL_RATE = 0.3
        const val RISE_RATE = 0.03
    }
}

/**
 * Distinguishes natural inter-word gaps from real pauses.
 *
 * Progress events (the aligned script position advancing) are the primary
 * signal. Recognizer "end of speech" and voice activity are secondary hints:
 * end of speech or measured silence shorten the pause threshold, while voice
 * keeps an ongoing utterance from being declared paused too early while
 * recognition lags.
 */
class PauseDetector(private val config: SmartFollowConfig) {

    var lastProgressMs: Long = Long.MIN_VALUE
        private set
    private var endOfSpeechMs: Long = Long.MIN_VALUE

    fun onProgress(nowMs: Long) {
        lastProgressMs = nowMs
        endOfSpeechMs = Long.MIN_VALUE
    }

    fun onEndOfSpeech(nowMs: Long) { endOfSpeechMs = nowMs }

    fun reset(nowMs: Long) {
        lastProgressMs = nowMs
        endOfSpeechMs = Long.MIN_VALUE
    }

    fun msSinceProgress(nowMs: Long): Long =
        if (lastProgressMs == Long.MIN_VALUE) Long.MAX_VALUE else nowMs - lastProgressMs

    fun phase(nowMs: Long, voice: VoiceState): SpeechPhase {
        val since = msSinceProgress(nowMs)
        val quickStop = (endOfSpeechMs != Long.MIN_VALUE && endOfSpeechMs >= lastProgressMs) ||
            voice == VoiceState.SILENCE
        val pauseMs = when {
            quickStop -> (config.pauseMs * 0.7).toLong().coerceAtLeast(config.shortGapMs + 100)
            voice == VoiceState.VOICE -> (config.pauseMs * 1.3).toLong()
            else -> config.pauseMs
        }
        return when {
            since >= pauseMs -> SpeechPhase.PAUSED
            since >= config.shortGapMs -> SpeechPhase.SHORT_GAP
            else -> SpeechPhase.ACTIVE
        }
    }
}
