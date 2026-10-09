package com.vrvision.core.calibration

/**
 * Software calibration for a passive phone VR headset.
 *
 * Physical IPD is set by the headset's lens spacing (or its IPD slider); software can only
 * move each eye's image on the screen so its center lines up with the lens center
 * ([lensSeparationMm]) and fine-tune each eye ([leftCenterOffsetX] etc.). It cannot change
 * the optical distance between the lenses.
 *
 * Offsets are in normalized eye-viewport units (1.0 = full viewport width/height).
 */
data class HeadsetCalibration(
    val id: Long = 0,
    val name: String = "Default headset",
    /** Distance between the two lens centers, used to place each eye's image on screen. */
    val lensSeparationMm: Float = 63.5f,
    /** Distance from the lens centers to the bottom edge of the phone screen; 0 = vertically centered. */
    val lensToBottomMm: Float = 0f,
    val distortionEnabled: Boolean = true,
    /** Radial barrel pre-distortion coefficients compensating the lens pincushion. */
    val k1: Float = 0.22f,
    val k2: Float = 0.10f,
    val leftCenterOffsetX: Float = 0f,
    val leftCenterOffsetY: Float = 0f,
    val rightCenterOffsetX: Float = 0f,
    val rightCenterOffsetY: Float = 0f,
    /** Shifts the image content (not the optical center), e.g. to fix vertical misalignment. */
    val imageOffsetX: Float = 0f,
    val imageOffsetY: Float = 0f,
    val zoom: Float = 1.0f,
    /** Vertical field of view of each virtual eye camera, degrees. */
    val fovDegrees: Float = 90f,
    /** Extra black margin around each eye viewport (normalized), useful against lens edge blur. */
    val viewportMargin: Float = 0f,
) {
    /** Returns a copy with every value clamped to its safe range. */
    fun validated(): HeadsetCalibration = copy(
        name = name.trim().take(MAX_NAME).ifEmpty { "Headset" },
        lensSeparationMm = lensSeparationMm.coerceIn(Limits.LENS_SEPARATION_MM),
        lensToBottomMm = lensToBottomMm.coerceIn(Limits.LENS_TO_BOTTOM_MM),
        k1 = k1.coerceIn(Limits.K1),
        k2 = k2.coerceIn(Limits.K2),
        leftCenterOffsetX = leftCenterOffsetX.coerceIn(Limits.CENTER_OFFSET),
        leftCenterOffsetY = leftCenterOffsetY.coerceIn(Limits.CENTER_OFFSET),
        rightCenterOffsetX = rightCenterOffsetX.coerceIn(Limits.CENTER_OFFSET),
        rightCenterOffsetY = rightCenterOffsetY.coerceIn(Limits.CENTER_OFFSET),
        imageOffsetX = imageOffsetX.coerceIn(Limits.IMAGE_OFFSET),
        imageOffsetY = imageOffsetY.coerceIn(Limits.IMAGE_OFFSET),
        zoom = zoom.coerceIn(Limits.ZOOM),
        fovDegrees = fovDegrees.coerceIn(Limits.FOV_DEG),
        viewportMargin = viewportMargin.coerceIn(Limits.VIEWPORT_MARGIN),
    )

    val isValid: Boolean get() = this == validated()

    object Limits {
        val LENS_SEPARATION_MM = 50f..75f
        val LENS_TO_BOTTOM_MM = 0f..60f
        val K1 = -0.10f..0.60f
        val K2 = -0.10f..0.40f
        val CENTER_OFFSET = -0.15f..0.15f
        val IMAGE_OFFSET = -0.25f..0.25f
        val ZOOM = 0.5f..2.0f
        val FOV_DEG = 60f..120f
        val VIEWPORT_MARGIN = 0f..0.2f
    }

    companion object {
        const val MAX_NAME = 40
    }
}

/**
 * Where each eye's viewport and optical center are on the physical screen.
 * All values are in pixels of the landscape surface; origin at top-left.
 */
data class EyeViewport(
    val x: Int,
    val y: Int,
    val width: Int,
    val height: Int,
    /** Optical center in viewport-normalized coordinates (0..1, top-left origin). */
    val centerU: Float,
    val centerV: Float,
)

object ViewportLayout {

    /**
     * Splits a landscape surface into two eye viewports and places each lens center.
     *
     * @param surfaceWidthPx landscape surface width in pixels (after display cutout insets).
     * @param xdpi physical horizontal pixel density; used to convert lens separation to pixels.
     */
    fun compute(
        surfaceWidthPx: Int,
        surfaceHeightPx: Int,
        xdpi: Float,
        ydpi: Float,
        calibration: HeadsetCalibration,
        horizontalInsetPx: Int = 0,
    ): Pair<EyeViewport, EyeViewport> {
        require(surfaceWidthPx > 1 && surfaceHeightPx > 0) { "Surface too small" }
        require(horizontalInsetPx >= 0 && horizontalInsetPx * 2 < surfaceWidthPx - 1) { "Inset too large" }
        val cal = calibration.validated()
        val halfW = surfaceWidthPx / 2
        val inset = horizontalInsetPx
        val pxPerMmX = if (xdpi > 0f) xdpi / MM_PER_INCH else 0f
        val pxPerMmY = if (ydpi > 0f) ydpi / MM_PER_INCH else 0f

        // Lens centers are symmetric about the screen center.
        val sepPx = cal.lensSeparationMm * pxPerMmX
        val leftLensX = if (pxPerMmX > 0f) surfaceWidthPx / 2f - sepPx / 2f else halfW / 2f
        val rightLensX = if (pxPerMmX > 0f) surfaceWidthPx / 2f + sepPx / 2f else halfW + halfW / 2f
        val lensY = if (cal.lensToBottomMm > 0f && pxPerMmY > 0f) {
            (surfaceHeightPx - cal.lensToBottomMm * pxPerMmY).coerceIn(0f, surfaceHeightPx.toFloat())
        } else surfaceHeightPx / 2f

        // A symmetric inset (camera cutout on one edge) shrinks both viewports from the outer
        // edges only, so the screen center — and therefore the lens geometry — is unchanged.
        val leftW = halfW - inset
        val rightW = surfaceWidthPx - halfW - inset
        val left = EyeViewport(
            x = inset, y = 0, width = leftW, height = surfaceHeightPx,
            centerU = ((leftLensX - inset) / leftW + cal.leftCenterOffsetX).coerceIn(0f, 1f),
            centerV = (lensY / surfaceHeightPx + cal.leftCenterOffsetY).coerceIn(0f, 1f),
        )
        val right = EyeViewport(
            x = halfW, y = 0, width = rightW, height = surfaceHeightPx,
            centerU = ((rightLensX - halfW) / rightW + cal.rightCenterOffsetX).coerceIn(0f, 1f),
            centerV = (lensY / surfaceHeightPx + cal.rightCenterOffsetY).coerceIn(0f, 1f),
        )
        return Pair(left, right)
    }

    private const val MM_PER_INCH = 25.4f
}

/**
 * Radial pre-distortion applied in the second render pass. Mirrors the GLSL in
 * the app's distortion shader so it can be unit tested.
 */
object DistortionModel {

    /**
     * For an output pixel at viewport coordinate (u, v), returns the coordinate to sample
     * in the undistorted eye image. Distances are measured with the viewport [aspect]
     * (width / height) so the distortion is circular on the physical screen.
     * Returns null when the sample falls outside the eye image (render black).
     */
    fun sourceCoord(
        u: Float,
        v: Float,
        centerU: Float,
        centerV: Float,
        aspect: Float,
        k1: Float,
        k2: Float,
    ): Pair<Float, Float>? {
        val dx = (u - centerU) * aspect
        val dy = v - centerV
        val r2 = dx * dx + dy * dy
        val scale = 1f + k1 * r2 + k2 * r2 * r2
        val su = centerU + (u - centerU) * scale
        val sv = centerV + (v - centerV) * scale
        return if (su < 0f || su > 1f || sv < 0f || sv > 1f) null else Pair(su, sv)
    }
}
