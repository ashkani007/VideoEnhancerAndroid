package com.vrvision.core

import com.vrvision.core.media.VideoFormat
import com.vrvision.core.media.VideoInfo
import com.vrvision.core.planning.CodecSupport
import com.vrvision.core.planning.DeviceState
import com.vrvision.core.planning.IssueSeverity
import com.vrvision.core.planning.OutputCodec
import com.vrvision.core.planning.OutputPlanner
import com.vrvision.core.planning.ThermalLevel
import com.vrvision.core.routing.CloudQuote
import com.vrvision.core.routing.Connectivity
import com.vrvision.core.routing.LocalMemoryModel
import com.vrvision.core.routing.LocalThroughput
import com.vrvision.core.routing.ProcessingRoute
import com.vrvision.core.routing.RoutingEngine
import com.vrvision.core.routing.RoutingInput
import com.vrvision.core.stereo.StereoLayout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** Codec limits similar to a flagship phone: HEVC/AVC encode up to 8192x4320, decode the same. */
class FakeCodecs(private val maxW: Int = 8192, private val maxH: Int = 4320, private val hevc: Boolean = true) : CodecSupport {
    override fun canEncode(codec: OutputCodec, width: Int, height: Int, fps: Double) =
        (codec == OutputCodec.AVC || hevc) && fits(width, height)
    override fun canDecode(codec: OutputCodec, width: Int, height: Int, fps: Double) = fits(width, height)
    private fun fits(w: Int, h: Int) = (w <= maxW && h <= maxH) || (w <= maxH && h <= maxW)
    override fun alignment(codec: OutputCodec) = 16
}

class PlanningRoutingTest {

    private val goodDevice = DeviceState(100_000_000_000, 80, true, ThermalLevel.NONE, 6_000_000_000, 12_000_000_000)
    private fun info(w: Int, h: Int, durS: Long = 60, fps: Float = 30f) = VideoInfo(w, h, 0, durS * 1000, fps, "video/hevc", sizeBytes = 500_000_000)

    @Test fun twoXDoublesEachDimensionAndQuadruplesPixels() {
        val p = OutputPlanner.plan(info(1920, 1080), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        assertEquals(3840, p.requested.width)
        assertEquals(2160, p.requested.height)
        assertEquals(4.0, p.pixelCountFactor, 1e-9)
        assertEquals(OutputCodec.HEVC, p.codec)
        assertFalse(p.blocking)
        assertTrue(p.alternatives.isEmpty())
        assertTrue(p.issues.any { it.code == "PIXELS" && it.message.contains("4×") })
    }

    @Test fun oversizedTargetIsBlockedWithExplicitAlternatives() {
        // VR180 SBS 5760x2880 -> 11520x5760 exceeds an 8K encoder.
        val p = OutputPlanner.plan(info(5760, 2880), VideoFormat(layout = StereoLayout.SIDE_BY_SIDE), 2.0, true, FakeCodecs(), goodDevice)
        assertEquals(11520, p.requested.width) // the user's selection is reported unchanged
        assertTrue(p.blocking)
        assertFalse(p.encodable)
        assertTrue(p.alternatives.isNotEmpty())
        val best = p.alternatives.first()
        assertTrue(best.width <= 8192 && best.height <= 4320)
        assertTrue(best.scale < 2.0)
        // SBS halves stay equal and aligned.
        assertEquals(0, (best.width / 2) % 16)
    }

    @Test fun hevcFallbackIsAWarningNotSilent() {
        val p = OutputPlanner.plan(info(1920, 1080), VideoFormat(), 2.0, true, FakeCodecs(hevc = false), goodDevice)
        assertEquals(OutputCodec.AVC, p.codec)
        assertTrue(p.issues.any { it.code == "HEVC_UNAVAILABLE" && it.severity == IssueSeverity.WARNING })
    }

    @Test fun storageBatteryAndThermalChecks() {
        val tight = goodDevice.copy(freeStorageBytes = 100_000_000, batteryPercent = 10, charging = false, thermal = ThermalLevel.SEVERE)
        val p = OutputPlanner.plan(info(1920, 1080, durS = 600), VideoFormat(), 2.0, true, FakeCodecs(), tight)
        val codes = p.issues.filter { it.severity == IssueSeverity.BLOCKING }.map { it.code }.toSet()
        assertEquals(setOf("STORAGE", "BATTERY", "THERMAL"), codes)
        assertTrue(p.estimatedOutputBytes > 0)
    }

    @Test fun outputSizeEstimateScalesWithDuration() {
        val a = OutputPlanner.plan(info(1920, 1080, durS = 60), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        val b = OutputPlanner.plan(info(1920, 1080, durS = 120), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        assertEquals(2.0, b.estimatedOutputBytes.toDouble() / a.estimatedOutputBytes, 0.01)
    }

    private fun routing(
        plan: com.vrvision.core.planning.OutputPlan,
        localOnly: Boolean = false,
        quote: CloudQuote? = CloudQuote(120.0, 0.5, "EUR", 4_000_000_000, 3_600_000),
        model: Boolean = true,
        throughput: LocalThroughput? = null,
        connectivity: Connectivity = Connectivity.UNMETERED,
    ) = RoutingInput(
        plan = plan, localModelAvailable = model, localModelName = "realesr-general-x4v3",
        localMemoryBytes = LocalMemoryModel.estimateBytes(1920, 1080, 3840, 2160, 128, 4, 5_000_000),
        localThroughput = throughput, privacyLocalOnly = localOnly, cloudConfigured = true,
        connectivity = connectivity, sourceSizeBytes = 500_000_000, cloudQuote = quote,
        thermal = ThermalLevel.NONE, batteryPercent = 80, charging = true,
    )

    @Test fun localPreferredForPrivacyWhenFeasible() {
        val p = OutputPlanner.plan(info(1920, 1080), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        val d = RoutingEngine.decide(routing(p), 6_000_000_000)
        assertEquals(ProcessingRoute.LOCAL, d.recommended)
        assertTrue(d.cloudRequiresConsent)
        assertTrue(ProcessingRoute.CLOUD in d.overrides)
    }

    @Test fun localOnlyPrivacyNeverRecommendsCloud() {
        val p = OutputPlanner.plan(info(1920, 1080), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        val d = RoutingEngine.decide(routing(p, localOnly = true, model = false), 6_000_000_000)
        assertEquals(ProcessingRoute.UNSUPPORTED, d.recommended)
        assertFalse(d.cloud.feasible)
        assertTrue(d.cloud.reasons.any { it.contains("privacy") })
    }

    @Test fun cloudRecommendedWhenLocalIsFarSlower() {
        val p = OutputPlanner.plan(info(1920, 1080, durS = 600), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        // 2000 ms per source megapixel -> 18000 frames * 2.07 MP * 2 s = ~20 h.
        val d = RoutingEngine.decide(routing(p, throughput = LocalThroughput(2000.0, "preview")), 6_000_000_000)
        assertEquals(ProcessingRoute.CLOUD, d.recommended)
        assertNotNull(d.local.estimatedSeconds)
        assertTrue(ProcessingRoute.LOCAL in d.overrides)
    }

    @Test fun offlineFallsBackToLocal() {
        val p = OutputPlanner.plan(info(1920, 1080), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        val d = RoutingEngine.decide(routing(p, connectivity = Connectivity.NONE), 6_000_000_000)
        assertEquals(ProcessingRoute.LOCAL, d.recommended)
        assertTrue(d.cloud.reasons.any { it.contains("internet") })
    }

    @Test fun insufficientRamMakesLocalInfeasible() {
        val p = OutputPlanner.plan(info(1920, 1080), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        val d = RoutingEngine.decide(routing(p, quote = null), 100_000_000)
        assertEquals(ProcessingRoute.UNSUPPORTED, d.recommended)
        assertTrue(d.local.reasons.any { it.contains("memory") })
    }

    @Test fun serverLimitsAreRespected() {
        val p = OutputPlanner.plan(info(1920, 1080), VideoFormat(), 2.0, true, FakeCodecs(), goodDevice)
        val d = RoutingEngine.decide(routing(p, quote = CloudQuote(10.0, null, null, 100_000_000, 3_600_000)), 6_000_000_000)
        assertFalse(d.cloud.feasible)
    }
}
