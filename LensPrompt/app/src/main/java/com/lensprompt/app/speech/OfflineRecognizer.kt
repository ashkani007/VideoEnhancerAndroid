package com.lensprompt.app.speech

import android.os.Process
import android.os.SystemClock
import android.util.Log
import com.lensprompt.app.diag.Diagnostics
import com.lensprompt.core.RecognizerJson
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import org.vosk.LibVosk
import org.vosk.LogLevel
import org.vosk.Model
import org.vosk.Recognizer
import java.io.File
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * A speech recognizer that consumes PCM handed to it by LensPrompt, instead of
 * opening the microphone itself. This is what lets one microphone capture feed
 * the video soundtrack, voice activity and speech recognition at the same time.
 *
 * Implementations must be cheap to call from the capture thread ([accept] never
 * blocks) and report through [events] using the same [SpeechEvent]s as the
 * system recognizer, so Smart Follow does not care which engine is running.
 */
interface PcmSpeechEngine {
    val name: String
    val events: SharedFlow<SpeechEvent>
    val status: StateFlow<RecognizerStatus>
    /** Starts recognizing 16 kHz mono PCM16; false if the engine cannot run. */
    fun start(): Boolean
    /** Called on the capture thread with 16 kHz mono samples. Never blocks. */
    fun accept(samples: ShortArray)
    fun stop()
}

/**
 * Loaded offline models, shared by the prompter and the floating overlay.
 * Only one model is kept in memory (they are 50–300 MB once loaded).
 */
object OfflineModelCache {
    private var loadedPath: String? = null
    private var model: Model? = null

    init {
        try { LibVosk.setLogLevel(LogLevel.WARNINGS) } catch (_: Throwable) {}
    }

    /** Loads (or returns the already loaded) model in [dir]. Slow: call off the main thread. */
    @Synchronized
    fun load(dir: File): Model {
        if (loadedPath == dir.absolutePath) model?.let { return it }
        model?.close()
        model = null
        loadedPath = null
        val t0 = SystemClock.elapsedRealtime()
        val m = Model(dir.absolutePath)
        Log.i(TAG, "loaded offline model ${dir.name} in ${SystemClock.elapsedRealtime() - t0} ms")
        model = m
        loadedPath = dir.absolutePath
        return m
    }

    @Synchronized
    fun loadedFor(dir: File): Model? = if (loadedPath == dir.absolutePath) model else null

    @Synchronized
    fun release() {
        model?.close()
        model = null
        loadedPath = null
    }

    private const val TAG = "OfflineModel"
}

/**
 * Offline streaming recognition with Vosk (Kaldi), on a dedicated thread.
 * Emits growing partial hypotheses (~10/s) and a final result at each
 * end-point Vosk detects in the stream; the stream itself never ends, so
 * there are no session restarts and nothing ever competes for the microphone.
 */
class VoskSpeechEngine(private val model: Model, private val label: String) : PcmSpeechEngine {

    override val name: String get() = "offline ($label)"

    private val _events = MutableSharedFlow<SpeechEvent>(extraBufferCapacity = 256, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    override val events: SharedFlow<SpeechEvent> = _events.asSharedFlow()

    private val _status = MutableStateFlow(RecognizerStatus.OFF)
    override val status: StateFlow<RecognizerStatus> = _status.asStateFlow()

    private val queue = ArrayBlockingQueue<ShortArray>(QUEUE_CHUNKS)
    @Volatile private var running = false
    private var thread: Thread? = null

    override fun start(): Boolean {
        if (running) return true
        val rec = try {
            Recognizer(model, 16_000f)
        } catch (e: Throwable) {
            Log.e(TAG, "could not create the offline recognizer", e)
            Diagnostics.lastRecognizerError = "offline recognizer: ${e.message}"
            _status.value = RecognizerStatus.FAILED
            return false
        }
        queue.clear()
        running = true
        Diagnostics.recognizerStartCount.incrementAndGet()
        _status.value = RecognizerStatus.LISTENING
        Diagnostics.recognizerState = "LISTENING"
        _events.tryEmit(SpeechEvent.SessionStarted(SystemClock.elapsedRealtime()))
        thread = Thread({ loop(rec) }, "lensprompt-offline-asr").apply { start() }
        return true
    }

    override fun accept(samples: ShortArray) {
        if (!running) return
        if (!queue.offer(samples)) {
            // The recognizer is behind real time (slow phone): drop the oldest audio
            // rather than drifting further behind the speaker.
            queue.poll()
            queue.offer(samples)
        }
    }

    override fun stop() {
        if (!running) return
        running = false
        thread?.join(1_500)
        thread = null
        queue.clear()
        _status.value = RecognizerStatus.OFF
        Diagnostics.recognizerState = "OFF"
    }

    private fun loop(rec: Recognizer) {
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO)
        var lastPartial = ""
        var lastPartialMs = 0L
        try {
            while (running) {
                val chunk = try { queue.poll(200, TimeUnit.MILLISECONDS) } catch (_: InterruptedException) { break } ?: continue
                Diagnostics.pcmFedToEngine.addAndGet(chunk.size * 2L)
                val endpoint = rec.acceptWaveForm(chunk, chunk.size)
                val now = SystemClock.elapsedRealtime()
                if (endpoint) {
                    val text = RecognizerJson.text(rec.result)
                    lastPartial = ""
                    if (text.isNotEmpty()) {
                        Diagnostics.onResult(final = true, text)
                        _events.tryEmit(SpeechEvent.Final(now, text))
                    }
                } else if (now - lastPartialMs >= PARTIAL_INTERVAL_MS) {
                    lastPartialMs = now
                    val text = RecognizerJson.partial(rec.partialResult)
                    if (text.isNotEmpty() && text != lastPartial) {
                        lastPartial = text
                        Diagnostics.onResult(final = false, text)
                        _events.tryEmit(SpeechEvent.Partial(now, text))
                    }
                }
            }
            val tail = RecognizerJson.text(rec.finalResult)
            if (tail.isNotEmpty()) {
                Diagnostics.onResult(final = true, tail)
                _events.tryEmit(SpeechEvent.Final(SystemClock.elapsedRealtime(), tail))
            }
        } catch (e: Throwable) {
            Log.e(TAG, "offline recognition failed", e)
            Diagnostics.lastRecognizerError = "offline recognizer: ${e.message}"
            _status.value = RecognizerStatus.FAILED
            Diagnostics.recognizerState = "FAILED"
            _events.tryEmit(SpeechEvent.Failure(SystemClock.elapsedRealtime(), -2, "Offline recognition failed: ${e.message}", fatal = true))
        } finally {
            try { rec.close() } catch (_: Throwable) {}
        }
    }

    private companion object {
        const val TAG = "OfflineASR"
        const val QUEUE_CHUNKS = 150 // 3 s of 20 ms chunks
        const val PARTIAL_INTERVAL_MS = 100L
    }
}
