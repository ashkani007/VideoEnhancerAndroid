package com.vrvision.core.stereo

/** How the two eye views are packed into one decoded video frame. */
enum class StereoLayout {
    /** One view shown to both eyes. */
    MONO,

    /** Left eye in the left half, right eye in the right half (unless swapped). */
    SIDE_BY_SIDE,

    /** Left eye in the top half, right eye in the bottom half (unless swapped). */
    TOP_BOTTOM;

    val isStereo: Boolean get() = this != MONO
}

/**
 * Whether each eye view was stored at full aspect ("full SBS/TB") or squeezed to
 * half width/height ("half SBS/TB"). Only affects the displayed aspect ratio, never
 * the texture coordinates.
 */
enum class StereoPacking { FULL, HALF }

enum class Eye { LEFT, RIGHT }

/** Axis-aligned rectangle in normalized image coordinates: (0,0) top-left, (1,1) bottom-right. */
data class UvRect(val u0: Float, val v0: Float, val u1: Float, val v1: Float) {
    val width: Float get() = u1 - u0
    val height: Float get() = v1 - v0

    /** Maps a coordinate inside this eye's view (0..1, 0..1) into full-frame coordinates. */
    fun map(u: Float, v: Float): Pair<Float, Float> = Pair(u0 + u * width, v0 + v * height)

    companion object {
        val FULL = UvRect(0f, 0f, 1f, 1f)
    }
}

object StereoMapper {

    /**
     * The region of the decoded frame that [eye] must sample.
     *
     * [swapEyes] lets the user fix files whose producer stored the right eye first;
     * it is never applied automatically.
     */
    fun eyeRect(layout: StereoLayout, eye: Eye, swapEyes: Boolean): UvRect {
        val first = (eye == Eye.LEFT) != swapEyes
        return when (layout) {
            StereoLayout.MONO -> UvRect.FULL
            StereoLayout.SIDE_BY_SIDE ->
                if (first) UvRect(0f, 0f, 0.5f, 1f) else UvRect(0.5f, 0f, 1f, 1f)
            StereoLayout.TOP_BOTTOM ->
                if (first) UvRect(0f, 0f, 1f, 0.5f) else UvRect(0f, 0.5f, 1f, 1f)
        }
    }

    /**
     * Display aspect ratio (width / height) of a single eye view.
     *
     * For HALF packing the eye view was squeezed when packed, so the original aspect is
     * restored by undoing the squeeze; FULL packing keeps the stored pixel aspect.
     */
    fun eyeAspect(
        frameWidth: Int,
        frameHeight: Int,
        layout: StereoLayout,
        packing: StereoPacking,
        pixelAspectRatio: Float = 1f,
    ): Float {
        require(frameWidth > 0 && frameHeight > 0) { "Frame size must be positive" }
        val frameAspect = frameWidth.toFloat() / frameHeight * pixelAspectRatio
        return when (layout) {
            StereoLayout.MONO -> frameAspect
            StereoLayout.SIDE_BY_SIDE ->
                if (packing == StereoPacking.FULL) frameAspect / 2f else frameAspect
            StereoLayout.TOP_BOTTOM ->
                if (packing == StereoPacking.FULL) frameAspect * 2f else frameAspect
        }
    }

    /** Pixel size of one eye view as stored in the frame. */
    fun eyePixelSize(frameWidth: Int, frameHeight: Int, layout: StereoLayout): Pair<Int, Int> =
        when (layout) {
            StereoLayout.MONO -> Pair(frameWidth, frameHeight)
            StereoLayout.SIDE_BY_SIDE -> Pair(frameWidth / 2, frameHeight)
            StereoLayout.TOP_BOTTOM -> Pair(frameWidth, frameHeight / 2)
        }
}
