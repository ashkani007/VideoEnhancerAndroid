package com.vrvision.core.routing

import com.vrvision.core.planning.IssueSeverity
import com.vrvision.core.planning.OutputPlan
import com.vrvision.core.planning.ThermalLevel

enum class ProcessingRoute { LOCAL, CLOUD, UNSUPPORTED }

enum class Connectivity { NONE, METERED, UNMETERED }

/** Measured local inference speed, from a preview run or the on-device benchmark. */
data class LocalThroughput(
    /** Milliseconds of end-to-end processing per megapixel of *source* frame. */
    val msPerSourceMegapixel: Double,
    val measuredOn: String,
)

/** Server quote for a job (from the backend's /v1/quote); null when cloud isn't configured or reachable. */
data class CloudQuote(
    val estimatedSeconds: Double,
    /** Estimated cost in the operator's currency, if the operator publishes one. */
    val estimatedCost: Double?,
    val currency: String?,
    val maxUploadBytes: Long,
    val maxDurationMs: Long,
)

data class RoutingInput(
    val plan: OutputPlan,
    val localModelAvailable: Boolean,
    val localModelName: String?,
    /** Working memory a local run needs (see [LocalMemoryModel]). */
    val localMemoryBytes: Long,
    val localThroughput: LocalThroughput?,
    val privacyLocalOnly: Boolean,
    val cloudConfigured: Boolean,
    val connectivity: Connectivity,
    val sourceSizeBytes: Long?,
    val cloudQuote: CloudQuote?,
    val thermal: ThermalLevel,
    val batteryPercent: Int?,
    val charging: Boolean,
)

data class RouteOption(
    val route: ProcessingRoute,
    val feasible: Boolean,
    val reasons: List<String>,
    val estimatedSeconds: Double?,
)

data class RoutingDecision(
    val recommended: ProcessingRoute,
    val reasons: List<String>,
    val local: RouteOption,
    val cloud: RouteOption,
    /** Cloud always needs the separate per-video consent screen before any upload. */
    val cloudRequiresConsent: Boolean = true,
) {
    /** Routes the user may pick instead of the recommendation. */
    val overrides: List<ProcessingRoute>
        get() = listOfNotNull(
            ProcessingRoute.LOCAL.takeIf { local.feasible && recommended != ProcessingRoute.LOCAL },
            ProcessingRoute.CLOUD.takeIf { cloud.feasible && recommended != ProcessingRoute.CLOUD },
        )
}

object LocalMemoryModel {
    /**
     * Rough peak working memory for tiled local inference: decoder and encoder buffers for
     * one frame each, the 8-bit RGB source frame, the output YUV frame, per-tile float
     * tensors (input, output, and ~4 live 64-channel activations), and model weights.
     */
    fun estimateBytes(srcW: Int, srcH: Int, outW: Int, outH: Int, tile: Int, modelScale: Int, modelBytes: Long): Long {
        val decoder = srcW.toLong() * srcH * 3 / 2 * 4 // codec keeps several buffers in flight
        val encoder = outW.toLong() * outH * 3 / 2 * 4
        val srcRgb = srcW.toLong() * srcH * 3
        val outYuv = outW.toLong() * outH * 3 / 2
        val tileIn = 3L * tile * tile * 4
        val tileOut = 3L * tile * modelScale * tile * modelScale * 4
        val activations = 4L * 64 * tile * tile * 4
        return decoder + encoder + srcRgb + outYuv + tileIn + tileOut + activations + modelBytes * 2
    }
}

/**
 * Recommends Local, Cloud or Unsupported with human-readable reasons. It never starts an
 * upload: a CLOUD recommendation still requires explicit consent for this video.
 */
object RoutingEngine {

    fun decide(input: RoutingInput, availableRamBytes: Long): RoutingDecision {
        val local = evaluateLocal(input, availableRamBytes)
        val cloud = evaluateCloud(input)
        val reasons = mutableListOf<String>()

        val recommended = when {
            !local.feasible && !cloud.feasible -> {
                reasons += "Neither local nor cloud processing can handle this video with the current settings."
                ProcessingRoute.UNSUPPORTED
            }
            local.feasible && !cloud.feasible -> {
                reasons += "Processing stays on this phone."
                ProcessingRoute.LOCAL
            }
            !local.feasible && cloud.feasible -> {
                reasons += "Local processing isn't possible here; cloud can process it after you consent to the upload."
                ProcessingRoute.CLOUD
            }
            else -> {
                // Both feasible: prefer local (privacy) unless it would be dramatically slower.
                val lt = local.estimatedSeconds
                val ct = cloud.estimatedSeconds
                if (lt != null && ct != null && lt > 4 * ct && lt > 30 * 60) {
                    reasons += "Local processing would take about ${minutes(lt)} versus about ${minutes(ct)} in the cloud."
                    ProcessingRoute.CLOUD
                } else {
                    reasons += if (lt == null) "Local is preferred for privacy. Run a 10-second preview to measure local speed."
                    else "Local is preferred for privacy and takes about ${minutes(lt)}."
                    ProcessingRoute.LOCAL
                }
            }
        }
        return RoutingDecision(recommended, reasons, local, cloud)
    }

    private fun evaluateLocal(input: RoutingInput, availableRamBytes: Long): RouteOption {
        val reasons = mutableListOf<String>()
        var ok = true
        val plan = input.plan
        if (!input.localModelAvailable) { ok = false; reasons += "No on-device AI model is installed." }
        if (!plan.encodable) { ok = false; reasons += "The requested output size can't be encoded on this phone." }
        plan.issues.filter { it.severity == IssueSeverity.BLOCKING && it.code in setOf("STORAGE", "BATTERY", "THERMAL") }
            .forEach { ok = false; reasons += it.message }
        if (input.localMemoryBytes > availableRamBytes * 6 / 10) {
            ok = false
            reasons += "Needs about ${mb(input.localMemoryBytes)} of working memory; only ${mb(availableRamBytes)} is available."
        }
        val seconds = input.localThroughput?.let { t ->
            val frames = (plan.source.frameRate ?: 30f) * input.plan.source.durationMs / 1000.0
            frames * (plan.source.pixelCount / 1e6) * t.msPerSourceMegapixel / 1000.0
        }
        if (seconds != null) reasons += "Estimated ${minutes(seconds)} based on ${input.localThroughput?.measuredOn}."
        if (ok && input.thermal == ThermalLevel.MODERATE) reasons += "The phone is warm, so expect throttling."
        if (ok && input.batteryPercent != null && input.batteryPercent < 40 && !input.charging) reasons += "Keep the phone charging during processing."
        return RouteOption(ProcessingRoute.LOCAL, ok, reasons, seconds)
    }

    private fun evaluateCloud(input: RoutingInput): RouteOption {
        val reasons = mutableListOf<String>()
        var ok = true
        when {
            input.privacyLocalOnly -> { ok = false; reasons += "Your privacy setting keeps all processing on this phone." }
            !input.cloudConfigured -> { ok = false; reasons += "No cloud backend is configured." }
            input.connectivity == Connectivity.NONE -> { ok = false; reasons += "No internet connection." }
            input.cloudQuote == null -> { ok = false; reasons += "The cloud backend did not respond to a quote request." }
        }
        val q = input.cloudQuote
        if (ok && q != null) {
            val size = input.sourceSizeBytes
            if (size != null && size > q.maxUploadBytes) { ok = false; reasons += "The file (${mb(size)}) exceeds the server limit of ${mb(q.maxUploadBytes)}." }
            if (input.plan.source.durationMs > q.maxDurationMs) { ok = false; reasons += "The video is longer than the server allows (${minutes(q.maxDurationMs / 1000.0)})." }
            if (ok) {
                reasons += "Estimated ${minutes(q.estimatedSeconds)} of server time" +
                    (if (q.estimatedCost != null) ", about %.2f %s.".format(q.estimatedCost, q.currency ?: "") else "; the operator publishes no price.")
                if (input.connectivity == Connectivity.METERED && size != null) reasons += "Uploading ${mb(size)} over a metered connection."
            }
        }
        return RouteOption(ProcessingRoute.CLOUD, ok, reasons, if (ok) q?.estimatedSeconds else null)
    }

    private fun minutes(s: Double): String = if (s < 90) "%.0f s".format(s) else if (s < 5400) "%.0f min".format(s / 60) else "%.1f h".format(s / 3600)
    private fun mb(b: Long) = if (b >= 1_000_000_000) "%.1f GB".format(b / 1e9) else "%.0f MB".format(b / 1e6)
}
