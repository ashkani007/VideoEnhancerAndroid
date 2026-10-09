package com.vrvision.core.media

import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.StereoLayout
import com.vrvision.core.stereo.StereoPacking

/** Technical metadata read from the container/codec. Null means "not detectable". */
data class VideoInfo(
    val width: Int,
    val height: Int,
    val rotationDegrees: Int = 0,
    val durationMs: Long,
    val frameRate: Float?,
    val videoMime: String?,
    val codecProfile: String? = null,
    val bitDepth: Int? = null,
    val bitrate: Long? = null,
    val audioTracks: List<AudioTrackInfo> = emptyList(),
    val subtitleTrackCount: Int = 0,
    val sizeBytes: Long? = null,
    val hdr: Boolean? = null,
) {
    /** Width/height as displayed, after applying the container rotation. */
    val displayWidth: Int get() = if (rotationDegrees % 180 != 0) height else width
    val displayHeight: Int get() = if (rotationDegrees % 180 != 0) width else height
    val pixelCount: Long get() = width.toLong() * height

    val codecLabel: String
        get() = when (videoMime) {
            "video/avc" -> "H.264 / AVC"
            "video/hevc" -> "H.265 / HEVC"
            "video/av01" -> "AV1"
            "video/x-vnd.on2.vp9" -> "VP9"
            "video/x-vnd.on2.vp8" -> "VP8"
            "video/mp4v-es" -> "MPEG-4 Part 2"
            null -> "Unknown"
            else -> videoMime
        }
}

data class AudioTrackInfo(
    val mime: String?,
    val channels: Int?,
    val sampleRate: Int?,
    val language: String?,
)

/** The user's confirmed interpretation of a video file. */
data class VideoFormat(
    val layout: StereoLayout = StereoLayout.MONO,
    val packing: StereoPacking = StereoPacking.HALF,
    val projection: ProjectionType = ProjectionType.FLAT,
    val swapEyes: Boolean = false,
)
