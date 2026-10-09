package com.vrvision.core

import com.vrvision.core.calibration.CalibrationCodec
import com.vrvision.core.calibration.CalibrationStore
import com.vrvision.core.calibration.DistortionModel
import com.vrvision.core.calibration.HeadsetCalibration
import com.vrvision.core.calibration.ProfileManager
import com.vrvision.core.calibration.ViewportLayout
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class InMemoryStore : CalibrationStore {
    val rows = LinkedHashMap<Long, HeadsetCalibration>()
    var active: Long? = null
    private var nextId = 1L
    override suspend fun all() = rows.values.toList()
    override suspend fun upsert(profile: HeadsetCalibration): Long {
        val id = if (profile.id == 0L) nextId++ else profile.id
        rows[id] = profile.copy(id = id); return id
    }
    override suspend fun delete(id: Long) { rows.remove(id) }
    override suspend fun activeId() = active
    override suspend fun setActiveId(id: Long) { active = id }
}

class CalibrationTest {

    @Test fun valuesAreClampedToSafeLimits() {
        val c = HeadsetCalibration(k1 = 5f, zoom = 10f, fovDegrees = 10f, lensSeparationMm = 100f, leftCenterOffsetX = -1f).validated()
        assertEquals(0.60f, c.k1)
        assertEquals(2.0f, c.zoom)
        assertEquals(60f, c.fovDegrees)
        assertEquals(75f, c.lensSeparationMm)
        assertEquals(-0.15f, c.leftCenterOffsetX)
        assertTrue(HeadsetCalibration().isValid)
    }

    @Test fun codecRoundTrip() {
        val c = HeadsetCalibration(name = "Bobo \"VR\" Z6\n", k1 = 0.31f, k2 = 0.05f, rightCenterOffsetY = 0.02f, zoom = 1.2f, distortionEnabled = false)
        val back = CalibrationCodec.decode(CalibrationCodec.encode(c))
        assertEquals(c.validated().copy(id = 0), back)
    }

    @Test fun codecClampsHostileInputAndRejectsGarbage() {
        val c = CalibrationCodec.decode("""{"format":1,"name":"x","k1":99,"zoom":-4,"unknown":"ignored"}""")
        assertEquals(0.6f, c.k1); assertEquals(0.5f, c.zoom)
        assertFailsWith<IllegalArgumentException> { CalibrationCodec.decode("""{"format":2}""") }
        assertFailsWith<IllegalArgumentException> { CalibrationCodec.decode("""{"format":1,"k1":{}}""") }
        assertFailsWith<IllegalArgumentException> { CalibrationCodec.decode("not json") }
    }

    @Test fun profilesPersistAndAlwaysHaveOneActive() = runBlocking {
        val store = InMemoryStore()
        val pm = ProfileManager(store)
        val def = pm.active()
        assertEquals(1, store.rows.size)
        val bobo = pm.createFrom(def.copy(k1 = 0.3f), "Bobo")
        pm.select(bobo.id)
        assertEquals(0.3f, pm.active().k1)

        // A new manager over the same store (app restart) sees the same state.
        val pm2 = ProfileManager(store)
        assertEquals(bobo.id, pm2.active().id)
        assertEquals(2, pm2.profiles().size)

        // Deleting the active profile falls back to another one.
        assertTrue(pm2.delete(bobo.id))
        assertEquals(def.id, pm2.active().id)
        // The last profile cannot be deleted.
        assertFalse(pm2.delete(def.id))
    }

    @Test fun duplicateNamesAreMadeUnique() = runBlocking {
        val pm = ProfileManager(InMemoryStore())
        val a = pm.createFrom(HeadsetCalibration(), "Box")
        val b = pm.createFrom(HeadsetCalibration(), "Box")
        assertEquals("Box", a.name)
        assertEquals("Box (2)", b.name)
    }

    @Test fun importedProfilesAreValidated() = runBlocking {
        val pm = ProfileManager(InMemoryStore())
        val p = pm.importJson("""{"format":1,"name":"Shared","fovDegrees":500}""")
        assertEquals(120f, p.fovDegrees)
        assertTrue(p.id > 0)
    }

    @Test fun viewportsPlaceLensCentersSymmetrically() {
        // S25 Ultra landscape: 3120 x 1440 at ~500 dpi.
        val (l, r) = ViewportLayout.compute(3120, 1440, 500f, 500f, HeadsetCalibration(lensSeparationMm = 63.5f))
        assertEquals(1560, l.width); assertEquals(1560, r.width)
        // 63.5 mm = 1250 px; each lens 625 px from screen center.
        assertEquals((1560 - 625) / 1560f, l.centerU, 1e-3f)
        assertEquals(625f / 1560f, r.centerU, 1e-3f)
        assertEquals(0.5f, l.centerV, 1e-6f)
        // Mirror symmetry.
        assertEquals(1f, l.centerU + r.centerU, 1e-4f)
    }

    @Test fun cutoutInsetKeepsLensCentersOnPhysicalPositions() {
        val (l0, r0) = ViewportLayout.compute(3120, 1440, 500f, 500f, HeadsetCalibration())
        val (l, r) = ViewportLayout.compute(3120, 1440, 500f, 500f, HeadsetCalibration(), horizontalInsetPx = 100)
        assertEquals(100, l.x); assertEquals(1460, l.width); assertEquals(1460, r.width)
        // Same physical lens position in screen pixels with and without the inset.
        assertEquals(l0.x + l0.centerU * l0.width, l.x + l.centerU * l.width, 0.5f)
        assertEquals(r0.x + r0.centerU * r0.width, r.x + r.centerU * r.width, 0.5f)
    }

    @Test fun perEyeOffsetsAreIndependent() {
        val cal = HeadsetCalibration(leftCenterOffsetY = 0.05f, rightCenterOffsetX = -0.02f)
        val (l, r) = ViewportLayout.compute(2000, 1000, 0f, 0f, cal)
        assertEquals(0.55f, l.centerV, 1e-5f)
        assertEquals(0.5f, r.centerV, 1e-5f)
        assertEquals(0.48f, r.centerU, 1e-5f)
        assertEquals(0.5f, l.centerU, 1e-5f)
    }

    @Test fun distortionKeepsCenterAndPushesOutward() {
        assertEquals(Pair(0.5f, 0.5f), DistortionModel.sourceCoord(0.5f, 0.5f, 0.5f, 0.5f, 1f, 0.3f, 0.1f))
        // Identity with zero coefficients.
        val id = DistortionModel.sourceCoord(0.7f, 0.2f, 0.5f, 0.5f, 1f, 0f, 0f)!!
        assertEquals(0.7f, id.first, 1e-6f); assertEquals(0.2f, id.second, 1e-6f)
        // Barrel pre-distortion samples further out the further from center.
        val near = DistortionModel.sourceCoord(0.6f, 0.5f, 0.5f, 0.5f, 1f, 0.3f, 0.1f)!!
        val far = DistortionModel.sourceCoord(0.8f, 0.5f, 0.5f, 0.5f, 1f, 0.3f, 0.1f)!!
        assertTrue(near.first > 0.6f && far.first > 0.8f)
        assertTrue((far.first - 0.8f) > (near.first - 0.6f))
        // Corners can fall outside the image and must render black.
        assertNull(DistortionModel.sourceCoord(0.0f, 0.0f, 0.5f, 0.5f, 1f, 0.6f, 0.4f))
    }
}
