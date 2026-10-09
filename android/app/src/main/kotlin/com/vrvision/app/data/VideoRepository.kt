package com.vrvision.app.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.vrvision.core.media.AudioTrackInfo
import com.vrvision.core.media.VideoFormat
import com.vrvision.core.media.VideoInfo
import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.FormatHints
import com.vrvision.core.stereo.StereoLayout
import com.vrvision.core.stereo.StereoPacking
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import java.io.File

sealed interface ImportResult {
    data class Imported(val id: Long, val alreadyInLibrary: Boolean) : ImportResult
    data class Failed(val reason: String) : ImportResult
}

class VideoRepository(
    private val context: Context,
    private val dao: VideoDao,
    private val reader: MetadataReader = MetadataReader(context),
) {
    fun originals(): Flow<List<VideoEntity>> = dao.observeByKind(VideoEntity.KIND_ORIGINAL)
    fun enhanced(): Flow<List<VideoEntity>> = dao.observeByKind(VideoEntity.KIND_ENHANCED)
    fun observe(id: Long): Flow<VideoEntity?> = dao.observe(id)
    suspend fun get(id: Long): VideoEntity? = dao.get(id)

    /**
     * Imports a document chosen through the Storage Access Framework. The file stays where it
     * is; only its URI and metadata are stored. Persistable read access is requested so the
     * video can be opened after a restart.
     */
    suspend fun import(uri: Uri): ImportResult = withContext(Dispatchers.IO) {
        dao.findByUri(uri.toString())?.let { return@withContext ImportResult.Imported(it.id, true) }
        try {
            context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (_: Exception) {
            // Provider does not offer persistable grants (or it's an app-private file); access
            // lasts for this session only.
        }
        val result = try {
            reader.read(uri)
        } catch (e: UnreadableVideoException) {
            return@withContext ImportResult.Failed(e.message ?: "Unreadable video")
        } catch (e: Exception) {
            return@withContext ImportResult.Failed("Could not read this file: ${e.javaClass.simpleName}")
        }
        val info = result.info
        val hint = FormatHints.suggest(result.displayName, info.displayWidth, info.displayHeight)
        val id = dao.insert(
            info.toEntity(uri.toString(), result.displayName).copy(
                layout = hint.layout.name,
                projection = hint.projection.name,
                formatConfirmed = false,
                formatHint = hint.reasons.joinToString(" "),
            ),
        )
        ImportResult.Imported(id, false)
    }

    /** Stores the user's confirmed stereo/projection interpretation. */
    suspend fun setFormat(id: Long, format: VideoFormat) {
        val v = dao.get(id) ?: return
        dao.update(
            v.copy(
                layout = format.layout.name, packing = format.packing.name,
                projection = format.projection.name, swapEyes = format.swapEyes, formatConfirmed = true,
            ),
        )
    }

    suspend fun savePosition(id: Long, positionMs: Long) = dao.savePosition(id, positionMs)

    /** Registers an enhanced output file produced by the app. */
    suspend fun addEnhanced(file: File, source: VideoEntity, enhancementJson: String): Long {
        val uri = Uri.fromFile(file)
        val read = reader.read(uri)
        return dao.insert(
            read.info.toEntity(uri.toString(), file.name).copy(
                layout = source.layout, packing = source.packing, projection = source.projection,
                swapEyes = source.swapEyes, formatConfirmed = true, formatHint = "Inherited from source",
                kind = VideoEntity.KIND_ENHANCED, sourceVideoId = source.id, enhancementJson = enhancementJson,
                sizeBytes = file.length(),
            ),
        )
    }

    /** Removes from the library. Imported originals are never deleted from the device. */
    suspend fun remove(id: Long) = withContext(Dispatchers.IO) {
        val v = dao.get(id) ?: return@withContext
        if (v.kind == VideoEntity.KIND_ENHANCED) {
            Uri.parse(v.uri).path?.let { p -> File(p).takeIf { it.startsWith(context.getExternalFilesDir(null) ?: context.filesDir) || it.startsWith(context.filesDir) }?.delete() }
        } else {
            try {
                context.contentResolver.releasePersistableUriPermission(Uri.parse(v.uri), Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (_: Exception) { }
        }
        dao.delete(id)
    }
}

fun VideoInfo.toEntity(uri: String, name: String) = VideoEntity(
    uri = uri, displayName = name, sizeBytes = sizeBytes, width = width, height = height,
    rotationDegrees = rotationDegrees, durationMs = durationMs, frameRate = frameRate, videoMime = videoMime,
    codecProfile = codecProfile, bitDepth = bitDepth, bitrate = bitrate, hdr = hdr,
    audioSummary = audioTracks.joinToString { "${it.mime?.removePrefix("audio/") ?: "?"} ${it.channels ?: "?"}ch ${it.sampleRate ?: "?"}Hz" },
    audioTrackCount = audioTracks.size, subtitleTrackCount = subtitleTrackCount,
    layout = StereoLayout.MONO.name, packing = StereoPacking.HALF.name, projection = ProjectionType.FLAT.name,
    swapEyes = false, formatConfirmed = false, formatHint = "",
)

fun VideoEntity.toInfo() = VideoInfo(
    width = width, height = height, rotationDegrees = rotationDegrees, durationMs = durationMs,
    frameRate = frameRate, videoMime = videoMime, codecProfile = codecProfile, bitDepth = bitDepth,
    bitrate = bitrate, audioTracks = List(audioTrackCount) { AudioTrackInfo(null, null, null, null) },
    subtitleTrackCount = subtitleTrackCount, sizeBytes = sizeBytes, hdr = hdr,
)

fun VideoEntity.toFormat() = VideoFormat(
    layout = enumOr(layout, StereoLayout.MONO),
    packing = enumOr(packing, StereoPacking.HALF),
    projection = enumOr(projection, ProjectionType.FLAT),
    swapEyes = swapEyes,
)

inline fun <reified T : Enum<T>> enumOr(name: String, default: T): T =
    enumValues<T>().firstOrNull { it.name == name } ?: default
