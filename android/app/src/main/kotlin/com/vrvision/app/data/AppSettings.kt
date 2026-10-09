package com.vrvision.app.data

import android.content.Context
import com.vrvision.app.BuildConfig
import com.vrvision.core.calibration.CalibrationStore
import com.vrvision.core.calibration.HeadsetCalibration
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** User preferences. Cloud is disabled until the user enables it and enters a server. */
data class Preferences(
    val cloudEnabled: Boolean = false,
    val cloudUrl: String = BuildConfig.DEFAULT_CLOUD_URL,
    /** "LOCAL_ONLY" keeps the router from ever recommending cloud. */
    val privacyLocalOnly: Boolean = true,
    val respectCutout: Boolean = true,
    val headsetModeDefault: Boolean = true,
    val useHeadTracking: Boolean = true,
    val denoise: Boolean = true,
    val sharpen: Boolean = true,
    val sharpenAmount: Float = 0.35f,
    val preferHevc: Boolean = true,
    val deleteCloudDataImmediately: Boolean = true,
)

class AppSettings(context: Context) {
    private val prefs = context.getSharedPreferences("vrvision", Context.MODE_PRIVATE)
    private val _state = MutableStateFlow(load())
    val state: StateFlow<Preferences> = _state.asStateFlow()

    private fun load() = Preferences(
        cloudEnabled = prefs.getBoolean("cloudEnabled", false),
        cloudUrl = prefs.getString("cloudUrl", BuildConfig.DEFAULT_CLOUD_URL) ?: "",
        privacyLocalOnly = prefs.getBoolean("privacyLocalOnly", true),
        respectCutout = prefs.getBoolean("respectCutout", true),
        headsetModeDefault = prefs.getBoolean("headsetModeDefault", true),
        useHeadTracking = prefs.getBoolean("useHeadTracking", true),
        denoise = prefs.getBoolean("denoise", true),
        sharpen = prefs.getBoolean("sharpen", true),
        sharpenAmount = prefs.getFloat("sharpenAmount", 0.35f),
        preferHevc = prefs.getBoolean("preferHevc", true),
        deleteCloudDataImmediately = prefs.getBoolean("deleteCloudDataImmediately", true),
    )

    fun update(transform: (Preferences) -> Preferences) {
        val p = transform(_state.value)
        prefs.edit()
            .putBoolean("cloudEnabled", p.cloudEnabled)
            .putString("cloudUrl", p.cloudUrl.trim())
            .putBoolean("privacyLocalOnly", p.privacyLocalOnly)
            .putBoolean("respectCutout", p.respectCutout)
            .putBoolean("headsetModeDefault", p.headsetModeDefault)
            .putBoolean("useHeadTracking", p.useHeadTracking)
            .putBoolean("denoise", p.denoise)
            .putBoolean("sharpen", p.sharpen)
            .putFloat("sharpenAmount", p.sharpenAmount.coerceIn(0f, 1f))
            .putBoolean("preferHevc", p.preferHevc)
            .putBoolean("deleteCloudDataImmediately", p.deleteCloudDataImmediately)
            .apply()
        _state.value = p
    }

    var activeCalibrationId: Long?
        get() = prefs.getLong("activeCalibration", -1L).takeIf { it > 0 }
        set(value) { prefs.edit().putLong("activeCalibration", value ?: -1L).apply() }

    /** Operator-issued API key for the user's backend; private app storage, never logged. */
    var cloudApiKey: String?
        get() = prefs.getString("cloudApiKey", null)
        set(value) { prefs.edit().putString("cloudApiKey", value?.trim()).apply() }

    /** Last on-device benchmark: ms per source megapixel per frame, and when it was measured. */
    var benchmarkMsPerMp: Float?
        get() = prefs.getFloat("benchMsPerMp", -1f).takeIf { it > 0 }
        set(value) { prefs.edit().putFloat("benchMsPerMp", value ?: -1f).apply() }
    var benchmarkInfo: String?
        get() = prefs.getString("benchInfo", null)
        set(value) { prefs.edit().putString("benchInfo", value).apply() }

    /** Short-lived cloud session token, kept only in private app storage. */
    var cloudToken: String?
        get() = prefs.getString("cloudToken", null)
        set(value) { prefs.edit().putString("cloudToken", value).apply() }
}

class RoomCalibrationStore(private val dao: CalibrationDao, private val settings: AppSettings) : CalibrationStore {
    override suspend fun all(): List<HeadsetCalibration> = dao.all().map { it.toModel() }
    override suspend fun upsert(profile: HeadsetCalibration): Long {
        val e = profile.toEntity()
        val id = dao.upsert(e)
        return if (profile.id != 0L) profile.id else id
    }
    override suspend fun delete(id: Long) = dao.delete(id)
    override suspend fun activeId(): Long? = settings.activeCalibrationId
    override suspend fun setActiveId(id: Long) { settings.activeCalibrationId = id }
}

fun CalibrationEntity.toModel() = HeadsetCalibration(
    id = id, name = name, lensSeparationMm = lensSeparationMm, lensToBottomMm = lensToBottomMm,
    distortionEnabled = distortionEnabled, k1 = k1, k2 = k2,
    leftCenterOffsetX = leftCenterOffsetX, leftCenterOffsetY = leftCenterOffsetY,
    rightCenterOffsetX = rightCenterOffsetX, rightCenterOffsetY = rightCenterOffsetY,
    imageOffsetX = imageOffsetX, imageOffsetY = imageOffsetY,
    zoom = zoom, fovDegrees = fovDegrees, viewportMargin = viewportMargin,
)

fun HeadsetCalibration.toEntity() = CalibrationEntity(
    id = id, name = name, lensSeparationMm = lensSeparationMm, lensToBottomMm = lensToBottomMm,
    distortionEnabled = distortionEnabled, k1 = k1, k2 = k2,
    leftCenterOffsetX = leftCenterOffsetX, leftCenterOffsetY = leftCenterOffsetY,
    rightCenterOffsetX = rightCenterOffsetX, rightCenterOffsetY = rightCenterOffsetY,
    imageOffsetX = imageOffsetX, imageOffsetY = imageOffsetY,
    zoom = zoom, fovDegrees = fovDegrees, viewportMargin = viewportMargin,
)
