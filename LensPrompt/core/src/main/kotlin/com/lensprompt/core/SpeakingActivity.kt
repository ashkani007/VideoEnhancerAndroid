package com.lensprompt.core

import kotlin.math.max
import kotlin.math.min

/** Whether the speaker's mouth is visibly moving. UNKNOWN when no face is tracked. */
enum class VisualState { SPEAKING, STILL, UNKNOWN }

/**
 * Detects talking from lip movement.
 *
 * Input per camera frame: mouth openness, i.e. the gap between the inner lips
 * divided by the face height (so it does not depend on distance to the
 * camera), or null when no face was found. Speech makes the openness oscillate;
 * a closed or held-open mouth does not. We therefore look at the *range* of
 * openness over a short window rather than its absolute value.
 */
class MouthActivityDetector(
    private val windowMs: Long = 700,
    /** Openness range within the window that counts as articulation. */
    private val minRange: Double = 0.03,
    /** Frames needed in the window before deciding. */
    private val minFrames: Int = 4,
    /** No face for this long → UNKNOWN. */
    private val staleMs: Long = 600,
) {
    private val times = LongArray(CAPACITY)
    private val values = DoubleArray(CAPACITY)
    private var head = 0
    private var count = 0
    private var lastFaceMs = Long.MIN_VALUE

    /** Latest openness range (debug display). */
    var lastRange: Double = 0.0
        private set

    fun onFrame(openness: Double?, nowMs: Long) {
        if (openness == null || openness.isNaN()) return
        lastFaceMs = nowMs
        if (count == CAPACITY) { head = (head + 1) % CAPACITY; count-- }
        val idx = (head + count) % CAPACITY
        times[idx] = nowMs
        values[idx] = openness
        count++
    }

    fun reset() {
        head = 0
        count = 0
        lastFaceMs = Long.MIN_VALUE
        lastRange = 0.0
    }

    fun state(nowMs: Long): VisualState {
        if (lastFaceMs == Long.MIN_VALUE || nowMs - lastFaceMs > staleMs) return VisualState.UNKNOWN
        while (count > 0 && nowMs - times[head] > windowMs) {
            head = (head + 1) % CAPACITY
            count--
        }
        if (count < minFrames) return VisualState.UNKNOWN
        var lo = Double.MAX_VALUE
        var hi = -Double.MAX_VALUE
        for (k in 0 until count) {
            val v = values[(head + k) % CAPACITY]
            lo = min(lo, v)
            hi = max(hi, v)
        }
        lastRange = hi - lo
        return if (lastRange >= minRange) VisualState.SPEAKING else VisualState.STILL
    }

    private companion object { const val CAPACITY = 64 }
}

/**
 * Fuses audio voice activity and visual lip activity into a pacing rate
 * (fraction of the reading speed, 0..1) for when words cannot be recognized.
 *
 * Audio is the primary signal: no voice means the speaker is not reading
 * aloud, whatever the lips do. Lips disambiguate *who* is talking: voice with
 * a still mouth is probably someone else or background noise, so the text
 * only creeps. Without audio information, visible articulation alone drives it.
 */
object SpeakingFusion {
    const val VOICE_STILL_MOUTH_RATE = 0.35

    fun rate(voice: VoiceState, visual: VisualState): Double = when (voice) {
        VoiceState.SILENCE -> 0.0
        VoiceState.VOICE -> when (visual) {
            VisualState.SPEAKING, VisualState.UNKNOWN -> 1.0
            VisualState.STILL -> VOICE_STILL_MOUTH_RATE
        }
        VoiceState.UNKNOWN -> if (visual == VisualState.SPEAKING) 1.0 else 0.0
    }
}
