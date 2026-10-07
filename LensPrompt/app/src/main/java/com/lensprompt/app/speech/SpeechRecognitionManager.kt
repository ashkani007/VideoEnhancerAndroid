package com.lensprompt.app.speech

import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import com.lensprompt.app.audio.RecognizerAudioFeed
import com.lensprompt.core.SmartFollowConfig
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

/** Recognizer output, timestamped with [SystemClock.elapsedRealtime]. */
sealed interface SpeechEvent {
    val timeMs: Long
    data class SessionStarted(override val timeMs: Long) : SpeechEvent
    data class Partial(override val timeMs: Long, val text: String) : SpeechEvent
    data class Final(override val timeMs: Long, val text: String) : SpeechEvent
    data class Level(override val timeMs: Long, val rmsDb: Float) : SpeechEvent
    data class EndOfSpeech(override val timeMs: Long) : SpeechEvent
    data class Failure(override val timeMs: Long, val code: Int, val message: String, val fatal: Boolean) : SpeechEvent
}

enum class RecognizerStatus { OFF, STARTING, LISTENING, RESTARTING, BACKING_OFF, FAILED }

/**
 * Continuous speech recognition on top of Android's one-shot [SpeechRecognizer].
 *
 * Android ends a recognition session after silence, on a final result or on
 * errors. To make Smart Follow feel continuous this class restarts sessions in a
 * controlled way:
 *  - normal ends (results, no-match, speech timeout) restart after a short delay;
 *  - repeated empty sessions slow the restart down so it never spins hot;
 *  - real errors back off exponentially and recreate the recognizer for client/busy
 *    errors; after too many consecutive errors the failure is reported as fatal;
 *  - only one restart is ever pending, and callbacks from old sessions are ignored.
 *
 * Must be used from the main thread (a [SpeechRecognizer] requirement).
 * No audio is stored or uploaded by this class; where recognition happens
 * (on-device or online) is decided by the device's recognition service, and
 * [preferOffline] asks it to stay on-device where supported.
 */
class SpeechRecognitionManager(private val context: Context) {

    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var config = SmartFollowConfig()

    private var active = false
    private var languageTag = ""
    private var preferOffline = false
    private var sessionId = 0
    private var sessionEnded = true
    private var sessionStartMs = 0L
    private var heardSpeechInSession = false
    private var consecutiveErrors = 0
    private var consecutiveEmptySessions = 0
    private var offlineFallbackUsed = false
    private var lastLevelEmitMs = 0L

    /** When set, recognition reads LensPrompt's own microphone stream instead of the mic. */
    private var externalFeed: RecognizerAudioFeed? = null
    private var preferOnDevice = true
    private var recognizerIsOnDevice = false

    private val _events = MutableSharedFlow<SpeechEvent>(extraBufferCapacity = 256, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    val events: SharedFlow<SpeechEvent> = _events.asSharedFlow()

    private val _status = MutableStateFlow(RecognizerStatus.OFF)
    val status: StateFlow<RecognizerStatus> = _status.asStateFlow()

    /** Number of session restarts since [start] (debug display). */
    private val _restarts = MutableStateFlow(0)
    val restarts: StateFlow<Int> = _restarts.asStateFlow()

    private val restartRunnable = Runnable { startSession() }

    fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    /** Android 13+ lets an app hand the recognizer its own audio stream. */
    fun supportsExternalAudio(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU

    /**
     * @param externalAudio when non-null (Android 13+ only), the recognizer reads 16 kHz
     *   PCM from LensPrompt's own capture instead of opening the microphone. Used during
     *   video recording, when the microphone must have exactly one owner.
     */
    fun start(languageTag: String, preferOffline: Boolean, config: SmartFollowConfig, externalAudio: RecognizerAudioFeed? = null) {
        stop()
        this.languageTag = languageTag
        this.preferOffline = preferOffline
        this.config = config
        externalFeed = if (supportsExternalAudio()) externalAudio else null
        preferOnDevice = true
        active = true
        consecutiveErrors = 0
        consecutiveEmptySessions = 0
        offlineFallbackUsed = false
        _restarts.value = 0
        if (!isAvailable()) {
            fail(ERROR_UNAVAILABLE, "Speech recognition is not available on this device.")
            return
        }
        startSession()
    }

    fun stop() {
        active = false
        handler.removeCallbacks(restartRunnable)
        sessionId++
        sessionEnded = true
        try { recognizer?.cancel() } catch (e: Exception) { Log.w(TAG, "cancel failed", e) }
        externalFeed?.closeSession()
        _status.value = RecognizerStatus.OFF
    }

    /** Stop and free the recognizer service connection. */
    fun release() {
        stop()
        destroyRecognizer()
    }

    // ------------------------------------------------------------- sessions

    private fun startSession() {
        if (!active) return
        handler.removeCallbacks(restartRunnable)
        val wantOnDevice = externalFeed != null && preferOnDevice && onDeviceAvailable()
        if (recognizer != null && recognizerIsOnDevice != wantOnDevice) destroyRecognizer()
        val rec = recognizer ?: try {
            recognizerIsOnDevice = wantOnDevice
            (if (wantOnDevice) SpeechRecognizer.createOnDeviceSpeechRecognizer(context) else SpeechRecognizer.createSpeechRecognizer(context))
                .also { recognizer = it }
        } catch (e: Exception) {
            Log.e(TAG, "createSpeechRecognizer failed", e)
            onSessionError(SpeechRecognizer.ERROR_CLIENT)
            return
        }
        val id = ++sessionId
        sessionEnded = false
        heardSpeechInSession = false
        sessionStartMs = SystemClock.elapsedRealtime()
        _status.value = RecognizerStatus.STARTING
        try {
            rec.setRecognitionListener(Listener(id))
            rec.startListening(buildIntent())
        } catch (e: Exception) {
            Log.e(TAG, "startListening failed", e)
            sessionEnded = true
            onSessionError(SpeechRecognizer.ERROR_CLIENT)
        }
    }

    private fun buildIntent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        if (languageTag.isNotBlank()) {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, languageTag)
        }
        if (preferOffline && !offlineFallbackUsed) putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        // Ask for long sessions; many services cap these, the restart logic covers the rest.
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 5_000L)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 5_000L)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 30_000L)
        val feed = externalFeed
        if (feed != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            // Read from LensPrompt's own capture (fresh pipe per session); a segmented
            // session keeps recognizing continuously instead of ending at silences.
            putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, feed.openSession())
            putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT, 1)
            putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_ENCODING, AudioFormat.ENCODING_PCM_16BIT)
            putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE, 16_000)
            putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION, RecognizerIntent.EXTRA_AUDIO_SOURCE)
        }
    }

    private fun onDeviceAvailable(): Boolean =
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && try {
            SpeechRecognizer.isOnDeviceRecognitionAvailable(context)
        } catch (_: Exception) {
            false
        }

    private fun scheduleRestart(delayMs: Long, status: RecognizerStatus) {
        if (!active) return
        handler.removeCallbacks(restartRunnable)
        _status.value = status
        _restarts.value = _restarts.value + 1
        handler.postDelayed(restartRunnable, delayMs)
    }

    /** A session ended normally (result, silence, nothing recognized). */
    private fun onSessionCompleted() {
        consecutiveErrors = 0
        val shortAndEmpty = !heardSpeechInSession && SystemClock.elapsedRealtime() - sessionStartMs < 1_500
        consecutiveEmptySessions = if (shortAndEmpty) consecutiveEmptySessions + 1 else 0
        // Quick empty sessions in a row → slow down so we never spin.
        val delay = config.recognizerRestartDelayMs * (1 + consecutiveEmptySessions.coerceAtMost(10))
        scheduleRestart(delay, RecognizerStatus.RESTARTING)
    }

    private fun onSessionError(code: Int) {
        if (!active) return
        if (externalFeed != null && recognizerIsOnDevice && code != SpeechRecognizer.ERROR_NO_MATCH &&
            code != SpeechRecognizer.ERROR_SPEECH_TIMEOUT
        ) {
            // The on-device recognizer could not handle this (language, model, audio
            // source). Fall back to the default service, still fed with our audio.
            Log.i(TAG, "on-device recognizer failed ($code); falling back to default service")
            preferOnDevice = false
            destroyRecognizer()
            scheduleRestart(config.recognizerRestartDelayMs, RecognizerStatus.RESTARTING)
            return
        }
        when (code) {
            SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> {
                onSessionCompleted()
                return
            }
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> {
                fail(code, "Microphone permission is required for Smart Follow.")
                return
            }
            ERROR_LANGUAGE_NOT_SUPPORTED, ERROR_LANGUAGE_UNAVAILABLE -> {
                if (preferOffline && !offlineFallbackUsed) {
                    // The offline model for this language is missing; try the online service.
                    offlineFallbackUsed = true
                    scheduleRestart(config.recognizerRestartDelayMs, RecognizerStatus.RESTARTING)
                } else {
                    fail(code, "The selected recognition language is not supported on this device.")
                }
                return
            }
        }
        consecutiveErrors++
        if (consecutiveErrors >= config.recognizerMaxConsecutiveErrors) {
            fail(code, "Speech recognition keeps failing (${describe(code)}).")
            return
        }
        if (code == SpeechRecognizer.ERROR_CLIENT || code == SpeechRecognizer.ERROR_RECOGNIZER_BUSY ||
            code == ERROR_SERVER_DISCONNECTED
        ) {
            destroyRecognizer() // a fresh connection clears most stuck states
        }
        val backoff = (config.recognizerErrorBackoffMs shl (consecutiveErrors - 1).coerceAtMost(6))
            .coerceAtMost(config.recognizerMaxBackoffMs)
        val nonFatal = SpeechEvent.Failure(SystemClock.elapsedRealtime(), code, describe(code), fatal = false)
        _events.tryEmit(nonFatal)
        scheduleRestart(backoff, RecognizerStatus.BACKING_OFF)
    }

    private fun fail(code: Int, message: String) {
        active = false
        handler.removeCallbacks(restartRunnable)
        _status.value = RecognizerStatus.FAILED
        _events.tryEmit(SpeechEvent.Failure(SystemClock.elapsedRealtime(), code, message, fatal = true))
        destroyRecognizer()
    }

    private fun destroyRecognizer() {
        try { recognizer?.destroy() } catch (e: Exception) { Log.w(TAG, "destroy failed", e) }
        recognizer = null
    }

    private inner class Listener(private val id: Int) : RecognitionListener {
        private fun current() = id == sessionId && active

        override fun onReadyForSpeech(params: Bundle?) {
            if (!current()) return
            _status.value = RecognizerStatus.LISTENING
            _events.tryEmit(SpeechEvent.SessionStarted(SystemClock.elapsedRealtime()))
        }

        override fun onBeginningOfSpeech() {
            if (current()) heardSpeechInSession = true
        }

        override fun onRmsChanged(rmsdB: Float) {
            if (!current()) return
            val now = SystemClock.elapsedRealtime()
            if (now - lastLevelEmitMs >= 40) {
                lastLevelEmitMs = now
                _events.tryEmit(SpeechEvent.Level(now, rmsdB))
            }
        }

        override fun onBufferReceived(buffer: ByteArray?) = Unit

        override fun onEndOfSpeech() {
            if (current()) _events.tryEmit(SpeechEvent.EndOfSpeech(SystemClock.elapsedRealtime()))
        }

        override fun onPartialResults(partialResults: Bundle?) {
            if (!current()) return
            val text = bestText(partialResults) ?: return
            heardSpeechInSession = true
            consecutiveErrors = 0
            _events.tryEmit(SpeechEvent.Partial(SystemClock.elapsedRealtime(), text))
        }

        override fun onResults(results: Bundle?) {
            if (!current() || sessionEnded) return
            sessionEnded = true
            bestText(results)?.let {
                heardSpeechInSession = true
                _events.tryEmit(SpeechEvent.Final(SystemClock.elapsedRealtime(), it))
            }
            onSessionCompleted()
        }

        override fun onError(error: Int) {
            if (!current() || sessionEnded) return
            sessionEnded = true
            Log.d(TAG, "recognizer error $error (${describe(error)})")
            onSessionError(error)
        }

        override fun onEvent(eventType: Int, params: Bundle?) = Unit

        // Segmented sessions (external audio, Android 13+): results per segment,
        // the session itself keeps running.
        override fun onSegmentResults(segmentResults: Bundle) {
            if (!current()) return
            bestText(segmentResults)?.let {
                heardSpeechInSession = true
                consecutiveErrors = 0
                _events.tryEmit(SpeechEvent.Final(SystemClock.elapsedRealtime(), it))
            }
        }

        override fun onEndOfSegmentedSession() {
            if (!current() || sessionEnded) return
            sessionEnded = true
            onSessionCompleted()
        }
    }

    private fun bestText(bundle: Bundle?): String? {
        bundle ?: return null
        val list = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val stable = list?.firstOrNull { it.isNotBlank() }.orEmpty()
        // Some Google versions split partials into stable + unstable text.
        val unstable = bundle.getStringArrayList(UNSTABLE_TEXT)?.firstOrNull().orEmpty()
        val combined = if (unstable.isNotBlank()) "$stable $unstable".trim() else stable
        return combined.ifBlank { null }
    }

    companion object {
        private const val TAG = "SpeechRecognition"
        private const val UNSTABLE_TEXT = "android.speech.extra.UNSTABLE_TEXT"
        // API 31 constants, as literals so they compile against any SDK level.
        private const val ERROR_SERVER_DISCONNECTED = 11
        private const val ERROR_LANGUAGE_NOT_SUPPORTED = 12
        private const val ERROR_LANGUAGE_UNAVAILABLE = 13
        const val ERROR_UNAVAILABLE = -1

        fun describe(code: Int): String = when (code) {
            SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "network timeout"
            SpeechRecognizer.ERROR_NETWORK -> "network error"
            SpeechRecognizer.ERROR_AUDIO -> "microphone busy or unavailable"
            SpeechRecognizer.ERROR_SERVER -> "recognition server error"
            SpeechRecognizer.ERROR_CLIENT -> "recognizer client error"
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "no speech"
            SpeechRecognizer.ERROR_NO_MATCH -> "no match"
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "recognizer busy"
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "missing microphone permission"
            10 -> "too many requests"
            ERROR_SERVER_DISCONNECTED -> "recognition service disconnected"
            ERROR_LANGUAGE_NOT_SUPPORTED -> "language not supported"
            ERROR_LANGUAGE_UNAVAILABLE -> "language unavailable"
            ERROR_UNAVAILABLE -> "speech recognition unavailable"
            else -> "error $code"
        }
    }
}
