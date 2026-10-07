package com.lensprompt.app.speech

import android.content.Context
import android.net.Uri
import android.util.Log
import com.lensprompt.app.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.zip.ZipInputStream
import kotlin.coroutines.coroutineContext

/**
 * An offline speech pack: a small Vosk model for one language.
 * Candidates are tried in order (newest first) when downloading.
 */
data class OfflineModelSpec(
    val key: String,
    val label: String,
    val candidates: List<String>,
    /** Approximate download size, MB (shown before downloading). */
    val approxMb: Int,
)

sealed interface ModelState {
    data object NotInstalled : ModelState
    data class Downloading(val name: String, val bytes: Long, val total: Long) : ModelState
    data object Installing : ModelState
    data class Installed(val name: String, val sizeMb: Int) : ModelState
    data class Failed(val message: String) : ModelState
}

/**
 * Downloads, imports, validates and deletes offline speech packs.
 *
 * Packs are downloaded only when the user asks (they are 40–50 MB each) from
 * the Vosk model repository, or imported from a .zip the user already has.
 * Stored in app-private storage: filesDir/vosk/<key>/model.
 */
class SpeechModelManager(private val context: Context) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val jobs = HashMap<String, Job>()
    private val root = File(context.filesDir, "vosk")

    private val _states = MutableStateFlow(SPECS.associate { it.key to scan(it.key) })
    val states: StateFlow<Map<String, ModelState>> = _states.asStateFlow()

    /** Installed model directory for a recognition language tag, or null. */
    fun modelDirFor(languageTag: String): File? {
        val key = keyFor(languageTag) ?: return null
        return File(root, "$key/model").takeIf { isValidModel(it) }
    }

    fun specFor(languageTag: String): OfflineModelSpec? = keyFor(languageTag)?.let { k -> SPECS.first { it.key == k } }

    fun download(key: String) {
        val spec = SPECS.firstOrNull { it.key == key } ?: return
        if (jobs[key]?.isActive == true) return
        jobs[key] = scope.launch {
            var lastError = "no download source"
            for (name in spec.candidates) {
                val url = "$BASE_URL/$name.zip"
                try {
                    set(key, ModelState.Downloading(name, 0, spec.approxMb * 1_000_000L))
                    val zip = File(root, "$key.zip.part").also { it.parentFile?.mkdirs() }
                    fetch(url, zip) { done, total -> set(key, ModelState.Downloading(name, done, total)) }
                    set(key, ModelState.Installing)
                    zip.inputStream().use { install(key, it) }
                    zip.delete()
                    set(key, scan(key))
                    return@launch
                } catch (e: NotFound) {
                    lastError = "not found: $name"
                    Log.w(TAG, "model $url not found, trying next")
                } catch (e: Exception) {
                    if (e is kotlinx.coroutines.CancellationException) throw e
                    lastError = e.message ?: e.javaClass.simpleName
                    Log.e(TAG, "download $url failed", e)
                    break
                }
            }
            File(root, "$key.zip.part").delete()
            set(key, ModelState.Failed(context.getString(R.string.models_download_failed, lastError)))
        }
    }

    fun cancel(key: String) {
        jobs.remove(key)?.cancel()
        File(root, "$key.zip.part").delete()
        set(key, scan(key))
    }

    /** Install from a Vosk model .zip picked by the user (Storage Access Framework). */
    fun import(key: String, uri: Uri) {
        if (jobs[key]?.isActive == true) return
        jobs[key] = scope.launch {
            try {
                set(key, ModelState.Installing)
                val input = context.contentResolver.openInputStream(uri) ?: throw IOException("cannot open file")
                input.use { install(key, it) }
                set(key, scan(key))
            } catch (e: Exception) {
                Log.e(TAG, "import failed", e)
                set(key, ModelState.Failed(context.getString(R.string.models_import_failed, e.message)))
            }
        }
    }

    fun delete(key: String) {
        cancel(key)
        OfflineModelCache.release()
        File(root, key).deleteRecursively()
        set(key, scan(key))
    }

    // ------------------------------------------------------------- internals

    private fun set(key: String, state: ModelState) = _states.update { it + (key to state) }

    private fun scan(key: String): ModelState {
        val dir = File(root, "$key/model")
        if (!isValidModel(dir)) return ModelState.NotInstalled
        val name = File(root, "$key/name").takeIf { it.exists() }?.readText()?.trim().orEmpty().ifBlank { "model" }
        val size = dir.walkBottomUp().filter { it.isFile }.sumOf { it.length() }
        return ModelState.Installed(name, (size / 1_000_000).toInt())
    }

    private class NotFound : IOException()

    private suspend fun fetch(url: String, dest: File, progress: (Long, Long) -> Unit) {
        var conn = URL(url).openConnection() as HttpURLConnection
        var redirects = 0
        while (true) {
            conn.connectTimeout = 15_000
            conn.readTimeout = 30_000
            conn.instanceFollowRedirects = true
            val code = conn.responseCode
            if (code in 300..399 && redirects < 5) {
                val loc = conn.getHeaderField("Location") ?: break
                conn.disconnect()
                conn = URL(URL(url), loc).openConnection() as HttpURLConnection
                redirects++
                continue
            }
            if (code == 404) { conn.disconnect(); throw NotFound() }
            if (code != 200) { conn.disconnect(); throw IOException("HTTP $code") }
            break
        }
        val total = conn.contentLengthLong
        try {
            conn.inputStream.use { input ->
                dest.outputStream().use { out ->
                    val buf = ByteArray(64 * 1024)
                    var done = 0L
                    var lastReport = 0L
                    while (true) {
                        coroutineContext.ensureActive()
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        done += n
                        if (done - lastReport > 512 * 1024) { lastReport = done; progress(done, total) }
                    }
                    if (total > 0 && done != total) throw IOException("download incomplete")
                }
            }
        } finally {
            conn.disconnect()
        }
    }

    /**
     * Unzips a Vosk model into filesDir/vosk/<key>/model. Vosk zips contain one
     * top-level folder (e.g. vosk-model-small-en-us-0.15/am/final.mdl …); it is
     * stripped. Paths are checked so a malicious zip cannot write elsewhere.
     */
    private suspend fun install(key: String, input: InputStream) {
        val staging = File(root, "$key.staging").also { it.deleteRecursively(); it.mkdirs() }
        val canonicalStaging = staging.canonicalPath + File.separator
        var topName = ""
        ZipInputStream(input.buffered()).use { zip ->
            while (true) {
                coroutineContext.ensureActive()
                val entry = zip.nextEntry ?: break
                val out = File(staging, entry.name)
                if (!out.canonicalPath.startsWith(canonicalStaging)) throw IOException("bad zip entry ${entry.name}")
                if (topName.isEmpty()) topName = entry.name.substringBefore('/')
                if (entry.isDirectory) {
                    out.mkdirs()
                } else {
                    out.parentFile?.mkdirs()
                    out.outputStream().use { zip.copyTo(it) }
                }
            }
        }
        val modelRoot = findModelRoot(staging) ?: run {
            staging.deleteRecursively()
            throw IOException("this zip is not a Vosk model (no am/final.mdl)")
        }
        OfflineModelCache.release()
        val target = File(root, key)
        target.deleteRecursively()
        target.mkdirs()
        if (!modelRoot.renameTo(File(target, "model"))) {
            modelRoot.copyRecursively(File(target, "model"), overwrite = true)
        }
        File(target, "name").writeText(if (modelRoot == staging) topName.ifBlank { "model" } else modelRoot.name)
        staging.deleteRecursively()
    }

    private fun findModelRoot(dir: File): File? {
        if (isValidModel(dir)) return dir
        return dir.listFiles()?.filter { it.isDirectory }?.firstNotNullOfOrNull { findModelRoot(it) }
    }

    companion object {
        private const val TAG = "SpeechModels"
        const val BASE_URL = "https://alphacephei.com/vosk/models"

        /**
         * Small Vosk models: streaming, offline, ~40–50 MB. Bigger "full" models are
         * more accurate but 1–2 GB, too large for a phone download.
         */
        val SPECS = listOf(
            OfflineModelSpec("en", "English", listOf("vosk-model-small-en-us-0.15"), 40),
            OfflineModelSpec("nl", "Nederlands (Dutch)", listOf("vosk-model-small-nl-0.22"), 39),
            OfflineModelSpec(
                "fa", "فارسی (Persian)",
                listOf("vosk-model-small-fa-0.42", "vosk-model-small-fa-0.5", "vosk-model-small-fa-0.4"), 53,
            ),
            OfflineModelSpec("de", "Deutsch", listOf("vosk-model-small-de-0.15"), 45),
            OfflineModelSpec("fr", "Français", listOf("vosk-model-small-fr-0.22"), 41),
            OfflineModelSpec("es", "Español", listOf("vosk-model-small-es-0.42"), 39),
        )

        fun keyFor(languageTag: String): String? {
            val tag = languageTag.ifBlank { Locale.getDefault().toLanguageTag() }
            val lang = tag.substringBefore('-').substringBefore('_').lowercase(Locale.ROOT)
            val key = if (lang == "pes" || lang == "prs") "fa" else lang
            return SPECS.firstOrNull { it.key == key }?.key
        }

        fun isValidModel(dir: File): Boolean =
            File(dir, "am/final.mdl").isFile && File(dir, "conf").isDirectory
    }
}
