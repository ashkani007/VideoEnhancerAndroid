package com.vrvision.core.tracking

import com.vrvision.core.math.Quaternion
import com.vrvision.core.math.Vec3

/**
 * Screen orientation of the phone, matching android.view.Surface.ROTATION_* values.
 * Inside a headset the phone is in landscape: ROTATION_90 (top of phone to the left)
 * or ROTATION_270 (top of phone to the right).
 */
enum class DisplayRotation(val surfaceValue: Int) {
    ROTATION_0(0), ROTATION_90(1), ROTATION_180(2), ROTATION_270(3);

    companion object {
        fun fromSurface(value: Int) = entries.firstOrNull { it.surfaceValue == value } ?: ROTATION_0
    }
}

/**
 * Converts the Android rotation-vector orientation into a headset camera orientation.
 *
 * Coordinate frames:
 * - Android device frame: X right, Y up along the screen (portrait), Z out of the screen.
 * - Android world frame (rotation vector): X east, Y north, Z up.
 * - Render (OpenGL) world: X right/east, Y up, -Z forward/north.
 * - Camera: looks along -Z, up +Y, X right — the user's eyes inside the headset.
 *
 * The camera always looks out of the back of the phone (the user faces the screen),
 * and "up" for the camera is the screen's up direction for the current display rotation.
 */
class HeadPoseConverter {

    private var recenterYaw = 0f
    private var manualYaw = 0f
    private var manualPitch = 0f
    private var lastCamera: Quaternion = Quaternion.IDENTITY

    /**
     * @param deviceToWorld quaternion from SensorManager.getQuaternionFromVector (w, x, y, z),
     *        rotating device-frame vectors into the Android world frame.
     * @return camera orientation in render world after recentering and manual offsets.
     */
    fun cameraOrientation(deviceToWorld: Quaternion, rotation: DisplayRotation): Quaternion {
        val raw = ENU_TO_GL * deviceToWorld.normalized() * cameraInDevice(rotation)
        lastCamera = raw
        return applyOffsets(raw)
    }

    /** Orientation when no sensor is available (e.g. touch-drag look-around only). */
    fun manualOnlyOrientation(): Quaternion = applyOffsets(Quaternion.IDENTITY).also { lastCamera = Quaternion.IDENTITY }

    /** Makes the current horizontal look direction the new "forward". Pitch and roll are kept. */
    fun recenter() {
        recenterYaw = Quaternion.yawOf(lastCamera.rotate(FORWARD))
        manualYaw = 0f
        manualPitch = 0f
    }

    /** Touch-drag look-around for use without a headset. Pitch is clamped to ±85°. */
    fun addManualRotation(deltaYawRad: Float, deltaPitchRad: Float) {
        manualYaw += deltaYawRad
        manualPitch = (manualPitch + deltaPitchRad).coerceIn(-MAX_PITCH, MAX_PITCH)
    }

    /** Column-major view matrix (inverse camera rotation) for OpenGL. */
    fun viewMatrix(camera: Quaternion, out: FloatArray = FloatArray(16)): FloatArray =
        camera.conjugate().toMatrix(out)

    private fun applyOffsets(raw: Quaternion): Quaternion {
        val yaw = Quaternion.fromAxisAngle(UP, -recenterYaw + manualYaw)
        val pitch = Quaternion.fromAxisAngle(RIGHT, manualPitch)
        return (yaw * raw * pitch).normalized()
    }

    companion object {
        val FORWARD = Vec3(0f, 0f, -1f)
        val UP = Vec3(0f, 1f, 0f)
        val RIGHT = Vec3(1f, 0f, 0f)
        private const val MAX_PITCH = 1.4835f // 85°

        /** Android world (east, north, up) → render world (x=east, y=up, z=-north). */
        val ENU_TO_GL: Quaternion = Quaternion.fromBasis(
            Vec3(1f, 0f, 0f), // east  -> +X
            Vec3(0f, 0f, -1f), // north -> -Z
            Vec3(0f, 1f, 0f), // up    -> +Y
        )

        /** Camera axes expressed in device coordinates for each display rotation. */
        fun cameraInDevice(rotation: DisplayRotation): Quaternion = when (rotation) {
            // Portrait: camera axes coincide with device axes.
            DisplayRotation.ROTATION_0 -> Quaternion.IDENTITY
            // Top of phone on the left: screen-up is device +X, screen-right is device -Y.
            DisplayRotation.ROTATION_90 -> Quaternion.fromBasis(Vec3(0f, -1f, 0f), Vec3(1f, 0f, 0f), Vec3(0f, 0f, 1f))
            DisplayRotation.ROTATION_180 -> Quaternion.fromBasis(Vec3(-1f, 0f, 0f), Vec3(0f, -1f, 0f), Vec3(0f, 0f, 1f))
            // Top of phone on the right: screen-up is device -X, screen-right is device +Y.
            DisplayRotation.ROTATION_270 -> Quaternion.fromBasis(Vec3(0f, 1f, 0f), Vec3(-1f, 0f, 0f), Vec3(0f, 0f, 1f))
        }
    }
}
