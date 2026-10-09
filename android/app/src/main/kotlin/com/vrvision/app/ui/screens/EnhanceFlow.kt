package com.vrvision.app.ui.screens

import com.vrvision.app.AppContainer
import com.vrvision.app.data.VideoEntity
import com.vrvision.app.data.toFormat
import com.vrvision.app.data.toInfo
import com.vrvision.app.enhance.EnhanceSettings
import com.vrvision.core.enhance.PreviewSegment
import com.vrvision.core.planning.OutputCodec
import com.vrvision.core.planning.OutputPlan
import com.vrvision.core.planning.OutputPlanner
import com.vrvision.core.planning.OutputTarget
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

enum class ModePreference { HYBRID, LOCAL, CLOUD }

/** The user's enhancement choices for one video. Defaults follow the product requirements. */
data class EnhanceDraft(
    val scale: Double = 2.0,
    /** An explicitly chosen smaller target offered by the planner; null = use [scale]. */
    val alternative: OutputTarget? = null,
    val denoise: Boolean = true,
    val sharpen: Boolean = true,
    val sharpenAmount: Float = 0.35f,
    val preferHevc: Boolean = true,
    val acceptAvc: Boolean = false,
    val mode: ModePreference = ModePreference.HYBRID,
    val previewStartMs: Long = -1,
) {
    val effectiveScale: Double get() = alternative?.scale ?: scale
}

fun AppContainer.draft(video: VideoEntity): EnhanceDraft = drafts.getOrPut(video.id) {
    val p = settings.state.value
    EnhanceDraft(
        denoise = p.denoise, sharpen = p.sharpen, sharpenAmount = p.sharpenAmount, preferHevc = p.preferHevc,
        previewStartMs = PreviewSegment.suggestedStart(video.durationMs),
    )
}

suspend fun AppContainer.plan(video: VideoEntity, d: EnhanceDraft): OutputPlan = withContext(Dispatchers.Default) {
    OutputPlanner.plan(
        source = video.toInfo(), format = video.toFormat(), scale = d.effectiveScale, preferHevc = d.preferHevc,
        codecs = device, device = device.deviceState(),
    )
}

/** Job settings from a plan. Returns null when the plan can't be executed as chosen. */
fun settingsFor(video: VideoEntity, d: EnhanceDraft, plan: OutputPlan): EnhanceSettings? {
    val codec = plan.codec ?: return null
    if (codec == OutputCodec.AVC && d.preferHevc && !d.acceptAvc) return null
    return EnhanceSettings(
        outWidth = plan.requested.width, outHeight = plan.requested.height, scale = plan.requested.scale,
        outputMime = codec.mime, bitrate = plan.estimatedBitrateBps.coerceAtMost(Int.MAX_VALUE.toLong()).toInt(),
        denoise = d.denoise, sharpen = d.sharpen, sharpenAmount = d.sharpenAmount,
        layout = video.layout, projection = video.projection,
    )
}
