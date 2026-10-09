package com.vrvision.core.planning

import com.vrvision.core.media.VideoFormat
import com.vrvision.core.media.VideoInfo
import com.vrvision.core.stereo.StereoLayout
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.roundToLong

enum class OutputCodec(val mime: String, val label: String) {
    HEVC("video/hevc", "H.265 / HEVC"),
    AVC("video/avc", "H.264 / AVC"),
}

/** What the device's codecs can do, answered by the app from MediaCodecInfo. */
interface CodecSupport {
    /** Whether a hardware-or-software encoder for [codec] accepts [width]x[height] at [fps]. */
    fun canEncode(codec: OutputCodec, width: Int, height: Int, fps: Double): Boolean
    /** Whether the device can decode (play back) [codec] at [width]x[height] at [fps]. */
    fun canDecode(codec: OutputCodec, width: Int, height: Int, fps: Double): Boolean
    /** Size alignment required by the encoder (typically 2 or 16). */
    fun alignment(codec: OutputCodec): Int = 2
}

enum class ThermalLevel { NONE, LIGHT, MODERATE, SEVERE, CRITICAL, EMERGENCY, SHUTDOWN, UNKNOWN }

data class DeviceState(
    val freeStorageBytes: Long,
    val batteryPercent: Int?,
    val charging: Boolean,
    val thermal: ThermalLevel,
    val availableRamBytes: Long,
    val totalRamBytes: Long,
)

enum class IssueSeverity { INFO, WARNING, BLOCKING }

data class PlanIssue(val severity: IssueSeverity, val code: String, val message: String)

data class OutputTarget(val width: Int, val height: Int, val scale: Double)

/**
 * The analysis shown before processing. [requested] is always the user's selection; if it
 * cannot be encoded or played, [alternatives] lists smaller targets that the user may
 * explicitly choose — the planner never substitutes one silently.
 */
data class OutputPlan(
    val source: VideoInfo,
    val format: VideoFormat,
    val requested: OutputTarget,
    val codec: OutputCodec?,
    val encodable: Boolean,
    val playableOnDevice: Boolean,
    val pixelCountFactor: Double,
    val estimatedBitrateBps: Long,
    val estimatedOutputBytes: Long,
    val requiredFreeBytes: Long,
    val issues: List<PlanIssue>,
    val alternatives: List<OutputTarget>,
) {
    val blocking: Boolean get() = issues.any { it.severity == IssueSeverity.BLOCKING }
}

object OutputPlanner {

    /** Bits per pixel per frame for visually high-quality encodes of upscaled content. */
    private const val BPP_HEVC = 0.07
    private const val BPP_AVC = 0.11
    private const val AUDIO_BPS_ESTIMATE = 256_000L
    private const val STORAGE_SAFETY_BYTES = 512L * 1024 * 1024

    fun plan(
        source: VideoInfo,
        format: VideoFormat,
        scale: Double,
        preferHevc: Boolean,
        codecs: CodecSupport,
        device: DeviceState,
        durationMs: Long = source.durationMs,
    ): OutputPlan {
        require(scale >= 1.0) { "Scale must be at least 1" }
        val fps = (source.frameRate ?: 30f).toDouble()
        val issues = mutableListOf<PlanIssue>()

        val order = if (preferHevc) listOf(OutputCodec.HEVC, OutputCodec.AVC) else listOf(OutputCodec.AVC, OutputCodec.HEVC)
        val requested = target(source.width, source.height, scale, codecs.alignment(order.first()), format.layout)
        val codec = order.firstOrNull { codecs.canEncode(it, requested.width, requested.height, fps) }
        val encodable = codec != null
        val playable = codec != null && codecs.canDecode(codec, requested.width, requested.height, fps)

        if (!encodable) {
            issues += PlanIssue(
                IssueSeverity.BLOCKING, "ENCODER_LIMIT",
                "This phone's video encoders cannot produce ${requested.width}×${requested.height} at ${"%.2f".format(fps)} fps.",
            )
        } else {
            if (preferHevc && codec == OutputCodec.AVC) issues += PlanIssue(
                IssueSeverity.WARNING, "HEVC_UNAVAILABLE",
                "HEVC can't encode this size here; H.264 can. Confirm H.264 or choose a smaller size.",
            )
            if (!playable) issues += PlanIssue(
                IssueSeverity.WARNING, "PLAYBACK_LIMIT",
                "The output can be encoded but exceeds this phone's decoder limits, so it may not play back here.",
            )
        }

        val bpp = if (codec == OutputCodec.AVC) BPP_AVC else BPP_HEVC
        val bitrate = (requested.width.toDouble() * requested.height * fps * bpp).roundToLong().coerceIn(2_000_000L, 400_000_000L)
        val seconds = durationMs / 1000.0
        val outBytes = ((bitrate + AUDIO_BPS_ESTIMATE) * seconds / 8).roundToLong()
        // Output is written once; keep a margin for the muxer's temporary file and the OS.
        val required = outBytes + outBytes / 5 + STORAGE_SAFETY_BYTES

        if (device.freeStorageBytes < required) issues += PlanIssue(
            IssueSeverity.BLOCKING, "STORAGE",
            "Needs about ${gb(required)} free; ${gb(device.freeStorageBytes)} available.",
        )
        val battery = device.batteryPercent
        if (battery != null && !device.charging) {
            if (battery < 15) issues += PlanIssue(IssueSeverity.BLOCKING, "BATTERY", "Battery at $battery%. Connect a charger before processing.")
            else if (battery < 40) issues += PlanIssue(IssueSeverity.WARNING, "BATTERY", "Battery at $battery%. Long local processing is best done while charging.")
        }
        when (device.thermal) {
            ThermalLevel.MODERATE -> issues += PlanIssue(IssueSeverity.WARNING, "THERMAL", "Phone is warm; local processing will be throttled.")
            ThermalLevel.SEVERE, ThermalLevel.CRITICAL, ThermalLevel.EMERGENCY, ThermalLevel.SHUTDOWN ->
                issues += PlanIssue(IssueSeverity.BLOCKING, "THERMAL", "Phone is too hot for local processing. Let it cool down.")
            else -> Unit
        }
        if (source.bitDepth != null && source.bitDepth > 8) issues += PlanIssue(
            IssueSeverity.WARNING, "BIT_DEPTH",
            "Source is ${source.bitDepth}-bit${if (source.hdr == true) " HDR" else ""}; local AI processing works in 8-bit SDR and will not preserve HDR.",
        )
        issues += PlanIssue(
            IssueSeverity.INFO, "PIXELS",
            "2× scaling doubles width and height: ${"%.0f".format(scale * scale)}× the pixels. More pixels do not guarantee proportionally more visible detail.",
        )

        val alternatives = if (encodable && playable) emptyList() else alternatives(source, format, scale, fps, order, codecs)

        return OutputPlan(
            source = source, format = format, requested = requested, codec = codec,
            encodable = encodable, playableOnDevice = playable, pixelCountFactor = requested.width.toDouble() * requested.height / source.pixelCount,
            estimatedBitrateBps = bitrate, estimatedOutputBytes = outBytes, requiredFreeBytes = required,
            issues = issues, alternatives = alternatives,
        )
    }

    /** Output size for a scale, rounded to the encoder alignment (keeps stereo halves equal). */
    fun target(width: Int, height: Int, scale: Double, alignment: Int, layout: StereoLayout = StereoLayout.MONO): OutputTarget {
        val a = max(2, alignment)
        // Each eye half must itself be aligned so both halves stay identical in size.
        val aw = if (layout == StereoLayout.SIDE_BY_SIDE) a * 2 else a
        val ah = if (layout == StereoLayout.TOP_BOTTOM) a * 2 else a
        val w = (Math.round(width * scale / aw) * aw).toInt().coerceAtLeast(aw)
        val h = (Math.round(height * scale / ah) * ah).toInt().coerceAtLeast(ah)
        return OutputTarget(w, h, scale)
    }

    /** Largest encodable and playable scales below the requested one, best first. */
    private fun alternatives(source: VideoInfo, format: VideoFormat, scale: Double, fps: Double, order: List<OutputCodec>, codecs: CodecSupport): List<OutputTarget> {
        val out = mutableListOf<OutputTarget>()
        var s = floor(scale * 20) / 20 - 0.05
        while (s >= 1.0 && out.size < 3) {
            val ok = order.any { c ->
                val t = target(source.width, source.height, s, codecs.alignment(c), format.layout)
                codecs.canEncode(c, t.width, t.height, fps) && codecs.canDecode(c, t.width, t.height, fps)
            }
            if (ok) {
                val t = target(source.width, source.height, s, codecs.alignment(order.first()), format.layout)
                if (out.none { it.width == t.width }) out += t
                s -= 0.25
            } else s -= 0.05
        }
        return out
    }

    private fun gb(b: Long) = "%.1f GB".format(b / 1e9)

}
