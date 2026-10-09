package com.vrvision.core.projection

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

enum class ProjectionType {
    /** Flat virtual cinema screen in front of the viewer. */
    FLAT,

    /** Equirectangular half sphere: 180° horizontal, 180° vertical, facing forward. */
    EQUIRECT_180,

    /** Equirectangular full sphere: 360° horizontal, 180° vertical. */
    EQUIRECT_360;

    val isSpherical: Boolean get() = this != FLAT

    /** Horizontal angular coverage in degrees. */
    val horizontalCoverageDeg: Float
        get() = when (this) {
            FLAT -> 0f
            EQUIRECT_180 -> 180f
            EQUIRECT_360 -> 360f
        }
}

/**
 * Flat-screen parameters (only used for [ProjectionType.FLAT]).
 * The screen keeps the video aspect ratio; [screenWidthMeters] sets its size.
 */
data class FlatScreenConfig(
    val distanceMeters: Float = 3.0f,
    val screenWidthMeters: Float = 4.0f,
) {
    fun validated(): FlatScreenConfig = FlatScreenConfig(
        distanceMeters = distanceMeters.coerceIn(MIN_DISTANCE, MAX_DISTANCE),
        screenWidthMeters = screenWidthMeters.coerceIn(MIN_WIDTH, MAX_WIDTH),
    )

    companion object {
        const val MIN_DISTANCE = 1.0f
        const val MAX_DISTANCE = 20.0f
        const val MIN_WIDTH = 0.5f
        const val MAX_WIDTH = 30.0f
    }
}

/**
 * Interleaved mesh in OpenGL world space: Y up, -Z forward, X right.
 * [positions] holds xyz triples, [uvs] holds image-space uv pairs where (0,0) is the
 * top-left of the eye view and v grows downwards (matching decoded video).
 */
class Mesh(val positions: FloatArray, val uvs: FloatArray, val indices: ShortArray) {
    val vertexCount: Int get() = positions.size / 3
}

object MeshFactory {

    /**
     * Builds the mesh for a projection. For spheres the viewer sits at the origin and
     * triangles face inwards. Longitude 0 (image center column) maps to -Z (forward).
     */
    fun build(
        type: ProjectionType,
        eyeAspect: Float,
        flat: FlatScreenConfig = FlatScreenConfig(),
        radius: Float = 10f,
        rings: Int = 48,
        segments: Int = 96,
    ): Mesh = when (type) {
        ProjectionType.FLAT -> flatQuad(eyeAspect, flat.validated())
        ProjectionType.EQUIRECT_180 -> sphere(radius, rings, segments, PI)
        ProjectionType.EQUIRECT_360 -> sphere(radius, rings, segments, 2 * PI)
    }

    private fun flatQuad(eyeAspect: Float, cfg: FlatScreenConfig): Mesh {
        require(eyeAspect > 0f) { "Aspect must be positive" }
        val halfW = cfg.screenWidthMeters / 2f
        val halfH = halfW / eyeAspect
        val z = -cfg.distanceMeters
        val positions = floatArrayOf(
            -halfW, halfH, z, // top-left
            halfW, halfH, z, // top-right
            -halfW, -halfH, z, // bottom-left
            halfW, -halfH, z, // bottom-right
        )
        val uvs = floatArrayOf(0f, 0f, 1f, 0f, 0f, 1f, 1f, 1f)
        val indices = shortArrayOf(0, 2, 1, 1, 2, 3)
        return Mesh(positions, uvs, indices)
    }

    /**
     * Sphere segment spanning [lonSpan] radians of longitude centered on forward and
     * the full ±90° latitude range.
     */
    private fun sphere(radius: Float, rings: Int, segments: Int, lonSpan: Double): Mesh {
        require(rings >= 2 && segments >= 3) { "Mesh too coarse" }
        require((rings + 1) * (segments + 1) <= Short.MAX_VALUE) { "Mesh too dense for 16-bit indices" }
        val vertexCount = (rings + 1) * (segments + 1)
        val positions = FloatArray(vertexCount * 3)
        val uvs = FloatArray(vertexCount * 2)
        var p = 0
        var t = 0
        for (r in 0..rings) {
            val v = r.toFloat() / rings
            val lat = PI / 2 - v * PI // +90° (top) .. -90° (bottom)
            for (s in 0..segments) {
                val u = s.toFloat() / segments
                val lon = (u - 0.5) * lonSpan // 0 at image center
                positions[p++] = (radius * cos(lat) * sin(lon)).toFloat()
                positions[p++] = (radius * sin(lat)).toFloat()
                positions[p++] = (-radius * cos(lat) * cos(lon)).toFloat()
                uvs[t++] = u
                uvs[t++] = v
            }
        }
        val indices = ShortArray(rings * segments * 6)
        var i = 0
        for (r in 0 until rings) {
            for (s in 0 until segments) {
                val a = (r * (segments + 1) + s).toShort()
                val b = (a + segments + 1).toShort()
                // Wound to face the center (viewer inside the sphere).
                indices[i++] = a; indices[i++] = (a + 1).toShort(); indices[i++] = b
                indices[i++] = b; indices[i++] = (a + 1).toShort(); indices[i++] = (b + 1).toShort()
            }
        }
        return Mesh(positions, uvs, indices)
    }
}
