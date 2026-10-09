package com.vrvision.app.cloud

import android.content.ContentResolver
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.TimeUnit

class CloudException(message: String, val httpCode: Int? = null) : Exception(message)

data class CloudJob(
    val id: String,
    val status: String,
    val progress: Double,
    val stage: String,
    val error: String?,
    val receivedBytes: Long,
    val previewAvailable: Boolean,
    val outputAvailable: Boolean,
    val result: JSONObject?,
)

/**
 * Client for the VRVision backend (backend/app/main.py). Used only from a job the user created
 * after accepting the consent screen; it holds no credentials besides the user-entered API key
 * and a short-lived token.
 */
class CloudClient(baseUrl: String, private val apiKey: String) {
    private val base = baseUrl.trimEnd('/')
    private val http = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .build()
    private val json = "application/json".toMediaType()
    private var token: String? = null
    private var tokenExp = 0L

    private suspend fun auth(): String {
        val now = System.currentTimeMillis() / 1000
        token?.let { if (now < tokenExp - 60) return it }
        val o = call(Request.Builder().url("$base/v1/auth/token").header("X-API-Key", apiKey).post(ByteArray(0).toRequestBody()).build(), authed = false)
        token = o.getString("token"); tokenExp = o.getLong("expires_at")
        return token!!
    }

    private suspend fun call(req: Request, authed: Boolean = true): JSONObject = withContext(Dispatchers.IO) {
        val r = if (authed) req.newBuilder().header("Authorization", "Bearer ${auth()}").build() else req
        http.newCall(r).execute().use { resp -> parse(resp) }
    }

    private fun parse(resp: Response): JSONObject {
        val body = resp.body?.string().orEmpty()
        if (!resp.isSuccessful) {
            val detail = try { JSONObject(body).optString("detail", body) } catch (_: Exception) { body }
            throw CloudException(detail.ifBlank { "HTTP ${resp.code}" }, resp.code)
        }
        return if (body.isBlank()) JSONObject() else JSONObject(body)
    }

    suspend fun health(): JSONObject = call(Request.Builder().url("$base/v1/health").get().build(), authed = false)

    suspend fun quote(width: Int, height: Int, fps: Double, durationMs: Long, sizeBytes: Long): JSONObject =
        call(post("/v1/quote", JSONObject().put("width", width).put("height", height).put("fps", fps)
            .put("duration_ms", durationMs).put("size_bytes", sizeBytes)))

    suspend fun createJob(body: JSONObject): String = call(post("/v1/jobs", body)).getString("id")

    suspend fun job(id: String): CloudJob {
        val o = call(Request.Builder().url("$base/v1/jobs/$id").get().build())
        return CloudJob(
            id = o.getString("id"), status = o.getString("status"), progress = o.optDouble("progress", 0.0),
            stage = o.optString("stage"), error = if (o.isNull("error")) null else o.optString("error"),
            receivedBytes = o.optLong("received_bytes"), previewAvailable = o.optBoolean("preview_available"),
            outputAvailable = o.optBoolean("output_available"), result = o.optJSONObject("result"),
        )
    }

    /**
     * Uploads [uri] in chunks. On a network error it waits with exponential backoff, asks the
     * server how many bytes it has and resumes from there.
     */
    suspend fun upload(resolver: ContentResolver, uri: Uri, size: Long, jobId: String, chunk: Int, onProgress: suspend (Long) -> Unit) {
        var attempt = 0
        while (true) {
            currentCoroutineContext().ensureActive()
            try {
                var offset = job(jobId).receivedBytes
                if (offset >= size) return
                withContext(Dispatchers.IO) {
                    resolver.openInputStream(uri)!!.use { input ->
                        var skipped = 0L
                        while (skipped < offset) {
                            val n = input.skip(offset - skipped)
                            if (n <= 0) throw IOException("Could not seek in source")
                            skipped += n
                        }
                        val buf = ByteArray(chunk)
                        while (offset < size) {
                            currentCoroutineContext().ensureActive()
                            val want = minOf(chunk.toLong(), size - offset).toInt()
                            var read = 0
                            while (read < want) {
                                val n = input.read(buf, read, want - read)
                                if (n < 0) throw IOException("Source ended early")
                                read += n
                            }
                            val req = Request.Builder().url("$base/v1/jobs/$jobId/upload")
                                .header("Content-Range", "bytes $offset-${offset + read - 1}/$size")
                                .put(buf.copyOf(read).toRequestBody("application/octet-stream".toMediaType()))
                                .build()
                            call(req)
                            offset += read
                            attempt = 0
                            onProgress(offset)
                        }
                    }
                }
                return
            } catch (e: IOException) {
                if (++attempt > MAX_RETRIES) throw CloudException("Upload failed after $MAX_RETRIES retries: ${e.message}")
                delay(backoffMs(attempt))
            } catch (e: CloudException) {
                // 409: our offset disagrees with the server (e.g. a response was lost after the
                // server stored a chunk). Re-read received_bytes and continue from there.
                if (e.httpCode != 409 || ++attempt > MAX_RETRIES) throw e
            }
        }
    }

    suspend fun completeUpload(jobId: String): CloudJob { call(post("/v1/jobs/$jobId/upload/complete", JSONObject())); return job(jobId) }
    suspend fun startFull(jobId: String) { call(post("/v1/jobs/$jobId/full", JSONObject())) }
    suspend fun cancel(jobId: String) { call(post("/v1/jobs/$jobId/cancel", JSONObject())) }
    suspend fun delete(jobId: String) { call(Request.Builder().url("$base/v1/jobs/$jobId").delete().build()) }

    /** Downloads with HTTP Range resume after interruptions. */
    suspend fun download(jobId: String, kind: String, dest: File, onProgress: suspend (Long) -> Unit) {
        var attempt = 0
        while (true) {
            currentCoroutineContext().ensureActive()
            try {
                withContext(Dispatchers.IO) {
                    val have = if (dest.exists()) dest.length() else 0L
                    val req = Request.Builder().url("$base/v1/jobs/$jobId/output?kind=$kind")
                        .header("Authorization", "Bearer ${auth()}")
                        .apply { if (have > 0) header("Range", "bytes=$have-") }
                        .get().build()
                    http.newCall(req).execute().use { resp ->
                        if (resp.code == 416) return@withContext
                        if (!resp.isSuccessful) throw CloudException("Download failed: HTTP ${resp.code}", resp.code)
                        val append = resp.code == 206
                        FileOutputStream(dest, append).use { out ->
                            val input = resp.body!!.byteStream()
                            val buf = ByteArray(256 * 1024)
                            var total = if (append) have else 0L
                            while (true) {
                                val n = input.read(buf)
                                if (n < 0) break
                                out.write(buf, 0, n)
                                total += n
                                onProgress(total)
                            }
                        }
                    }
                }
                return
            } catch (e: IOException) {
                if (++attempt > MAX_RETRIES) throw CloudException("Download failed after $MAX_RETRIES retries: ${e.message}")
                delay(backoffMs(attempt))
            }
        }
    }

    private fun post(path: String, body: JSONObject) =
        Request.Builder().url("$base$path").post(body.toString().toRequestBody(json)).build()

    companion object {
        const val CONSENT_TEXT_VERSION = "2026-10-01"
        const val MAX_RETRIES = 6
        fun backoffMs(attempt: Int): Long = (1000L shl (attempt - 1).coerceAtMost(6)).coerceAtMost(60_000L)

        fun consentJson(grantedAtMs: Long, version: String): JSONObject =
            JSONObject().put("granted", true).put("text_version", version).put("granted_at", Instant.ofEpochMilli(grantedAtMs).toString())

        suspend fun sha256(resolver: ContentResolver, uri: Uri): String = withContext(Dispatchers.IO) {
            val md = MessageDigest.getInstance("SHA-256")
            resolver.openInputStream(uri)!!.use { input ->
                val buf = ByteArray(1 shl 20)
                while (true) {
                    val n = input.read(buf)
                    if (n < 0) break
                    md.update(buf, 0, n)
                }
            }
            md.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
