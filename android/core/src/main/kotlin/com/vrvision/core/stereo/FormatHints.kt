package com.vrvision.core.stereo

import com.vrvision.core.projection.ProjectionType

/**
 * A *suggestion* for the stereo layout and projection of a file.
 *
 * Stereo layout cannot be reliably detected from pixels or container metadata in
 * general, so the app shows this as a pre-selected hint with its [reasons] and
 * always lets the user confirm or change it. It is never applied silently to a file
 * the user has already configured.
 */
data class FormatSuggestion(
    val layout: StereoLayout,
    val projection: ProjectionType,
    val confident: Boolean,
    val reasons: List<String>,
)

object FormatHints {

    private val sbsTokens = listOf("sbs", "_lr", "-lr", ".lr", "3dh", "half-sbs", "hsbs", "fsbs", "_3d_lr")
    private val tbTokens = listOf("_tb", "-tb", ".tb", "_ou", "-ou", "overunder", "over-under", "3dv", "htab", "top-bottom", "topbottom")
    private val vr180Tokens = listOf("180", "vr180", "_180x180", "fisheye180")
    private val vr360Tokens = listOf("360", "vr360", "_360x180", "equirect")

    fun suggest(fileName: String, width: Int, height: Int): FormatSuggestion {
        val name = fileName.lowercase()
        val reasons = mutableListOf<String>()
        val aspect = if (height > 0) width.toFloat() / height else 0f

        var layout = StereoLayout.MONO
        var layoutFromName = false
        when {
            sbsTokens.any { name.contains(it) } -> {
                layout = StereoLayout.SIDE_BY_SIDE; layoutFromName = true
                reasons += "File name contains a side-by-side tag."
            }
            tbTokens.any { name.contains(it) } -> {
                layout = StereoLayout.TOP_BOTTOM; layoutFromName = true
                reasons += "File name contains a top-bottom tag."
            }
        }

        var projection = ProjectionType.FLAT
        var projectionFromName = false
        when {
            vr360Tokens.any { name.contains(it) } -> {
                projection = ProjectionType.EQUIRECT_360; projectionFromName = true
                reasons += "File name suggests 360° video."
            }
            vr180Tokens.any { name.contains(it) } -> {
                projection = ProjectionType.EQUIRECT_180; projectionFromName = true
                reasons += "File name suggests VR180 video."
            }
        }

        if (!layoutFromName && !projectionFromName && aspect > 0f) {
            // Aspect heuristics only; weak evidence.
            when {
                // 2:1 is typical for both mono 360 and SBS 180 (two 1:1 eyes).
                kotlin.math.abs(aspect - 2f) < 0.02f -> {
                    layout = StereoLayout.SIDE_BY_SIDE
                    projection = ProjectionType.EQUIRECT_180
                    reasons += "2:1 frame is common for side-by-side VR180, but also for mono 360°."
                }
                kotlin.math.abs(aspect - 1f) < 0.02f -> {
                    layout = StereoLayout.TOP_BOTTOM
                    projection = ProjectionType.EQUIRECT_360
                    reasons += "1:1 frame is common for top-bottom 360°."
                }
                aspect > 3.2f -> {
                    layout = StereoLayout.SIDE_BY_SIDE
                    reasons += "Very wide frame is common for full side-by-side 3D."
                }
                else -> reasons += "No stereo hints found; assuming flat 2D."
            }
        }

        return FormatSuggestion(
            layout = layout,
            projection = projection,
            confident = layoutFromName || projectionFromName,
            reasons = reasons,
        )
    }
}
