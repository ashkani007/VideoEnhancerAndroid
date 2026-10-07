package com.lensprompt.app.diag

import android.os.SystemClock
import android.util.Log
import java.util.concurrent.atomic.AtomicLong

/**
 * Process-wide audio / recognition diagnostics. Written from the capture,
 * recognizer and UI threads (volatile fields and atomics, no locks), read by the
 * debug HUD, the "Copy diagnostics" button and a periodic logcat line:
 *
 *   adb logcat -s LensPromptDiag
 *
 * These are measurements, not guesses: every value is set where the event
 * actually happens (AudioRecord.read, pipe write, recognizer callback, …).
 */
object Diagnostics {
    const val TAG = "LensPromptDiag"

    // ---- microphone
    /** Who captures the microphone: "system recognizer", "LensPrompt (AudioRecord)", "none". */
    @Volatile var micOwner = "none"
    @Volatile var audioSource = "-"
    @Volatile var sampleRate = 0
    /** AudioRecord.getState(): UNINITIALIZED / INITIALIZED / "-" (no AudioRecord). */
    @Volatile var audioRecordState = "-"
    /** AudioRecord.getRecordingState(): STOPPED / RECORDING. */
    @Volatile var audioRecordRecordingState = "-"
    val pcmBytesRead = AtomicLong()
    /** Bytes per second actually read from AudioRecord (≈96 000 at 48 kHz mono). */
    @Volatile var pcmReadRate = 0.0
    val pcmReadErrors = AtomicLong()
    /** Android says our capture is silenced by another app (API 29+), null = unknown. */
    @Volatile var micSilenced: Boolean? = null
    /** How long the samples have been exactly zero (silenced clients receive zeros). */
    @Volatile var zeroRunMs = 0L

    // ---- pipe to the system recognizer (EXTRA_AUDIO_SOURCE)
    val pipeBytesWritten = AtomicLong()
    /** Chunks dropped because the pipe was full (nobody reading it). */
    val pipeFullDrops = AtomicLong()
    /** Writes that failed for other reasons (reader closed, bad descriptor). */
    val pipeWriteFailures = AtomicLong()

    // ---- recognizer
    @Volatile var recognizerEngine = "-"
    /** The recognition service component (system recognizer) or model (offline). */
    @Volatile var recognizerComponent = "-"
    @Volatile var recognizerState = "OFF"
    val recognizerStartCount = AtomicLong()
    val recognizerRestartCount = AtomicLong()
    val partialCount = AtomicLong()
    val finalCount = AtomicLong()
    val pcmFedToEngine = AtomicLong()
    @Volatile var lastRecognizerError = "-"
    @Volatile var lastResultAtMs = 0L
    @Volatile var lastResultText = ""
    /** Recognizer health verdict for the current route. */
    @Volatile var recognizerVerdict = "-"

    // ---- smart follow / recording
    @Volatile var vadLevelDb = Float.NaN
    @Volatile var vadState = "-"
    @Volatile var voicedWithoutWordsMs = 0L
    @Volatile var recordingState = "idle"
    @Volatile var muxState = "-"
    /** What moves the text: "words (system recognizer)", "words (offline)", "pacing", "manual". */
    @Volatile var smartFollowSource = "-"

    /** Clears the recognizer counters (new prompting session or route). */
    fun resetRecognizer(engine: String, component: String) {
        recognizerEngine = engine
        recognizerComponent = component
        recognizerStartCount.set(0)
        recognizerRestartCount.set(0)
        partialCount.set(0)
        finalCount.set(0)
        pcmFedToEngine.set(0)
        pipeBytesWritten.set(0)
        pipeFullDrops.set(0)
        pipeWriteFailures.set(0)
        lastRecognizerError = "-"
        lastResultAtMs = 0L
        lastResultText = ""
        recognizerVerdict = "-"
    }

    fun resetCapture() {
        pcmBytesRead.set(0)
        pcmReadRate = 0.0
        pcmReadErrors.set(0)
        micSilenced = null
        zeroRunMs = 0
    }

    fun onResult(final: Boolean, text: String) {
        if (final) finalCount.incrementAndGet() else partialCount.incrementAndGet()
        lastResultAtMs = SystemClock.elapsedRealtime()
        lastResultText = text.takeLast(60)
    }

    fun resultAgeText(now: Long = SystemClock.elapsedRealtime()): String =
        if (lastResultAtMs == 0L) "never" else "%.1fs".format((now - lastResultAtMs) / 1000.0)

    /** Every value, one per line (Copy diagnostics, bug reports). */
    fun full(): List<Pair<String, String>> = listOf(
        "MIC OWNER" to micOwner,
        "AUDIO SOURCE" to "$audioSource @ $sampleRate Hz",
        "AUDIORECORD STATE" to audioRecordState,
        "AUDIORECORD RECORDING STATE" to audioRecordRecordingState,
        "PCM BYTES READ" to pcmBytesRead.get().toString(),
        "PCM READ RATE" to "%.0f B/s".format(pcmReadRate),
        "PCM READ ERRORS" to pcmReadErrors.get().toString(),
        "MIC SILENCED BY SYSTEM" to (micSilenced?.toString() ?: "unknown"),
        "ZERO-SAMPLE RUN" to "${zeroRunMs} ms",
        "PIPE BYTES WRITTEN" to pipeBytesWritten.get().toString(),
        "PIPE FULL DROPS" to pipeFullDrops.get().toString(),
        "PIPE WRITE FAILURES" to pipeWriteFailures.get().toString(),
        "RECOGNIZER ENGINE" to recognizerEngine,
        "RECOGNIZER COMPONENT" to recognizerComponent,
        "SPEECH RECOGNIZER STATE" to recognizerState,
        "RECOGNIZER START COUNT" to recognizerStartCount.get().toString(),
        "RECOGNIZER RESTART COUNT" to recognizerRestartCount.get().toString(),
        "PARTIAL RESULT COUNT" to partialCount.get().toString(),
        "FINAL RESULT COUNT" to finalCount.get().toString(),
        "PCM FED TO ENGINE" to pcmFedToEngine.get().toString(),
        "LAST RECOGNIZER ERROR" to lastRecognizerError,
        "LAST RESULT AGE" to resultAgeText(),
        "LAST RESULT" to lastResultText,
        "RECOGNIZER VERDICT" to recognizerVerdict,
        "VAD LEVEL" to (if (vadLevelDb.isNaN()) "-" else "%.1f dB".format(vadLevelDb)) + " $vadState",
        "VOICED WITHOUT WORDS" to "$voicedWithoutWordsMs ms",
        "RECORDING STATE" to recordingState,
        "MUX STATE" to muxState,
        "SMART FOLLOW SOURCE" to smartFollowSource,
    )

    /** The few lines that fit the on-screen HUD. */
    fun hud(): List<String> = listOf(
        "Mic: $micOwner · $audioSource · rec=$audioRecordRecordingState" +
            (if (micSilenced == true) " · SILENCED" else "") +
            " · %.0f kB/s".format(pcmReadRate / 1000),
        "ASR: $recognizerEngine $recognizerState · starts ${recognizerStartCount.get()}/restarts ${recognizerRestartCount.get()}" +
            " · P${partialCount.get()} F${finalCount.get()} · last ${resultAgeText()}",
        "ASR err: $lastRecognizerError · verdict: $recognizerVerdict",
        "Pipe: ${pipeBytesWritten.get() / 1024} kB, full ${pipeFullDrops.get()}, fail ${pipeWriteFailures.get()}" +
            " · engine fed ${pcmFedToEngine.get() / 1024} kB",
        "Follow: $smartFollowSource · voiced w/o words ${voicedWithoutWordsMs}ms · rec $recordingState · mux $muxState",
    )

    fun text(): String = full().joinToString("\n") { (k, v) -> "$k: $v" }

    fun logLine(): String = full().joinToString(" | ") { (k, v) -> "$k=$v" }

    fun log(event: String) = Log.i(TAG, "$event — ${logLine()}")
}
