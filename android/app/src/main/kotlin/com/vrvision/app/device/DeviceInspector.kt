package com.vrvision.app.device

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.MediaCodecInfo
import android.media.MediaCodecList
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Environment
import android.os.PowerManager
import android.os.StatFs
import com.vrvision.core.planning.CodecSupport
import com.vrvision.core.planning.DeviceState
import com.vrvision.core.planning.OutputCodec
import com.vrvision.core.planning.ThermalLevel
import com.vrvision.core.routing.Connectivity

/** One codec's capability summary, for the video information screen. */
data class CodecSummary(val name: String, val mime: String, val encoder: Boolean, val hardware: Boolean, val maxWidth: Int, val maxHeight: Int)

/** Reads hardware codec limits and current device conditions. */
class DeviceInspector(private val context: Context) : CodecSupport {

    private val codecs: List<MediaCodecInfo> by lazy { MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos.toList() }

    private fun candidates(mime: String, encoder: Boolean) =
        codecs.filter { it.isEncoder == encoder && it.supportedTypes.any { t -> t.equals(mime, ignoreCase = true) } }

    private fun supports(info: MediaCodecInfo, mime: String, w: Int, h: Int, fps: Double): Boolean = try {
        val vc = info.getCapabilitiesForType(mime).videoCapabilities
        vc != null && vc.isSizeSupported(w, h) && (fps <= 0 || vc.areSizeAndRateSupported(w, h, fps))
    } catch (_: Exception) { false }

    override fun canEncode(codec: OutputCodec, width: Int, height: Int, fps: Double): Boolean =
        candidates(codec.mime, true).any { supports(it, codec.mime, width, height, fps) }

    override fun canDecode(codec: OutputCodec, width: Int, height: Int, fps: Double): Boolean =
        candidates(codec.mime, false).any { supports(it, codec.mime, width, height, fps) }

    override fun alignment(codec: OutputCodec): Int = candidates(codec.mime, true).mapNotNull {
        try {
            val vc = it.getCapabilitiesForType(codec.mime).videoCapabilities
            maxOf(vc.widthAlignment, vc.heightAlignment)
        } catch (_: Exception) { null }
    }.maxOrNull()?.coerceAtLeast(2) ?: 2

    /** Whether any decoder on this phone handles the source mime at its size and rate. */
    fun canDecodeSource(mime: String?, width: Int, height: Int, fps: Double): Boolean =
        mime != null && candidates(mime, false).any { supports(it, mime, width, height, fps) || supports(it, mime, height, width, fps) }

    fun summaries(mimes: List<String> = listOf("video/hevc", "video/avc", "video/av01", "video/x-vnd.on2.vp9")): List<CodecSummary> =
        codecs.flatMap { info ->
            info.supportedTypes.filter { t -> mimes.any { it.equals(t, true) } }.mapNotNull { t ->
                try {
                    val vc = info.getCapabilitiesForType(t).videoCapabilities ?: return@mapNotNull null
                    CodecSummary(info.name, t, info.isEncoder, info.isHardwareAccelerated, vc.supportedWidths.upper, vc.supportedHeights.upper)
                } catch (_: Exception) { null }
            }
        }

    fun deviceState(): DeviceState {
        val dir = context.getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: context.filesDir
        val free = try { StatFs(dir.path).availableBytes } catch (_: Exception) { 0L }
        val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val plugged = (battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0
        val am = context.getSystemService(ActivityManager::class.java)
        val mem = ActivityManager.MemoryInfo().also { am.getMemoryInfo(it) }
        return DeviceState(
            freeStorageBytes = free,
            batteryPercent = if (level >= 0 && scale > 0) level * 100 / scale else null,
            charging = plugged,
            thermal = thermal(),
            availableRamBytes = mem.availMem,
            totalRamBytes = mem.totalMem,
        )
    }

    fun thermal(): ThermalLevel {
        val pm = context.getSystemService(PowerManager::class.java)
        return when (pm.currentThermalStatus) {
            PowerManager.THERMAL_STATUS_NONE -> ThermalLevel.NONE
            PowerManager.THERMAL_STATUS_LIGHT -> ThermalLevel.LIGHT
            PowerManager.THERMAL_STATUS_MODERATE -> ThermalLevel.MODERATE
            PowerManager.THERMAL_STATUS_SEVERE -> ThermalLevel.SEVERE
            PowerManager.THERMAL_STATUS_CRITICAL -> ThermalLevel.CRITICAL
            PowerManager.THERMAL_STATUS_EMERGENCY -> ThermalLevel.EMERGENCY
            PowerManager.THERMAL_STATUS_SHUTDOWN -> ThermalLevel.SHUTDOWN
            else -> ThermalLevel.UNKNOWN
        }
    }

    fun connectivity(): Connectivity {
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return Connectivity.NONE
        if (!caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) return Connectivity.NONE
        return if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED)) Connectivity.UNMETERED else Connectivity.METERED
    }
}
