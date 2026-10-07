package com.lensprompt.core

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * Turns discrete position estimates into continuous, camera-like motion.
 *
 * State is (position, velocity) in pixels. Every frame:
 *   desiredVelocity = feedForward (reading speed in px/s) + correction(error)
 * and the actual velocity moves toward it under acceleration/deceleration
 * limits. Position only ever changes by velocity * dt, so the text cannot
 * jump, however the target moves. Small backward errors are ignored (a
 * teleprompter should not reverse when the speaker repeats a word); real
 * backward corrections are allowed slowly.
 */
class TeleprompterScrollController(private var config: SmartFollowConfig = SmartFollowConfig()) {

    /** Scroll offset in px: content y currently placed at the reading anchor. */
    var position: Double = 0.0
        private set

    /** Current scroll speed, px/s. */
    var velocity: Double = 0.0
        private set

    fun updateConfig(newConfig: SmartFollowConfig) { config = newConfig }

    /** Hard reposition (user dragged the text, reset to start). Not used while following. */
    fun snapTo(px: Double) {
        position = px
        velocity = 0.0
    }

    /**
     * Follow a moving target.
     * @param dtSec frame time in seconds.
     * @param targetPx desired scroll offset.
     * @param feedForwardPx velocity the target itself moves at, px/s.
     */
    fun follow(dtSec: Double, targetPx: Double, feedForwardPx: Double): Double {
        val dt = dtSec.coerceIn(0.0, 0.1)
        if (dt == 0.0) return position
        val error = targetPx - position

        val correction = if (error >= 0) {
            // Large errors (after a skip) may glide faster than normal corrections.
            val cap = config.maxCorrectionVelocityPx + max(0.0, error - LARGE_ERROR_PX) * 1.5
            min(config.scrollGain * error, cap)
        } else {
            val beyond = -error - config.backwardDeadZonePx
            if (beyond <= 0) 0.0 else -min(config.scrollGain * beyond, config.maxBackwardVelocityPx)
        }

        var desired = max(0.0, feedForwardPx) + correction
        // Do not run past the target when it has stopped.
        if (feedForwardPx <= 0.0 && error <= 0.0 && desired > 0.0) desired = 0.0
        desired = desired.coerceIn(-config.maxBackwardVelocityPx, config.maxScrollVelocityPx)
        return integrate(dt, desired)
    }

    /** Constant-speed scrolling for manual mode (speed 0 = smooth stop). */
    fun cruise(dtSec: Double, speedPx: Double): Double {
        val dt = dtSec.coerceIn(0.0, 0.1)
        if (dt == 0.0) return position
        return integrate(dt, speedPx.coerceIn(-config.maxScrollVelocityPx, config.maxScrollVelocityPx))
    }

    private fun integrate(dt: Double, desired: Double): Double {
        val dv = desired - velocity
        val slowingDown = abs(desired) < abs(velocity) || desired * velocity < 0
        val limit = (if (slowingDown) config.maxDecelerationPx else config.maxAccelerationPx) * dt
        velocity += dv.coerceIn(-limit, limit)
        if (abs(velocity) < STOP_EPSILON && abs(desired) < STOP_EPSILON) velocity = 0.0
        position += velocity * dt
        return position
    }

    private companion object {
        const val LARGE_ERROR_PX = 400.0
        const val STOP_EPSILON = 0.5
    }
}

/**
 * Maps fractional script progress (tokens) to content y (px) and back.
 *
 * [tokenY] holds a y for each token that already interpolates *within* a line
 * (a token half way along a line sits half way to the next line). That makes
 * y(progress) continuous and monotonic, so steady reading produces steady
 * scrolling instead of a line-by-line staircase.
 */
class ProgressMapper(private val tokenY: FloatArray, private val endY: Float) {

    val size: Int get() = tokenY.size

    fun yAt(progress: Double): Double {
        if (tokenY.isEmpty()) return 0.0
        if (progress <= 0.0) return tokenY[0].toDouble()
        val i = progress.toInt()
        if (i >= tokenY.size) return endY.toDouble()
        val y0 = tokenY[i].toDouble()
        val y1 = if (i + 1 < tokenY.size) tokenY[i + 1].toDouble() else endY.toDouble()
        return y0 + (y1 - y0) * (progress - i)
    }

    /** Pixels per token around [progress]; converts token velocity to px velocity. */
    fun pxPerToken(progress: Double): Double {
        if (tokenY.size < 2) return 0.0
        // Average over a few tokens so line breaks do not cause speed spikes.
        val lo = (progress - 3).coerceAtLeast(0.0)
        val hi = (progress + 3).coerceAtMost(tokenY.size.toDouble())
        if (hi <= lo) return 0.0
        return (yAt(hi) - yAt(lo)) / (hi - lo)
    }

    /** Inverse of [yAt]; used when the user scrolls by hand before starting. */
    fun progressAt(y: Double): Double {
        if (tokenY.isEmpty()) return 0.0
        if (y <= tokenY[0]) return 0.0
        if (y >= endY) return tokenY.size.toDouble()
        var lo = 0
        var hi = tokenY.size - 1
        while (lo < hi) {
            val mid = (lo + hi + 1) ushr 1
            if (tokenY[mid] <= y) lo = mid else hi = mid - 1
        }
        val y0 = tokenY[lo]
        val y1 = if (lo + 1 < tokenY.size) tokenY[lo + 1] else endY
        val f = if (y1 > y0) (y - y0) / (y1 - y0) else 0.0
        return lo + f.coerceIn(0.0, 1.0)
    }

    companion object {
        /** Uniform mapping for tests and the simulator. */
        fun uniform(tokens: Int, pxPerToken: Float): ProgressMapper =
            ProgressMapper(FloatArray(tokens) { it * pxPerToken }, tokens * pxPerToken)
    }
}
