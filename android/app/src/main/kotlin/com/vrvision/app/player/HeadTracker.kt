package com.vrvision.app.player

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.vrvision.core.math.Quaternion
import com.vrvision.core.tracking.DisplayRotation
import com.vrvision.core.tracking.HeadPoseConverter

/**
 * Head tracking from Android's fused rotation-vector sensors.
 *
 * Prefers TYPE_GAME_ROTATION_VECTOR (gyro + accelerometer, no magnetometer), which avoids
 * sudden yaw jumps near metal or magnets in a headset; falls back to TYPE_ROTATION_VECTOR.
 * Without either sensor the view is controlled by touch drag only.
 */
class HeadTracker(context: Context) : SensorEventListener {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val sensor: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR)
        ?: sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)

    val sensorName: String? get() = sensor?.name
    val hasSensor: Boolean get() = sensor != null

    private val converter = HeadPoseConverter()
    private val q = FloatArray(4)
    @Volatile private var latest: Quaternion? = null
    @Volatile var displayRotation: DisplayRotation = DisplayRotation.ROTATION_90
    @Volatile var enabled: Boolean = true
    private var running = false

    fun start() {
        if (running || sensor == null) return
        // SENSOR_DELAY_GAME (~50-200 Hz) balances latency and battery; the renderer reads the
        // most recent sample every frame.
        running = sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_GAME)
    }

    fun stop() {
        if (running) sensorManager.unregisterListener(this)
        running = false
    }

    override fun onSensorChanged(event: SensorEvent) {
        SensorManager.getQuaternionFromVector(q, event.values)
        latest = Quaternion(q[0], q[1], q[2], q[3])
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    /** Camera orientation for this frame (called on the GL thread). */
    @Synchronized
    fun orientation(): Quaternion {
        val sample = latest
        return if (enabled && sample != null) converter.cameraOrientation(sample, displayRotation)
        else converter.manualOnlyOrientation()
    }

    @Synchronized
    fun recenter() = converter.recenter()

    @Synchronized
    fun drag(dxRadians: Float, dyRadians: Float) = converter.addManualRotation(dxRadians, dyRadians)
}
