package com.lensprompt.app.data

import android.content.Context
import android.util.AtomicFile
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import java.io.File
import java.util.UUID

data class Script(
    val id: String,
    val title: String,
    val body: String,
    val createdAt: Long,
    val updatedAt: Long,
    val lastOpenedAt: Long = 0L,
) {
    val wordCount: Int get() = body.split(Regex("\\s+")).count { it.isNotBlank() }

    fun toJson(): JSONObject = JSONObject()
        .put("id", id).put("title", title).put("body", body)
        .put("createdAt", createdAt).put("updatedAt", updatedAt).put("lastOpenedAt", lastOpenedAt)

    companion object {
        fun fromJson(o: JSONObject) = Script(
            id = o.getString("id"),
            title = o.optString("title", ""),
            body = o.optString("body", ""),
            createdAt = o.optLong("createdAt"),
            updatedAt = o.optLong("updatedAt"),
            lastOpenedAt = o.optLong("lastOpenedAt"),
        )
    }
}

/**
 * Scripts stored as one JSON file each, written with [AtomicFile] so a crash or
 * process kill mid-write can never corrupt or lose a script. All disk work is
 * on [Dispatchers.IO]; the in-memory list is the source of truth for the UI.
 */
class ScriptRepository(context: Context) {

    private val dir = File(context.filesDir, "scripts").apply { mkdirs() }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val writeLock = Mutex()

    private val _scripts = MutableStateFlow<List<Script>>(emptyList())
    val scripts: StateFlow<List<Script>> = _scripts.asStateFlow()

    private val _loaded = MutableStateFlow(false)
    val loaded: StateFlow<Boolean> = _loaded.asStateFlow()

    private val _lastError = MutableStateFlow<String?>(null)
    val lastError: StateFlow<String?> = _lastError.asStateFlow()

    init {
        scope.launch { load() }
    }

    private suspend fun load() {
        val list = ArrayList<Script>()
        dir.listFiles { f -> f.name.endsWith(".json") }?.forEach { f ->
            try {
                val bytes = AtomicFile(f).readFully()
                list += Script.fromJson(JSONObject(String(bytes, Charsets.UTF_8)))
            } catch (e: Exception) {
                Log.w(TAG, "Skipping unreadable script ${f.name}", e)
            }
        }
        if (list.isEmpty() && _scripts.value.isEmpty()) {
            val now = System.currentTimeMillis()
            val welcome = Script(UUID.randomUUID().toString(), WELCOME_TITLE, WELCOME_BODY, now, now)
            list += welcome
            persist(welcome)
        }
        // Keep anything created while loading was still in progress.
        _scripts.update { current -> sorted(list + current.filter { c -> list.none { it.id == c.id } }) }
        _loaded.value = true
    }

    fun get(id: String): Script? = _scripts.value.firstOrNull { it.id == id }

    fun create(title: String = "", body: String = ""): Script {
        val now = System.currentTimeMillis()
        val s = Script(UUID.randomUUID().toString(), title, body, now, now, now)
        _scripts.update { sorted(it + s) }
        scope.launch { persist(s) }
        return s
    }

    /** Saves edits. Cheap to call often; the editor debounces. */
    fun save(id: String, title: String, body: String) {
        var changed: Script? = null
        _scripts.update { list ->
            list.map {
                if (it.id == id && (it.title != title || it.body != body)) {
                    it.copy(title = title, body = body, updatedAt = System.currentTimeMillis()).also { s -> changed = s }
                } else it
            }.let(::sorted)
        }
        changed?.let { s -> scope.launch { persist(s) } }
    }

    fun rename(id: String, title: String) {
        val s = get(id) ?: return
        save(id, title, s.body)
    }

    fun duplicate(id: String): Script? {
        val src = get(id) ?: return null
        return create(src.title.ifBlank { "Untitled" } + " (copy)", src.body)
    }

    fun delete(id: String) {
        _scripts.update { list -> list.filterNot { it.id == id } }
        scope.launch {
            writeLock.withLock {
                try { AtomicFile(file(id)).delete() } catch (e: Exception) { report("Could not delete script", e) }
            }
        }
    }

    fun markOpened(id: String) {
        var changed: Script? = null
        _scripts.update { list ->
            list.map { if (it.id == id) it.copy(lastOpenedAt = System.currentTimeMillis()).also { s -> changed = s } else it }
                .let(::sorted)
        }
        changed?.let { s -> scope.launch { persist(s) } }
    }

    fun clearError() { _lastError.value = null }

    private suspend fun persist(s: Script) = writeLock.withLock {
        val af = AtomicFile(file(s.id))
        var out: java.io.FileOutputStream? = null
        try {
            out = af.startWrite()
            out.write(s.toJson().toString().toByteArray(Charsets.UTF_8))
            af.finishWrite(out)
        } catch (e: Exception) {
            out?.let { af.failWrite(it) }
            report("Could not save “${s.title.ifBlank { "Untitled" }}”", e)
        }
    }

    private fun report(message: String, e: Exception) {
        Log.e(TAG, message, e)
        _lastError.value = "$message: ${e.message ?: e.javaClass.simpleName}"
    }

    private fun file(id: String) = File(dir, "$id.json")

    private fun sorted(list: List<Script>) =
        list.sortedByDescending { maxOf(it.updatedAt, it.lastOpenedAt) }

    companion object {
        private const val TAG = "ScriptRepository"
        const val WELCOME_TITLE = "Welcome to LensPrompt"
        const val WELCOME_BODY =
            "Welcome to LensPrompt. This short script lets you try Smart Follow. " +
                "Tap the play button and simply start reading out loud at your own pace. " +
                "The text follows your voice, so you never have to chase it. " +
                "Try speaking a little faster, then slow down again. " +
                "Now stop for a few seconds and notice that the text waits for you. " +
                "When you continue, LensPrompt finds your place and moves on smoothly. " +
                "You can skip a sentence or repeat a few words and it will keep up. " +
                "Switch to manual mode at any time if you prefer a fixed scrolling speed. " +
                "Good luck with your recording!"
    }
}
