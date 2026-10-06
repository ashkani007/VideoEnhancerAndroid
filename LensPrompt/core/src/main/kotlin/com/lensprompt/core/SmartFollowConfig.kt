package com.lensprompt.core

/**
 * Every Smart Follow tuning parameter lives here. Nothing else in the engine
 * hard-codes a threshold, so tuning happens in one place and tests can
 * construct deterministic variants.
 *
 * Units: times are milliseconds, positions are script tokens (words), speeds
 * are tokens per second unless the name says otherwise.
 */
data class SmartFollowConfig(
    // ---------------------------------------------------------------- alignment
    /** How many of the most recent recognized tokens form the alignment query. */
    val queryTokens: Int = 8,
    /** Script tokens searched behind the last reliable position. */
    val searchBackTokens: Int = 24,
    /** Script tokens searched ahead of the last reliable position. */
    val searchForwardTokens: Int = 60,
    /** Forward window used while alignment is lost (skips, off-script). */
    val recoverySearchForwardTokens: Int = 400,
    /** Score for a perfect token match (scaled by token informativeness). */
    val matchScore: Double = 2.0,
    /** Penalty for aligning a recognized token to a different script token. */
    val mismatchPenalty: Double = 1.0,
    /** Penalty for a recognized word that is not in the script (insertion). */
    val insertionPenalty: Double = 0.8,
    /** Penalty for a script word the speaker skipped (deletion). */
    val deletionPenalty: Double = 0.6,
    /** Minimum fuzzy similarity [0,1] for two tokens to count as a match. */
    val minTokenSimilarity: Double = 0.72,
    /** Score lost per token of distance ahead of the expected position. */
    val forwardDistancePenalty: Double = 0.035,
    /** Score lost per token of distance behind the expected position. */
    val backwardDistancePenalty: Double = 0.18,
    /** Penalty per trailing recognized token left unmatched at the query end. */
    val trailingUnmatchedPenalty: Double = 1.1,

    // --------------------------------------------------------------- confidence
    /** Below this, a measurement is ignored (position held). */
    val minConfidence: Double = 0.35,
    /** At or above this, the measurement is trusted fully. */
    val highConfidence: Double = 0.7,
    /** Minimum matched tokens needed to move more than [smallJumpTokens]. */
    val reacquireMinMatches: Int = 3,
    /** Consecutive agreeing measurements needed to accept a large jump. */
    val reacquireConfirmations: Int = 2,
    /** Two jump candidates "agree" when within this many tokens of each other. */
    val reacquireAgreementTokens: Int = 4,
    /** Moves up to this size are normal tracking, not a jump. */
    val smallJumpTokens: Int = 6,
    /** Backward moves up to this size are tolerated (speaker repeating). */
    val backtrackAllowanceTokens: Int = 3,
    /** Backward moves need at least this many matched tokens to be accepted. */
    val backtrackMinMatches: Int = 4,

    // ---------------------------------------------------------------- velocity
    /** Window of progress samples used for the velocity regression. */
    val velocityWindowMs: Long = 3_500,
    /** Exponential-moving-average factor applied to regression output. */
    val velocitySmoothing: Double = 0.35,
    /** Speeds above this are treated as recognition noise. */
    val maxReadingTokensPerSec: Double = 7.0,
    /** Initial reading speed assumption (~ 150 wpm) before samples exist. */
    val defaultTokensPerSec: Double = 2.5,
    /** Recognition latency the target position leads by (velocity * latency). */
    val recognitionLatencyMs: Long = 350,
    /** Max tokens the target may coast past the last measured position. */
    val maxCoastTokens: Double = 3.0,

    // ------------------------------------------------------------------- pause
    /** After this long without progress the speaker is in a short gap. */
    val shortGapMs: Long = 600,
    /** After this long without progress the speaker is paused. */
    val pauseMs: Long = 1_400,
    /** Without any recognized words for this long, alignment is considered lost. */
    val lostAfterMs: Long = 8_000,
    /** Consecutive rejected measurements before entering LOW_CONFIDENCE. */
    val lowConfidenceAfterRejects: Int = 3,

    // ----------------------------------------------------------------- scroll
    /** Proportional gain: how strongly position error becomes velocity (1/s). */
    val scrollGain: Double = 2.2,
    /** Max scroll acceleration, px/s^2. */
    val maxAccelerationPx: Double = 900.0,
    /** Max deceleration when stopping, px/s^2 (stopping is allowed to be firmer). */
    val maxDecelerationPx: Double = 1_600.0,
    /** Hard cap on scroll speed, px/s. */
    val maxScrollVelocityPx: Double = 900.0,
    /** Cap on the error-correction part of velocity, px/s. */
    val maxCorrectionVelocityPx: Double = 260.0,
    /** Backward errors smaller than this are ignored (no reverse scrolling), px. */
    val backwardDeadZonePx: Double = 60.0,
    /** Max reverse scroll speed when a real backward correction is needed, px/s. */
    val maxBackwardVelocityPx: Double = 140.0,

    // ------------------------------------------------------------- recognizer
    /** Delay before restarting the recognizer after a normal end of session. */
    val recognizerRestartDelayMs: Long = 120,
    /** Base back-off after a recognizer error; doubles per consecutive error. */
    val recognizerErrorBackoffMs: Long = 400,
    /** Cap for the error back-off. */
    val recognizerMaxBackoffMs: Long = 5_000,
    /** Consecutive hard errors before Smart Follow reports ERROR. */
    val recognizerMaxConsecutiveErrors: Int = 8,
) {
    companion object {
        /**
         * Builds a config from the three user-facing sliders (each 0..1, 0.5 = default).
         * Keeps the user's mental model simple while the engine keeps fine control.
         */
        fun fromUserSettings(
            responsiveness: Float,
            pauseSensitivity: Float,
            alignmentStrictness: Float,
        ): SmartFollowConfig {
            val base = SmartFollowConfig()
            val r = responsiveness.coerceIn(0f, 1f).toDouble()
            val p = pauseSensitivity.coerceIn(0f, 1f).toDouble()
            val a = alignmentStrictness.coerceIn(0f, 1f).toDouble()
            // r: 0 = calm, 1 = snappy
            val gain = lerp(1.4, 3.4, r)
            val accel = lerp(600.0, 1_400.0, r)
            val smoothing = lerp(0.2, 0.55, r)
            // p: 0 = tolerant of gaps, 1 = stops quickly
            val pause = lerp(2_200.0, 800.0, p).toLong()
            val shortGap = (pause * 0.43).toLong()
            // a: 0 = lenient fuzzy matching, 1 = strict
            val minSim = lerp(0.62, 0.84, a)
            val minConf = lerp(0.25, 0.48, a)
            return base.copy(
                scrollGain = gain,
                maxAccelerationPx = accel,
                velocitySmoothing = smoothing,
                pauseMs = pause,
                shortGapMs = shortGap,
                minTokenSimilarity = minSim,
                minConfidence = minConf,
            )
        }

        private fun lerp(a: Double, b: Double, t: Double) = a + (b - a) * t
    }
}
