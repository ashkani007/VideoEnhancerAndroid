package com.vrvision.core.enhance

import com.vrvision.core.stereo.StereoLayout

/** Integer rectangle, [x, x+w) × [y, y+h). */
data class Rect(val x: Int, val y: Int, val w: Int, val h: Int) {
    val right: Int get() = x + w
    val bottom: Int get() = y + h
    val area: Long get() = w.toLong() * h
}

/**
 * One inference window. The model always sees a [window]-sized input (fixed tensor shape,
 * replicate-padded when the region is smaller); only [core] — the part far enough from
 * the window border to be free of edge artifacts — is written to the output.
 */
data class Tile(val region: Rect, val window: Rect, val core: Rect)

object TilePlanner {

    /**
     * Regions processed independently. For stereo frames each eye is its own region, so a
     * convolution near the seam never mixes the two eyes (which would create inconsistent
     * features between eyes). Mono frames are one region.
     */
    fun regions(width: Int, height: Int, layout: StereoLayout): List<Rect> = when (layout) {
        StereoLayout.MONO -> listOf(Rect(0, 0, width, height))
        StereoLayout.SIDE_BY_SIDE -> listOf(Rect(0, 0, width / 2, height), Rect(width / 2, 0, width - width / 2, height))
        StereoLayout.TOP_BOTTOM -> listOf(Rect(0, 0, width, height / 2), Rect(0, height / 2, width, height - height / 2))
    }

    fun tiles(width: Int, height: Int, layout: StereoLayout, window: Int, overlap: Int): List<Tile> {
        require(window > 2 * overlap && overlap >= 0) { "Window must exceed twice the overlap" }
        return regions(width, height, layout).flatMap { r ->
            val xs = axis(r.w, window, overlap)
            val ys = axis(r.h, window, overlap)
            ys.flatMap { (wy, cy) ->
                xs.map { (wx, cx) ->
                    Tile(
                        region = r,
                        window = Rect(r.x + wx.first, r.y + wy.first, window, window),
                        core = Rect(r.x + cx.first, r.y + cy.first, cx.last - cx.first, cy.last - cy.first),
                    )
                }
            }
        }
    }

    /**
     * Splits [0, length) into window starts and core intervals (as first..endExclusive pairs).
     * Cores partition the axis exactly; interior core edges sit at the middle of each overlap.
     */
    internal fun axis(length: Int, window: Int, overlap: Int): List<Pair<IntRange, IntRange>> {
        if (length <= window) return listOf(0..window to 0..length)
        val stride = window - 2 * overlap
        val starts = mutableListOf<Int>()
        var s = 0
        while (s + window < length) { starts += s; s += stride }
        starts += length - window
        val bounds = IntArray(starts.size + 1)
        bounds[0] = 0
        bounds[starts.size] = length
        for (i in 0 until starts.size - 1) bounds[i + 1] = (starts[i + 1] + starts[i] + window) / 2
        return starts.mapIndexed { i, st -> (st..st + window) to (bounds[i]..bounds[i + 1]) }
    }
}

/** Default 10-second preview segment selection. */
object PreviewSegment {
    const val DEFAULT_LENGTH_MS = 10_000L

    /** Starts a third of the way in (skipping typical intros), clamped to fit. */
    fun suggestedStart(durationMs: Long, lengthMs: Long = DEFAULT_LENGTH_MS): Long =
        clampStart(durationMs / 3, durationMs, lengthMs)

    fun clampStart(startMs: Long, durationMs: Long, lengthMs: Long = DEFAULT_LENGTH_MS): Long =
        startMs.coerceIn(0, (durationMs - lengthMs).coerceAtLeast(0))

    fun length(durationMs: Long, lengthMs: Long = DEFAULT_LENGTH_MS): Long = minOf(lengthMs, durationMs.coerceAtLeast(0))
}
