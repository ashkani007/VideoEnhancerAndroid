package com.vrvision.app.data

import android.content.Context
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.provider.OpenableColumns
import com.vrvision.core.media.AudioTrackInfo
import com.vrvision.core.media.VideoInfo

class UnreadableVideoException(message: String, cause: Throwable? = null) : Exception(message, cause)

/** Reads technical metadata without decoding frames. */
class MetadataReader(private val context: Context) {

    data class Result(val info: VideoInfo, val displayName: String)

    fun read(uri: Uri): Result {
        val name = displayName(uri)
        val extractor = MediaExtractor()
        val retriever = MediaMetadataRetriever()
        try {
            try {
                extractor.setDataSource(context, uri, null)
            } catch (e: Exception) {
                throw UnreadableVideoException("The file could not be opened as a video container.", e)
            }
            var video: MediaFormat? = null
            val audio = mutableListOf<AudioTrackInfo>()
            var subtitles = 0
            for (i in 0 until extractor.trackCount) {
                val f = extractor.getTrackFormat(i)
                val mime = f.getString(MediaFormat.KEY_MIME) ?: continue
                when {
                    mime.startsWith("video/") && video == null -> video = f
                    mime.startsWith("audio/") -> audio += AudioTrackInfo(
                        mime = mime,
                        channels = f.intOrNull(MediaFormat.KEY_CHANNEL_COUNT),
                        sampleRate = f.intOrNull(MediaFormat.KEY_SAMPLE_RATE),
                        language = if (f.containsKey(MediaFormat.KEY_LANGUAGE)) f.getString(MediaFormat.KEY_LANGUAGE) else null,
                    )
                    mime.startsWith("text/") || mime == "application/x-subrip" || mime.contains("ttml") || mime.contains("vtt") -> subtitles++
                }
            }
            val v = video ?: throw UnreadableVideoException("No video track found.")

            try { retriever.setDataSource(context, uri) } catch (_: Exception) { /* optional extras only */ }
            fun meta(key: Int): String? = try { retriever.extractMetadata(key) } catch (_: Exception) { null }

            val width = v.intOrNull(MediaFormat.KEY_WIDTH) ?: meta(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull() ?: 0
            val height = v.intOrNull(MediaFormat.KEY_HEIGHT) ?: meta(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull() ?: 0
            if (width <= 0 || height <= 0) throw UnreadableVideoException("Video dimensions are missing or invalid.")
            val durationUs = v.longOrNull(MediaFormat.KEY_DURATION)
            val durationMs = durationUs?.div(1000) ?: meta(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
            val rotation = meta(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toIntOrNull()
                ?: v.intOrNull(MediaFormat.KEY_ROTATION) ?: 0

            val frameRate = v.numberOrNull(MediaFormat.KEY_FRAME_RATE)?.toFloat()
                ?: run {
                    val frames = meta(MediaMetadataRetriever.METADATA_KEY_VIDEO_FRAME_COUNT)?.toLongOrNull()
                    if (frames != null && durationMs > 0) frames * 1000f / durationMs else null
                }
            val mime = v.getString(MediaFormat.KEY_MIME)
            val profile = v.intOrNull(MediaFormat.KEY_PROFILE)
            val transfer = v.intOrNull(MediaFormat.KEY_COLOR_TRANSFER)
            val hdr = transfer?.let { it == MediaFormat.COLOR_TRANSFER_ST2084 || it == MediaFormat.COLOR_TRANSFER_HLG }

            return Result(
                info = VideoInfo(
                    width = width,
                    height = height,
                    rotationDegrees = rotation,
                    durationMs = durationMs,
                    frameRate = frameRate,
                    videoMime = mime,
                    codecProfile = profileName(mime, profile),
                    bitDepth = bitDepth(mime, profile, hdr),
                    bitrate = meta(MediaMetadataRetriever.METADATA_KEY_BITRATE)?.toLongOrNull(),
                    audioTracks = audio,
                    subtitleTrackCount = subtitles,
                    sizeBytes = fileSize(uri),
                    hdr = hdr,
                ),
                displayName = name,
            )
        } finally {
            extractor.release()
            try { retriever.release() } catch (_: Exception) { }
        }
    }

    private fun displayName(uri: Uri): String =
        if (uri.scheme == "file") uri.lastPathSegment ?: "video" else context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) c.getString(0) else null
        } ?: uri.lastPathSegment ?: "video"

    private fun fileSize(uri: Uri): Long? =
        if (uri.scheme == "file") uri.path?.let { java.io.File(it).length() } else context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { c ->
            if (c.moveToFirst() && !c.isNull(0)) c.getLong(0) else null
        }

    private fun profileName(mime: String?, profile: Int?): String? {
        if (profile == null) return null
        return when (mime) {
            MediaFormat.MIMETYPE_VIDEO_HEVC -> when (profile) {
                MediaCodecInfo.CodecProfileLevel.HEVCProfileMain -> "Main"
                MediaCodecInfo.CodecProfileLevel.HEVCProfileMain10 -> "Main 10"
                MediaCodecInfo.CodecProfileLevel.HEVCProfileMain10HDR10 -> "Main 10 HDR10"
                MediaCodecInfo.CodecProfileLevel.HEVCProfileMain10HDR10Plus -> "Main 10 HDR10+"
                else -> "Profile $profile"
            }
            MediaFormat.MIMETYPE_VIDEO_AVC -> when (profile) {
                MediaCodecInfo.CodecProfileLevel.AVCProfileBaseline -> "Baseline"
                MediaCodecInfo.CodecProfileLevel.AVCProfileMain -> "Main"
                MediaCodecInfo.CodecProfileLevel.AVCProfileHigh -> "High"
                MediaCodecInfo.CodecProfileLevel.AVCProfileHigh10 -> "High 10"
                else -> "Profile $profile"
            }
            else -> "Profile $profile"
        }
    }

    /** Bit depth inferred from the codec profile; null when not determinable. */
    private fun bitDepth(mime: String?, profile: Int?, hdr: Boolean?): Int? = when {
        mime == MediaFormat.MIMETYPE_VIDEO_HEVC && profile != null ->
            if (profile == MediaCodecInfo.CodecProfileLevel.HEVCProfileMain) 8 else 10
        mime == MediaFormat.MIMETYPE_VIDEO_AVC && profile != null ->
            if (profile == MediaCodecInfo.CodecProfileLevel.AVCProfileHigh10) 10 else 8
        hdr == true -> 10
        else -> null
    }
}

private fun MediaFormat.intOrNull(key: String): Int? = if (containsKey(key)) try { getInteger(key) } catch (_: Exception) { null } else null
private fun MediaFormat.longOrNull(key: String): Long? = if (containsKey(key)) try { getLong(key) } catch (_: Exception) { null } else null
private fun MediaFormat.numberOrNull(key: String): Number? = if (!containsKey(key)) null else
    try { getInteger(key) } catch (_: Exception) { try { getFloat(key) } catch (_: Exception) { null } }
