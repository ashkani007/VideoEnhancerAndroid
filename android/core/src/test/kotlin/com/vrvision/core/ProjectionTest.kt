package com.vrvision.core

import com.vrvision.core.math.Vec3
import com.vrvision.core.projection.FlatScreenConfig
import com.vrvision.core.projection.MeshFactory
import com.vrvision.core.projection.ProjectionType
import kotlin.math.atan2
import kotlin.math.sqrt
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ProjectionTest {

    private fun vertex(m: com.vrvision.core.projection.Mesh, i: Int) =
        Vec3(m.positions[i * 3], m.positions[i * 3 + 1], m.positions[i * 3 + 2])

    /** Finds the vertex whose uv is closest to (u, v). */
    private fun vertexAt(m: com.vrvision.core.projection.Mesh, u: Float, v: Float): Vec3 {
        var best = 0; var bestD = Float.MAX_VALUE
        for (i in 0 until m.vertexCount) {
            val du = m.uvs[i * 2] - u; val dv = m.uvs[i * 2 + 1] - v
            val d = du * du + dv * dv
            if (d < bestD) { bestD = d; best = i }
        }
        return vertex(m, best)
    }

    @Test fun flatQuadKeepsAspectAndDistance() {
        val m = MeshFactory.build(ProjectionType.FLAT, 16f / 9f, FlatScreenConfig(distanceMeters = 3f, screenWidthMeters = 4f))
        assertEquals(4, m.vertexCount)
        val tl = vertexAt(m, 0f, 0f); val br = vertexAt(m, 1f, 1f)
        val w = br.x - tl.x; val h = tl.y - br.y
        assertEquals(4f, w, 1e-5f)
        assertEquals(16f / 9f, w / h, 1e-4f)
        assertEquals(-3f, tl.z, 1e-6f)
        // Image top (v = 0) is up, image left (u = 0) is left.
        assertTrue(tl.y > 0 && tl.x < 0)
    }

    @Test fun flatConfigIsClamped() {
        val c = FlatScreenConfig(distanceMeters = 0.1f, screenWidthMeters = 100f).validated()
        assertEquals(FlatScreenConfig.MIN_DISTANCE, c.distanceMeters)
        assertEquals(FlatScreenConfig.MAX_WIDTH, c.screenWidthMeters)
    }

    @Test fun sphereImageCenterIsStraightAhead() {
        for (type in listOf(ProjectionType.EQUIRECT_180, ProjectionType.EQUIRECT_360)) {
            val m = MeshFactory.build(type, 1f)
            val c = vertexAt(m, 0.5f, 0.5f).normalized()
            assertTrue(c.approx(Vec3(0f, 0f, -1f), 1e-3f), "center of $type is $c")
            // Top of image is straight up.
            assertTrue(vertexAt(m, 0.5f, 0f).normalized().approx(Vec3(0f, 1f, 0f), 1e-3f))
        }
    }

    @Test fun vr180SpansExactlyMinus90To90Degrees() {
        val m = MeshFactory.build(ProjectionType.EQUIRECT_180, 1f)
        val left = vertexAt(m, 0f, 0.5f); val right = vertexAt(m, 1f, 0.5f)
        assertEquals(-90.0, Math.toDegrees(atan2(left.x.toDouble(), -left.z.toDouble())), 0.01)
        assertEquals(90.0, Math.toDegrees(atan2(right.x.toDouble(), -right.z.toDouble())), 0.01)
        // u increasing goes to the viewer's right (no mirroring).
        val q = vertexAt(m, 0.75f, 0.5f)
        assertTrue(q.x > 0f)
    }

    @Test fun vr360SeamIsBehindViewer() {
        val m = MeshFactory.build(ProjectionType.EQUIRECT_360, 1f)
        val l = vertexAt(m, 0f, 0.5f).normalized(); val r = vertexAt(m, 1f, 0.5f).normalized()
        assertTrue(l.approx(Vec3(0f, 0f, 1f), 1e-3f))
        assertTrue(r.approx(Vec3(0f, 0f, 1f), 1e-3f))
        // A quarter to the right of center is 90° to the right.
        assertTrue(vertexAt(m, 0.75f, 0.5f).normalized().approx(Vec3(1f, 0f, 0f), 1e-3f))
    }

    @Test fun sphereVerticesLieOnRadiusAndIndicesInRange() {
        val m = MeshFactory.build(ProjectionType.EQUIRECT_360, 1f, radius = 7f, rings = 10, segments = 20)
        for (i in 0 until m.vertexCount) {
            val v = vertex(m, i)
            assertEquals(7f, sqrt(v.dot(v)), 1e-3f)
        }
        assertTrue(m.indices.all { it in 0 until m.vertexCount })
        assertEquals(10 * 20 * 6, m.indices.size)
    }
}
