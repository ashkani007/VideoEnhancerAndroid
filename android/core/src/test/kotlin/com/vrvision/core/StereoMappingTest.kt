package com.vrvision.core

import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.Eye
import com.vrvision.core.stereo.FormatHints
import com.vrvision.core.stereo.StereoLayout
import com.vrvision.core.stereo.StereoMapper
import com.vrvision.core.stereo.StereoPacking
import com.vrvision.core.stereo.UvRect
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class StereoMappingTest {

    @Test fun monoUsesWholeFrameForBothEyes() {
        for (swap in listOf(false, true)) {
            assertEquals(UvRect.FULL, StereoMapper.eyeRect(StereoLayout.MONO, Eye.LEFT, swap))
            assertEquals(UvRect.FULL, StereoMapper.eyeRect(StereoLayout.MONO, Eye.RIGHT, swap))
        }
    }

    @Test fun sideBySideLeftEyeSamplesLeftHalf() {
        assertEquals(UvRect(0f, 0f, 0.5f, 1f), StereoMapper.eyeRect(StereoLayout.SIDE_BY_SIDE, Eye.LEFT, false))
        assertEquals(UvRect(0.5f, 0f, 1f, 1f), StereoMapper.eyeRect(StereoLayout.SIDE_BY_SIDE, Eye.RIGHT, false))
    }

    @Test fun topBottomLeftEyeSamplesTopHalf() {
        assertEquals(UvRect(0f, 0f, 1f, 0.5f), StereoMapper.eyeRect(StereoLayout.TOP_BOTTOM, Eye.LEFT, false))
        assertEquals(UvRect(0f, 0.5f, 1f, 1f), StereoMapper.eyeRect(StereoLayout.TOP_BOTTOM, Eye.RIGHT, false))
    }

    @Test fun swapExchangesEyesExactly() {
        for (layout in listOf(StereoLayout.SIDE_BY_SIDE, StereoLayout.TOP_BOTTOM)) {
            assertEquals(StereoMapper.eyeRect(layout, Eye.RIGHT, false), StereoMapper.eyeRect(layout, Eye.LEFT, true))
            assertEquals(StereoMapper.eyeRect(layout, Eye.LEFT, false), StereoMapper.eyeRect(layout, Eye.RIGHT, true))
        }
    }

    @Test fun eyeRectsNeverOverlapAndCoverFrame() {
        for (layout in listOf(StereoLayout.SIDE_BY_SIDE, StereoLayout.TOP_BOTTOM)) {
            val l = StereoMapper.eyeRect(layout, Eye.LEFT, false)
            val r = StereoMapper.eyeRect(layout, Eye.RIGHT, false)
            assertEquals(1f, l.width * l.height + r.width * r.height, 1e-6f)
            val overlapW = minOf(l.u1, r.u1) - maxOf(l.u0, r.u0)
            val overlapH = minOf(l.v1, r.v1) - maxOf(l.v0, r.v0)
            assertTrue(overlapW <= 0f || overlapH <= 0f)
        }
    }

    @Test fun eyeLocalCoordinatesMapIntoTheCorrectHalf() {
        val right = StereoMapper.eyeRect(StereoLayout.SIDE_BY_SIDE, Eye.RIGHT, false)
        assertEquals(Pair(0.75f, 0.5f), right.map(0.5f, 0.5f))
        val bottom = StereoMapper.eyeRect(StereoLayout.TOP_BOTTOM, Eye.RIGHT, false)
        assertEquals(Pair(0.5f, 0.75f), bottom.map(0.5f, 0.5f))
    }

    @Test fun aspectRatios() {
        // Half SBS 1920x1080: each eye squeezed to 960x1080 but represents 16:9.
        assertEquals(16f / 9f, StereoMapper.eyeAspect(1920, 1080, StereoLayout.SIDE_BY_SIDE, StereoPacking.HALF), 1e-4f)
        // Full SBS 3840x1080: each eye is 1920x1080.
        assertEquals(16f / 9f, StereoMapper.eyeAspect(3840, 1080, StereoLayout.SIDE_BY_SIDE, StereoPacking.FULL), 1e-4f)
        // Full TB 1920x2160: each eye is 1920x1080.
        assertEquals(16f / 9f, StereoMapper.eyeAspect(1920, 2160, StereoLayout.TOP_BOTTOM, StereoPacking.FULL), 1e-4f)
        assertEquals(16f / 9f, StereoMapper.eyeAspect(1920, 1080, StereoLayout.MONO, StereoPacking.FULL), 1e-4f)
        assertEquals(Pair(2880, 2880), StereoMapper.eyePixelSize(5760, 2880, StereoLayout.SIDE_BY_SIDE))
    }

    @Test fun formatHintsFromName() {
        val s = FormatHints.suggest("Trip_VR180_SBS.mp4", 5760, 2880)
        assertEquals(StereoLayout.SIDE_BY_SIDE, s.layout)
        assertEquals(ProjectionType.EQUIRECT_180, s.projection)
        assertTrue(s.confident)

        val tb = FormatHints.suggest("concert_360_TB.mp4", 3840, 3840)
        assertEquals(StereoLayout.TOP_BOTTOM, tb.layout)
        assertEquals(ProjectionType.EQUIRECT_360, tb.projection)
    }

    @Test fun formatHintsWithoutNameAreNotConfident() {
        val s = FormatHints.suggest("video.mp4", 4096, 2048)
        assertFalse(s.confident)
        assertTrue(s.reasons.isNotEmpty())
        val flat = FormatHints.suggest("holiday.mp4", 1920, 1080)
        assertEquals(StereoLayout.MONO, flat.layout)
        assertEquals(ProjectionType.FLAT, flat.projection)
    }
}
