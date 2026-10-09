package com.vrvision.app

import com.vrvision.app.cloud.CloudClient
import com.vrvision.app.data.VideoEntity
import com.vrvision.app.ui.screens.EnhanceDraft
import com.vrvision.app.ui.screens.settingsFor
import com.vrvision.core.media.VideoFormat
import com.vrvision.core.media.VideoInfo
import com.vrvision.core.planning.CodecSupport
import com.vrvision.core.planning.DeviceState
import com.vrvision.core.planning.OutputCodec
import com.vrvision.core.planning.OutputPlanner
import com.vrvision.core.planning.ThermalLevel
import com.vrvision.core.stereo.StereoLayout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class EnhanceFlowTest {

    private val video = VideoEntity(
        id = 1, uri = "content://x", displayName = "trip_sbs.mp4", sizeBytes = 1_000_000, width = 3840, height = 1080,
        rotationDegrees = 0, durationMs = 60_000, frameRate = 30f, videoMime = "video/hevc", codecProfile = null,
        bitDepth = 8, bitrate = null, hdr = false, audioSummary = "", audioTrackCount = 1, subtitleTrackCount = 0,
        layout = "SIDE_BY_SIDE", packing = "FULL", projection = "FLAT", swapEyes = false, formatConfirmed = true, formatHint = "",
    )
    private val device = DeviceState(50_000_000_000, 90, true, ThermalLevel.NONE, 8_000_000_000, 12_000_000_000)

    private class Codecs(val hevc: Boolean) : CodecSupport {
        override fun canEncode(codec: OutputCodec, width: Int, height: Int, fps: Double) = codec == OutputCodec.AVC || hevc
        override fun canDecode(codec: OutputCodec, width: Int, height: Int, fps: Double) = true
    }

    private fun plan(hevc: Boolean) = OutputPlanner.plan(
        VideoInfo(3840, 1080, 0, 60_000, 30f, "video/hevc"), VideoFormat(layout = StereoLayout.SIDE_BY_SIDE),
        2.0, true, Codecs(hevc), device,
    )

    @Test fun settingsCarryPlanAndUserChoices() {
        val s = assertNotNull(settingsFor(video, EnhanceDraft(denoise = false, sharpenAmount = 0.2f), plan(hevc = true)))
        assertEquals(7680, s.outWidth); assertEquals(2160, s.outHeight)
        assertEquals("video/hevc", s.outputMime)
        assertEquals("SIDE_BY_SIDE", s.layout)
        assertEquals(false, s.denoise)
        assertTrue(s.bitrate > 0)
        assertNull(s.consentGrantedAtMs, "no consent is ever implied")
    }

    @Test fun avcFallbackNeedsExplicitAcceptance() {
        assertNull(settingsFor(video, EnhanceDraft(preferHevc = true), plan(hevc = false)))
        val s = assertNotNull(settingsFor(video, EnhanceDraft(preferHevc = true, acceptAvc = true), plan(hevc = false)))
        assertEquals("video/avc", s.outputMime)
    }

    @Test fun uploadBackoffGrowsAndIsCapped() {
        assertEquals(1000, CloudClient.backoffMs(1))
        assertEquals(2000, CloudClient.backoffMs(2))
        assertTrue((1..20).map { CloudClient.backoffMs(it) }.zipWithNext().all { (a, b) -> b >= a })
        assertEquals(60_000, CloudClient.backoffMs(20))
    }
}
