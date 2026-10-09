package com.vrvision.app.enhance

import android.content.Context
import android.os.SystemClock
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.vrvision.app.cloud.CloudClient
import com.vrvision.app.data.AppSettings
import com.vrvision.app.data.JobDao
import com.vrvision.app.data.JobEntity
import com.vrvision.core.enhance.FrameUpscaler
import com.vrvision.core.enhance.PreviewSegment
import com.vrvision.core.stereo.StereoLayout
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.random.Random

/** Creates, starts, accepts/rejects and cancels enhancement jobs. */
class JobManager(private val context: Context, private val dao: JobDao, private val settings: AppSettings) {

    private val work get() = WorkManager.getInstance(context)

    fun observe(id: Long): Flow<JobEntity?> = dao.observe(id)
    fun observeAll(): Flow<List<JobEntity>> = dao.observeAll()

    suspend fun startPreview(videoId: Long, durationMs: Long, mode: String, s: EnhanceSettings, previewStartMs: Long): Long {
        val start = PreviewSegment.clampStart(previewStartMs, durationMs)
        val id = dao.insert(
            JobEntity(
                videoId = videoId, mode = mode, isPreview = true, status = JobStatus.QUEUED, settingsJson = s.toJson(),
                previewStartMs = start, previewDurationMs = PreviewSegment.length(durationMs),
            ),
        )
        enqueue(id)
        return id
    }

    /** The user accepted the preview: process the whole video with identical settings. */
    suspend fun acceptPreview(previewJobId: Long): Long {
        val p = dao.get(previewJobId) ?: error("No such job")
        val id = dao.insert(
            JobEntity(
                videoId = p.videoId, mode = p.mode, isPreview = false, status = JobStatus.QUEUED,
                settingsJson = p.settingsJson, cloudJobId = p.cloudJobId,
            ),
        )
        enqueue(id)
        return id
    }

    /** The user rejected the preview: delete it (and any cloud copy) and do not process further. */
    suspend fun rejectPreview(previewJobId: Long) {
        val p = dao.get(previewJobId) ?: return
        p.outputPath?.let { File(it).delete() }
        if (p.mode == JobModes.CLOUD && p.cloudJobId != null) deleteCloudCopy(p.cloudJobId)
        dao.update(p.copy(status = JobStatus.REJECTED, stage = "Preview rejected", outputPath = null))
    }

    suspend fun cancel(id: Long) {
        work.cancelUniqueWork(workName(id))
        val j = dao.get(id) ?: return
        if (j.mode == JobModes.CLOUD && j.cloudJobId != null) deleteCloudCopy(j.cloudJobId)
        if (j.status !in JobStatus.terminal) dao.update(j.copy(status = JobStatus.CANCELLED, stage = "Cancelled", finishedAt = System.currentTimeMillis()))
    }

    private suspend fun deleteCloudCopy(cloudId: String) {
        val prefs = settings.state.value
        val key = settings.cloudApiKey ?: return
        try { CloudClient(prefs.cloudUrl, key).delete(cloudId) } catch (_: Exception) { /* retention policy still applies */ }
    }

    private fun enqueue(id: Long) {
        val req = OneTimeWorkRequestBuilder<EnhanceWorker>().setInputData(workDataOf(EnhanceWorker.KEY_JOB to id)).build()
        work.enqueueUniqueWork(workName(id), ExistingWorkPolicy.KEEP, req)
    }

    private fun workName(id: Long) = "enhance-$id"

    /**
     * Measures real on-device inference speed with the bundled model on random tiles and stores
     * ms per source megapixel (inference only; decode/encode add to the real total, which the
     * preview run measures end to end).
     */
    suspend fun benchmark(registry: ModelRegistry, denoise: Boolean, frameW: Int = 1920, frameH: Int = 1080): Double = withContext(Dispatchers.Default) {
        val model = registry.forDenoise(denoise) ?: throw ModelUnavailableException("No on-device AI model is installed.")
        OrtSrEngine(registry.loadVerified(model)).use { engine ->
            val input = FloatArray(3 * engine.window * engine.window) { Random.nextFloat() }
            engine.run(input) // warm-up
            val n = 4
            val t0 = SystemClock.elapsedRealtime()
            repeat(n) { engine.run(input) }
            val msPerTile = (SystemClock.elapsedRealtime() - t0).toDouble() / n
            val tiles = FrameUpscaler(engine).tileCount(frameW, frameH, StereoLayout.MONO)
            val msPerMp = msPerTile * tiles / (frameW * frameH / 1e6)
            settings.benchmarkMsPerMp = msPerMp.toFloat()
            settings.benchmarkInfo = "inference benchmark (%.0f ms per 128 px tile)".format(msPerTile)
            msPerMp
        }
    }
}
