package com.vrvision.app.browser

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import com.vrvision.app.data.ImportResult
import com.vrvision.app.data.VideoRepository
import com.vrvision.core.browser.DownloadCategory
import com.vrvision.core.media.VideoFormat
import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.StereoLayout
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File

/** A finished download the user wanted to play or enhance, now in the video library. */
data class ImportedDownload(val downloadId: Long, val videoId: Long, val purpose: String)

/**
 * User-confirmed downloads through Android's DownloadManager into the app's private
 * Downloads/VRVision folder. Only the URL is requested: no cookies, credentials or page headers
 * are forwarded, so files that need a login can't be fetched (by design).
 */
class BrowserDownloads(
    private val context: Context,
    private val dao: BrowserDao,
    private val videos: VideoRepository,
    private val scope: CoroutineScope,
) {
    private val dm = context.getSystemService(DownloadManager::class.java)
    private var poller: Job? = null
    private val _imported = MutableSharedFlow<ImportedDownload>(extraBufferCapacity = 4)
    val imported: SharedFlow<ImportedDownload> = _imported

    fun all(): Flow<List<DownloadEntity>> = dao.downloads()

    /** Must only be called after the user confirmed a [com.vrvision.core.browser.DownloadDecision.Confirm]. */
    suspend fun enqueue(
        url: String, fileName: String, mimeType: String?, category: DownloadCategory,
        purpose: String = "NONE", format: VideoFormat? = null,
    ): Long {
        val req = DownloadManager.Request(Uri.parse(url))
            .setTitle(fileName)
            .setDescription("VRVision download")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, "VRVision/$fileName")
            .setAllowedOverMetered(true)
        mimeType?.let { req.setMimeType(it) }
        val systemId = dm.enqueue(req)
        val id = dao.addDownload(
            DownloadEntity(
                systemId = systemId, url = url, fileName = fileName, mimeType = mimeType, category = category.name,
                status = "RUNNING", purpose = purpose, layout = format?.layout?.name, projection = format?.projection?.name,
            ),
        )
        ensurePolling()
        return id
    }

    fun cancel(d: DownloadEntity) {
        dm.remove(d.systemId)
        scope.launch { dao.updateDownload(d.copy(status = "CANCELLED")) }
    }

    fun ensurePolling() {
        if (poller?.isActive == true) return
        poller = scope.launch {
            while (isActive) {
                val active = dao.activeDownloads()
                if (active.isEmpty()) break
                active.forEach { refresh(it) }
                delay(1000)
            }
        }
    }

    private suspend fun refresh(d: DownloadEntity) {
        val q = DownloadManager.Query().setFilterById(d.systemId)
        val row = dm.query(q)?.use { c ->
            if (!c.moveToFirst()) null else Triple(
                c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)),
                c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)) to
                    c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)),
                c.getString(c.getColumnIndexOrThrow(DownloadManager.COLUMN_LOCAL_URI)) to
                    c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON)),
            )
        }
        if (row == null) { dao.updateDownload(d.copy(status = "CANCELLED")); return }
        val (status, bytes, extra) = row
        val updated = when (status) {
            DownloadManager.STATUS_SUCCESSFUL -> d.copy(status = "SUCCESSFUL", bytesDone = bytes.first, bytesTotal = bytes.second, localPath = extra.first?.let { Uri.parse(it).path })
            DownloadManager.STATUS_FAILED -> d.copy(status = "FAILED", failure = failureText(extra.second))
            else -> d.copy(status = "RUNNING", bytesDone = bytes.first, bytesTotal = bytes.second)
        }
        dao.updateDownload(updated)
        if (updated.status == "SUCCESSFUL" && updated.category == DownloadCategory.VIDEO.name && updated.purpose != "NONE") importToLibrary(updated)
    }

    /** Adds a finished video download to the library with the format the user confirmed. */
    suspend fun importToLibrary(d: DownloadEntity): Long? {
        d.importedVideoId?.let { return it }
        val file = d.localPath?.let { File(it) } ?: return null
        val result = videos.import(Uri.fromFile(file))
        val videoId = (result as? ImportResult.Imported)?.id ?: run {
            dao.updateDownload(d.copy(failure = (result as? ImportResult.Failed)?.reason ?: "Import failed"))
            return null
        }
        if (d.layout != null && d.projection != null) {
            videos.setFormat(
                videoId,
                VideoFormat(
                    layout = StereoLayout.entries.firstOrNull { it.name == d.layout } ?: StereoLayout.MONO,
                    projection = ProjectionType.entries.firstOrNull { it.name == d.projection } ?: ProjectionType.FLAT,
                ),
            )
        }
        dao.updateDownload(d.copy(importedVideoId = videoId))
        _imported.tryEmit(ImportedDownload(d.id, videoId, d.purpose))
        return videoId
    }

    /** Removes download records and downloaded files, except files already imported into the library. */
    suspend fun clearAll() {
        val all = dao.allDownloads()
        all.filter { it.status == "RUNNING" || it.status == "PENDING" }.forEach { dm.remove(it.systemId) }
        val keep = all.filter { it.importedVideoId != null }.mapNotNull { it.localPath }.toSet()
        File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "VRVision").listFiles()
            ?.filter { it.isFile && it.path !in keep }?.forEach { it.delete() }
        dao.clearDownloads()
    }

    private fun failureText(reason: Int): String = when (reason) {
        DownloadManager.ERROR_INSUFFICIENT_SPACE -> "Not enough storage."
        DownloadManager.ERROR_HTTP_DATA_ERROR, DownloadManager.ERROR_UNHANDLED_HTTP_CODE ->
            "The server refused the download (it may require a login or block downloads)."
        DownloadManager.ERROR_TOO_MANY_REDIRECTS -> "Too many redirects."
        DownloadManager.ERROR_CANNOT_RESUME -> "The download was interrupted and can't be resumed."
        in 400..599 -> "The server answered HTTP $reason (login required, forbidden or unavailable)."
        else -> "Download failed ($reason)."
    }
}
