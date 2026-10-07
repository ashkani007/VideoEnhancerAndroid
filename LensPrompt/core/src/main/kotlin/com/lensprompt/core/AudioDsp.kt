package com.lensprompt.core

import kotlin.math.log10
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Small, allocation-light audio helpers used by the app-owned microphone
 * pipeline during video recording. Pure Kotlin so they are unit-tested here.
 */
object AudioDsp {

    /**
     * Level of a PCM16 chunk in dB on a 0..~90 scale (20·log10 of the RMS sample
     * value). Only *relative* changes matter: the voice detector adapts its own
     * noise floor.
     */
    fun levelDb(samples: ShortArray, count: Int = samples.size): Float {
        if (count <= 0) return 0f
        var sum = 0.0
        for (i in 0 until count) {
            val v = samples[i].toDouble()
            sum += v * v
        }
        val rms = sqrt(sum / count)
        return (20.0 * log10(max(rms, 1.0))).toFloat()
    }

    /**
     * Converts mono PCM16 at [inRate] to 16 kHz (what speech recognizers expect).
     * 48 kHz input is decimated by 3 with a boxcar low-pass; other rates use
     * linear interpolation. [state] carries the fractional read position across
     * chunks so consecutive calls produce a continuous stream.
     */
    class To16k(private val inRate: Int) {
        private var pos = 0.0
        private var prev: Short = 0
        private val step = inRate / 16_000.0

        fun process(input: ShortArray, count: Int = input.size): ShortArray {
            if (inRate == 16_000) return input.copyOf(count)
            if (inRate == 48_000) {
                // Exact 3:1 decimation with averaging (cheap anti-alias filter).
                val out = ShortArray(count / 3)
                var o = 0
                var i = 0
                while (i + 2 < count && o < out.size) {
                    out[o++] = ((input[i] + input[i + 1] + input[i + 2]) / 3).toShort()
                    i += 3
                }
                return if (o == out.size) out else out.copyOf(o)
            }
            val outList = ShortArray(((count - pos) / step).toInt().coerceAtLeast(0) + 1)
            var o = 0
            while (pos < count && o < outList.size) {
                val i = pos.toInt()
                val frac = pos - i
                val a = if (i == 0) prev.toInt() else input[i - 1].toInt()
                val b = input[i].toInt()
                outList[o++] = (a + (b - a) * frac).toInt().toShort()
                pos += step
            }
            pos -= count
            if (count > 0) prev = input[count - 1]
            return if (o == outList.size) outList else outList.copyOf(o)
        }
    }

    /**
     * Where the app-recorded audio sits on the video's timeline.
     *
     * @param audioStartNanos monotonic time of the first captured audio frame.
     * @param videoStartNanos monotonic time of the first video frame.
     * @return audio frames to drop from the start (when audio started first) and
     *   the presentation offset of the first kept frame (when video started first).
     */
    fun alignAudioToVideo(audioStartNanos: Long, videoStartNanos: Long, sampleRate: Int): AudioAlignment {
        val deltaNanos = videoStartNanos - audioStartNanos
        return if (deltaNanos >= 0) {
            AudioAlignment(skipFrames = deltaNanos * sampleRate / 1_000_000_000L, startOffsetUs = 0)
        } else {
            AudioAlignment(skipFrames = 0, startOffsetUs = -deltaNanos / 1_000)
        }
    }

    /**
     * Best estimate of when the first video frame was captured, from recorder
     * status callbacks: each callback at time t reports d nanoseconds recorded, so
     * the start is t − d. Callback delivery is only ever late, never early, so
     * the minimum over all callbacks is the tightest estimate.
     */
    class VideoStartEstimator {
        var estimateNanos: Long = Long.MAX_VALUE
            private set

        fun onStatus(callbackNanos: Long, recordedDurationNanos: Long) {
            if (recordedDurationNanos <= 0) return
            val start = callbackNanos - recordedDurationNanos
            if (start < estimateNanos) estimateNanos = start
        }

        fun onStarted(callbackNanos: Long) {
            if (callbackNanos < estimateNanos) estimateNanos = callbackNanos
        }

        val hasEstimate: Boolean get() = estimateNanos != Long.MAX_VALUE
    }
}

data class AudioAlignment(val skipFrames: Long, val startOffsetUs: Long)
