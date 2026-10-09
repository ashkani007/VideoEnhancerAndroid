package com.vrvision.core

import com.vrvision.core.math.Quaternion
import com.vrvision.core.math.Vec3
import com.vrvision.core.tracking.DisplayRotation
import com.vrvision.core.tracking.HeadPoseConverter
import kotlin.math.PI
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class HeadTrackingTest {

    private val east = Vec3(1f, 0f, 0f)
    private val north = Vec3(0f, 1f, 0f)
    private val up = Vec3(0f, 0f, 1f)
    private fun neg(v: Vec3) = v * -1f

    /** Device-to-world rotation from where the device axes point in ENU world coordinates. */
    private fun device(xAxis: Vec3, yAxis: Vec3, zAxis: Vec3) = Quaternion.fromBasis(xAxis, yAxis, zAxis)

    private fun forward(q: Quaternion) = q.rotate(Vec3(0f, 0f, -1f))
    private fun camUp(q: Quaternion) = q.rotate(Vec3(0f, 1f, 0f))
    private fun camRight(q: Quaternion) = q.rotate(Vec3(1f, 0f, 0f))

    /** Phone upright in landscape (top to the left), screen towards the user who faces north. */
    private val headsetFacingNorth = device(xAxis = up, yAxis = neg(east), zAxis = neg(north))

    @Test fun landscapeHeadsetLooksForwardAndUpright() {
        val t = HeadPoseConverter()
        val cam = t.cameraOrientation(headsetFacingNorth, DisplayRotation.ROTATION_90)
        assertTrue(forward(cam).approx(Vec3(0f, 0f, -1f)), "forward=${forward(cam)}")
        assertTrue(camUp(cam).approx(Vec3(0f, 1f, 0f)), "up=${camUp(cam)}")
        assertTrue(camRight(cam).approx(Vec3(1f, 0f, 0f)), "right=${camRight(cam)}")
    }

    @Test fun rotation270IsAlsoUpright() {
        // Top of the phone to the right: device X points down, Y points east.
        val q = device(xAxis = neg(up), yAxis = east, zAxis = neg(north))
        val cam = HeadPoseConverter().cameraOrientation(q, DisplayRotation.ROTATION_270)
        assertTrue(forward(cam).approx(Vec3(0f, 0f, -1f)))
        assertTrue(camUp(cam).approx(Vec3(0f, 1f, 0f)))
    }

    @Test fun turningHeadRightLooksRight() {
        // Same pose rotated 90° clockwise seen from above: user now faces east.
        val yawRight = Quaternion.fromAxisAngle(up, (-PI / 2).toFloat())
        val cam = HeadPoseConverter().cameraOrientation(yawRight * headsetFacingNorth, DisplayRotation.ROTATION_90)
        assertTrue(forward(cam).approx(Vec3(1f, 0f, 0f)), "forward=${forward(cam)}")
    }

    @Test fun lookingUpPitchesUp() {
        // Pitch up 30° about the user's right axis (east).
        val pitchUp = Quaternion.fromAxisAngle(east, (PI / 6).toFloat())
        val cam = HeadPoseConverter().cameraOrientation(pitchUp * headsetFacingNorth, DisplayRotation.ROTATION_90)
        val f = forward(cam)
        assertEquals(0.5f, f.y, 1e-4f)
        assertTrue(f.z < 0f)
    }

    @Test fun tiltingHeadRightRollsCameraRight() {
        // Roll right: rotate about the viewing direction (north) clockwise as seen by the user.
        val rollRight = Quaternion.fromAxisAngle(north, (PI / 6).toFloat())
        val cam = HeadPoseConverter().cameraOrientation(rollRight * headsetFacingNorth, DisplayRotation.ROTATION_90)
        assertTrue(camUp(cam).x > 0.1f, "up should lean right: ${camUp(cam)}")
        assertTrue(forward(cam).approx(Vec3(0f, 0f, -1f)))
    }

    @Test fun recenterMakesCurrentHeadingForwardButKeepsPitch() {
        val t = HeadPoseConverter()
        val pose = Quaternion.fromAxisAngle(up, 1.0f) * Quaternion.fromAxisAngle(east, 0.3f) * headsetFacingNorth
        t.cameraOrientation(pose, DisplayRotation.ROTATION_90)
        t.recenter()
        val f = forward(t.cameraOrientation(pose, DisplayRotation.ROTATION_90))
        assertEquals(0f, f.x, 1e-4f)
        assertTrue(f.z < 0f)
        assertTrue(f.y > 0.2f, "pitch must be preserved")
    }

    @Test fun viewMatrixIsInverseOfCamera() {
        val t = HeadPoseConverter()
        val cam = Quaternion.fromAxisAngle(Vec3(0.3f, 1f, 0.2f), 0.7f)
        val view = t.viewMatrix(cam)
        val camM = cam.toMatrix()
        // view * cam == identity (column-major multiply).
        for (r in 0 until 3) for (c in 0 until 3) {
            var s = 0f
            for (k in 0 until 3) s += view[k * 4 + r] * camM[c * 4 + k]
            assertEquals(if (r == c) 1f else 0f, s, 1e-4f)
        }
    }

    @Test fun manualPitchIsClamped() {
        val t = HeadPoseConverter()
        t.addManualRotation(0f, 10f)
        val f = forward(t.manualOnlyOrientation())
        assertTrue(f.y < 1f && f.y > 0.99f)
    }
}
