package com.vrvision.app.enhance

import android.app.Notification
import android.content.Context
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import com.vrvision.app.R
import com.vrvision.app.VRVisionApp
import com.vrvision.app.cloud.CloudClient
import com.vrvision.app.cloud.CloudException
import com.vrvision.app.data.JobEntity
import com.vrvision.app.data.VideoEntity
import com.vrvision.core.stereo.StereoLayout
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import org.json.JSONObject
import java.io.File

/**
 * Runs one enhancement job (preview or full; local AI, local conventional, or cloud) as a
 * user-visible foreground job so Android does not kill long processing.
 */
class EnhanceWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {

    private val container = (appContext as VRVisionApp).container
    private val jobs = container.database.jobs()

    override suspend fun doWork(): Result {
        val jobId = inputData.getLong(KEY_JOB, -1)
        val job = jobs.get(jobId) ?: return Result.failure()
        if (job.status in JobStatus.terminal) return Result.success()
        val video = container.videos.get(job.videoId) ?: return fail(job, JobStatus.FAILED, "The source video is no longer in the library.")
        try { setForeground(foreground(job, 0f, "Starting")) } catch (_: Exception) { /* notification permission denied: work still runs */ }
        jobs.update(job.copy(status = JobStatus.RUNNING, startedAt = job.startedAt ?: System.currentTimeMillis(), message = ""))
        val settings = EnhanceSettings.fromJson(job.settingsJson)
        return try {
            when (job.mode) {
                JobModes.LOCAL_AI -> runLocalAi(job, video, settings)
                JobModes.LOCAL_CONVENTIONAL -> runConventional(job, video, settings)
                JobModes.CLOUD -> runCloud(job, video, settings)
                else -> fail(job, JobStatus.FAILED, "Unknown mode ${job.mode}")
            }
        } catch (e: CancellationException) {
            jobs.get(jobId)?.let { if (it.status !in JobStatus.terminal) jobs.update(it.copy(status = JobStatus.CANCELLED, finishedAt = System.currentTimeMillis(), stage = "Cancelled")) }
            throw e
        } catch (e: UnsupportedProcessingException) {
            fail(job, JobStatus.UNSUPPORTED, e.message ?: "Not supported on this phone")
        } catch (e: ModelUnavailableException) {
            fail(job, JobStatus.UNSUPPORTED, e.message ?: "Model unavailable")
        } catch (e: CloudException) {
            fail(job, JobStatus.FAILED, "Cloud: ${e.message}")
        } catch (e: Exception) {
            fail(job, JobStatus.FAILED, "${e.javaClass.simpleName}: ${e.message}")
        }
    }

    private suspend fun progress(job: JobEntity, fraction: Float, stage: String) {
        jobs.progress(job.id, fraction.coerceIn(0f, 1f), stage)
        try { setForeground(foreground(job, fraction, stage)) } catch (_: Exception) { }
    }

    private fun previewFile(job: JobEntity) = File(applicationContext.filesDir, "previews/job_${job.id}.mp4")

    private fun fullFile(video: VideoEntity, s: EnhanceSettings): File {
        val dir = applicationContext.getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: applicationContext.filesDir
        val base = video.displayName.substringBeforeLast('.').replace(Regex("[^A-Za-z0-9._-]"), "_").take(60)
        return File(dir, "VRVision/${base}_${s.outWidth}x${s.outHeight}_${System.currentTimeMillis()}.mp4")
    }

    private suspend fun runLocalAi(job: JobEntity, video: VideoEntity, s: EnhanceSettings): Result {
        val registry = ModelRegistry(applicationContext)
        val model = registry.forDenoise(s.denoise) ?: throw ModelUnavailableException("No on-device AI model is installed.")
        val bytes = registry.loadVerified(model)
        val out = if (job.isPreview) previewFile(job) else fullFile(video, s)
        val started = SystemClock.elapsedRealtime()
        val result = OrtSrEngine(bytes).use { engine ->
            LocalEnhancer(applicationContext, engine).run(
                LocalRequest(
                    source = Uri.parse(video.uri),
                    startUs = if (job.isPreview) job.previewStartMs * 1000 else 0,
                    endUs = if (job.isPreview) (job.previewStartMs + job.previewDurationMs) * 1000 else Long.MAX_VALUE,
                    outWidth = s.outWidth, outHeight = s.outHeight,
                    layout = StereoLayout.entries.firstOrNull { it.name == s.layout } ?: StereoLayout.MONO,
                    outputMime = s.outputMime, bitrate = s.bitrate,
                    sharpenAmount = if (s.sharpen) s.sharpenAmount else 0f,
                    output = out,
                ),
            ) { p -> progress(job, p.framesDone.toFloat() / p.framesExpected, p.stage) }
        }
        val elapsed = SystemClock.elapsedRealtime() - started
        if (job.isPreview) container.settings.let {
            it.benchmarkMsPerMp = result.msPerSourceMegapixel.toFloat()
            it.benchmarkInfo = "measured on the last local preview"
        }
        val json = JSONObject()
            .put("type", "AI super resolution (Real-ESRGAN)")
            .put("model", model.name).put("modelVersion", model.version).put("modelSha256", model.sha256)
            .put("denoise", model.denoiseLabel).put("runtime", model.runtime)
            .put("sharpen", if (s.sharpen) "Conventional unsharp mask ${s.sharpenAmount}" else "Off")
            .put("source", "${video.width}x${video.height}").put("output", "${s.outWidth}x${s.outHeight}")
            .put("codec", s.outputMime).put("framesIn", result.framesIn).put("framesOut", result.framesOut)
            .put("elapsedMs", elapsed).put("msPerSourceMegapixel", result.msPerSourceMegapixel)
            .put("audio", if (result.audioRemuxed) "Original AAC copied" else (result.audioNote ?: "None"))
            .put("outputBytes", out.length())
            .put("validation", JSONObject().put("ok", result.validation.ok).put("problems", result.validation.problems.joinToString("; ")))
        if (!result.validation.ok) {
            out.delete()
            return fail(job, JobStatus.FAILED, "Output failed validation: ${result.validation.problems.joinToString("; ")}")
        }
        return finish(job, video, out, json)
    }

    private suspend fun runConventional(job: JobEntity, video: VideoEntity, s: EnhanceSettings): Result {
        val out = if (job.isPreview) previewFile(job) else fullFile(video, s)
        val started = SystemClock.elapsedRealtime()
        ConventionalUpscaler(applicationContext).run(
            Uri.parse(video.uri), if (job.isPreview) job.previewStartMs else 0,
            if (job.isPreview) job.previewStartMs + job.previewDurationMs else null,
            s.outWidth, s.outHeight, s.outputMime, s.bitrate, out,
        ) { pct -> progress(job, pct / 100f, "Conventional Lanczos upscaling ($pct%)") }
        val validation = OutputValidator.validate(applicationContext, out, s.outWidth, s.outHeight, s.outputMime, -1, -1, expectAudio = false)
        val json = JSONObject()
            .put("type", "Conventional upscaling (Lanczos, not AI)")
            .put("source", "${video.width}x${video.height}").put("output", "${validation.width}x${validation.height}")
            .put("codec", validation.videoMime).put("elapsedMs", SystemClock.elapsedRealtime() - started).put("outputBytes", out.length())
            .put("validation", JSONObject().put("ok", validation.width == s.outWidth && validation.height == s.outHeight && validation.firstFrameDecodes))
        if (validation.width != s.outWidth || validation.height != s.outHeight || !validation.firstFrameDecodes) {
            out.delete()
            return fail(job, JobStatus.FAILED, "Output failed validation: ${validation.problems.joinToString("; ")}")
        }
        return finish(job, video, out, json)
    }

    private suspend fun runCloud(job: JobEntity, video: VideoEntity, s: EnhanceSettings): Result {
        val prefs = container.settings.state.value
        val key = container.settings.cloudApiKey
        if (!prefs.cloudEnabled || prefs.privacyLocalOnly || prefs.cloudUrl.isBlank() || key.isNullOrBlank()) {
            return fail(job, JobStatus.FAILED, "Cloud processing is not configured or was disabled.")
        }
        val consentAt = s.consentGrantedAtMs ?: return fail(job, JobStatus.FAILED, "No upload consent recorded; nothing was uploaded.")
        val client = CloudClient(prefs.cloudUrl, key)
        val resolver = applicationContext.contentResolver
        val uri = Uri.parse(video.uri)
        var cloudId = job.cloudJobId

        if (cloudId == null) {
            progress(job, 0f, "Computing checksum")
            val size = video.sizeBytes ?: throw CloudException("File size unknown; cannot upload.")
            val body = JSONObject()
                .put("consent", CloudClient.consentJson(consentAt, s.consentTextVersion ?: CloudClient.CONSENT_TEXT_VERSION))
                .put("file_name", video.displayName).put("size_bytes", size).put("sha256", CloudClient.sha256(resolver, uri))
                .put("width", video.width).put("height", video.height).put("fps", (video.frameRate ?: 30f).toDouble())
                .put("duration_ms", video.durationMs).put("layout", s.layout).put("projection", s.projection)
                .put("out_width", s.outWidth).put("out_height", s.outHeight).put("denoise", s.denoise)
                .put("sharpen_amount", if (s.sharpen) s.sharpenAmount.toDouble() else 0.0)
                .put("preview_start_ms", job.previewStartMs)
            cloudId = client.createJob(body)
            jobs.update(jobs.get(job.id)!!.copy(cloudJobId = cloudId))
            client.upload(resolver, uri, size, cloudId, 4 * 1024 * 1024) { sent -> progress(job, 0.3f * sent / size, "Uploading ${sent / 1_000_000} / ${size / 1_000_000} MB") }
            client.completeUpload(cloudId)
        } else if (!job.isPreview) {
            client.startFull(cloudId)
        }

        // Poll until the server finishes this phase.
        val wanted = if (job.isPreview) "PREVIEW_READY" else "SUCCEEDED"
        val deadline = SystemClock.elapsedRealtime() + 8 * 3600_000L
        var cj = client.job(cloudId)
        while (cj.status != wanted) {
            if (cj.status in setOf("FAILED", "CANCELLED", "EXPIRED")) throw CloudException(cj.error ?: "Server job ${cj.status.lowercase()}")
            if (SystemClock.elapsedRealtime() > deadline) throw CloudException("Timed out waiting for the server.")
            progress(job, 0.3f + 0.6f * cj.progress.toFloat(), "Server: ${cj.stage}")
            delay(3000)
            cj = try { client.job(cloudId) } catch (e: java.io.IOException) { delay(10_000); client.job(cloudId) }
        }
        val out = if (job.isPreview) previewFile(job) else fullFile(video, s)
        out.parentFile?.mkdirs()
        client.download(cloudId, if (job.isPreview) "preview" else "full", out) { got -> progress(job, 0.9f, "Downloading ${got / 1_000_000} MB") }
        val validation = OutputValidator.validate(applicationContext, out, s.outWidth, s.outHeight, "video/hevc", -1, -1, expectAudio = false)
        if (validation.width != s.outWidth || validation.height != s.outHeight || !validation.firstFrameDecodes) {
            out.delete()
            return fail(job, JobStatus.FAILED, "Downloaded output failed validation: ${validation.problems.joinToString("; ")}")
        }
        val r = cj.result ?: JSONObject()
        val json = JSONObject()
            .put("type", "AI super resolution (Real-ESRGAN, cloud)")
            .put("model", r.optString("model", "Real-ESRGAN general v3 compact")).put("modelVersion", r.optString("model_version"))
            .put("engine", r.optString("engine")).put("source", "${video.width}x${video.height}").put("output", "${s.outWidth}x${s.outHeight}")
            .put("codec", "video/hevc").put("elapsedMs", (r.optDouble("elapsed_s", 0.0) * 1000).toLong())
            .put("framesOut", r.optInt("frames")).put("outputBytes", out.length())
            .put("server", prefs.cloudUrl).put("validation", JSONObject().put("ok", true))
        if (!job.isPreview && prefs.deleteCloudDataImmediately) {
            try { client.delete(cloudId) } catch (_: Exception) { /* server retention policy still applies */ }
        }
        return finish(job, video, out, json)
    }

    private suspend fun finish(job: JobEntity, video: VideoEntity, out: File, json: JSONObject): Result {
        val current = jobs.get(job.id) ?: job
        val outputVideoId = if (job.isPreview) null else container.videos.addEnhanced(out, video, json.toString())
        jobs.update(
            current.copy(
                status = JobStatus.SUCCEEDED, progress = 1f, stage = "Done", outputPath = out.path,
                outputVideoId = outputVideoId, resultJson = json.toString(), finishedAt = System.currentTimeMillis(),
            ),
        )
        return Result.success()
    }

    private suspend fun fail(job: JobEntity, status: String, message: String): Result {
        val current = jobs.get(job.id) ?: job
        jobs.update(current.copy(status = status, message = message, stage = status.lowercase().replaceFirstChar { it.uppercase() }, finishedAt = System.currentTimeMillis()))
        return Result.failure()
    }

    private fun foreground(job: JobEntity, fraction: Float, stage: String): ForegroundInfo {
        val n: Notification = NotificationCompat.Builder(applicationContext, VRVisionApp.CHANNEL_PROCESSING)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(if (job.isPreview) "Enhancing 10-second preview" else "Enhancing video")
            .setContentText(stage)
            .setProgress(100, (fraction * 100).toInt(), false)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
        val type = if (Build.VERSION.SDK_INT >= 35) ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROCESSING else ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        return ForegroundInfo(NOTIFICATION_BASE + job.id.toInt(), n, type)
    }

    companion object {
        const val KEY_JOB = "jobId"
        private const val NOTIFICATION_BASE = 4000
    }
}
