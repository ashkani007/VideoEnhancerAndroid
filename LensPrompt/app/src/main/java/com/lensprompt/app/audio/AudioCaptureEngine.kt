package com.lensprompt.app.audio

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioRecordingConfiguration
import android.media.AudioTimestamp
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.os.Process
import android.os.SystemClock
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.util.Log
import androidx.annotation.RequiresApi
import androidx.core.content.ContextCompat
import com.lensprompt.app.diag.Diagnostics
import com.lensprompt.core.AudioDsp
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.OutputStream
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit

/** What was captured, for muxing into the video afterwards. */
data class CapturedAudio(
    val pcmFile: File,
    val sampleRate: Int,
    /** System.nanoTime() of the first PCM frame in [pcmFile]. */
    val startNanos: Long,
    val frames: Long,
)

/**
 * LensPrompt's one microphone capture.
 *
 * Why it exists: a video recorder captures sound from CAMCORDER, which Android
 * treats as privacy-sensitive; while it is captured, other apps (including the
 * system speech-recognition service) receive silence. So while recording video
 * with sound LensPrompt captures the microphone once, itself, and fans the
 * samples out:
 *  1. raw PCM to a file, later encoded and muxed into the video (optional),
 *  2. levels for voice-activity detection,
 *  3. 16 kHz PCM to an in-process recognizer ([pcm16kSink]) and/or to the
 *     system recognizer through a pipe ([recognizerFeed], Android 13+).
 *
 * The capture uses the plain MIC source, not CAMCORDER: MIC is not
 * privacy-sensitive, so LensPrompt never silences anyone else by capturing.
 *
 * The capture thread never blocks on consumers.
 */
class AudioCaptureEngine(private val context: Context) {

    private var record: AudioRecord? = null
    private var thread: Thread? = null
    @Volatile private var running = false

    private var sampleRate = 48_000
    private var pcmFile: File? = null
    @Volatile private var startNanos = 0L
    @Volatile private var frames = 0L

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var recordingCallback: AudioManager.AudioRecordingCallback? = null

    val recognizerFeed = RecognizerAudioFeed()

    /** In-process consumer of 16 kHz mono PCM (offline recognizer); called on the capture thread. */
    @Volatile var pcm16kSink: ((ShortArray) -> Unit)? = null

    /** Called (main thread) when Android starts or stops silencing this capture. */
    @Volatile var onSilencedChanged: ((Boolean) -> Unit)? = null

    val isRunning: Boolean get() = running

    /**
     * @param pcmOut where to write the raw PCM for muxing, or null to not keep audio.
     * @param onLevel called on the capture thread ~25×/s with (level dB, elapsedRealtime ms).
     * @return false if the microphone could not be opened (permission, in use, no mic).
     */
    @SuppressLint("MissingPermission") // checked below
    fun start(pcmOut: File?, onLevel: (Float, Long) -> Unit): Boolean {
        stop()
        Diagnostics.resetCapture()
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Diagnostics.audioRecordState = "no RECORD_AUDIO permission"
            return false
        }
        val rec = openRecord() ?: return false
        record = rec
        pcmFile = pcmOut
        frames = 0
        startNanos = 0
        Diagnostics.audioRecordState = stateName(rec.state)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) registerSilencingCallback(rec)
        try {
            rec.startRecording()
        } catch (e: Exception) {
            Log.e(TAG, "startRecording failed", e)
            Diagnostics.audioRecordRecordingState = "startRecording failed: ${e.message}"
            releaseRecord()
            return false
        }
        Diagnostics.audioRecordRecordingState = recordingStateName(rec.recordingState)
        if (rec.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
            Log.e(TAG, "microphone did not start (in use by another app?)")
            releaseRecord()
            return false
        }
        running = true
        Diagnostics.micOwner = "LensPrompt (AudioRecord)"
        recognizerFeed.start()
        thread = Thread({ captureLoop(rec, pcmOut, onLevel) }, "lensprompt-mic").apply { start() }
        Diagnostics.log("mic started")
        return true
    }

    /** Stops capture and returns what was recorded (null if nothing usable or no file). */
    fun stop(): CapturedAudio? {
        if (!running && record == null) return null
        running = false
        thread?.join(2_000)
        thread = null
        releaseRecord()
        recognizerFeed.stop()
        Diagnostics.micOwner = "none"
        Diagnostics.log("mic stopped")
        val file = pcmFile ?: return null
        pcmFile = null
        return if (frames > 0 && startNanos != 0L) CapturedAudio(file, sampleRate, startNanos, frames) else null
    }

    private fun releaseRecord() {
        val rec = record ?: return
        record = null
        unregisterSilencingCallback()
        try { rec.stop() } catch (_: Exception) {}
        Diagnostics.audioRecordRecordingState = recordingStateName(rec.recordingState)
        rec.release()
        Diagnostics.audioRecordState = "released"
    }

    @SuppressLint("MissingPermission")
    private fun openRecord(): AudioRecord? {
        val sources = intArrayOf(MediaRecorder.AudioSource.MIC, MediaRecorder.AudioSource.VOICE_RECOGNITION)
        for (rate in intArrayOf(48_000, 44_100, 16_000)) {
            for (source in sources) {
                val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
                if (min <= 0) continue
                try {
                    val r = AudioRecord(source, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(min * 4, rate / 5 * 2))
                    if (r.state == AudioRecord.STATE_INITIALIZED) {
                        sampleRate = rate
                        Diagnostics.sampleRate = rate
                        Diagnostics.audioSource = sourceName(source)
                        return r
                    }
                    r.release()
                } catch (e: Exception) {
                    Log.w(TAG, "AudioRecord($source, $rate) failed", e)
                }
            }
        }
        Diagnostics.audioRecordState = "could not open AudioRecord"
        return null
    }

    private fun captureLoop(rec: AudioRecord, pcmOut: File?, onLevel: (Float, Long) -> Unit) {
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO)
        val chunk = sampleRate / 50 // 20 ms
        val buf = ShortArray(chunk)
        val bytes = ByteArray(chunk * 2)
        val resampler = AudioDsp.To16k(sampleRate)
        val ts = AudioTimestamp()
        var lastLevelMs = 0L
        var rateWindowStart = SystemClock.elapsedRealtime()
        var rateWindowBytes = 0L
        var zeroFrames = 0L
        var out: OutputStream? = null
        try {
            if (pcmOut != null) out = BufferedOutputStream(FileOutputStream(pcmOut), 64 * 1024)
            while (running) {
                val n = rec.read(buf, 0, chunk)
                if (n <= 0) {
                    if (n < 0) {
                        Diagnostics.pcmReadErrors.incrementAndGet()
                        Log.w(TAG, "read error $n")
                        SystemClock.sleep(5)
                    }
                    continue
                }
                if (startNanos == 0L) startNanos = firstFrameNanos(rec, ts, n)
                if (out != null) {
                    for (i in 0 until n) {
                        val v = buf[i].toInt()
                        bytes[2 * i] = (v and 0xFF).toByte()
                        bytes[2 * i + 1] = (v shr 8 and 0xFF).toByte()
                    }
                    out.write(bytes, 0, n * 2)
                }
                frames += n

                // diagnostics: throughput and all-zero runs (what a silenced client gets)
                Diagnostics.pcmBytesRead.addAndGet(n * 2L)
                rateWindowBytes += n * 2L
                var allZero = true
                for (i in 0 until n) if (buf[i].toInt() != 0) { allZero = false; break }
                zeroFrames = if (allZero) zeroFrames + n else 0
                Diagnostics.zeroRunMs = zeroFrames * 1000 / sampleRate

                val now = SystemClock.elapsedRealtime()
                if (now - rateWindowStart >= 1_000) {
                    Diagnostics.pcmReadRate = rateWindowBytes * 1000.0 / (now - rateWindowStart)
                    Diagnostics.audioRecordRecordingState = recordingStateName(rec.recordingState)
                    rateWindowStart = now
                    rateWindowBytes = 0
                }
                if (now - lastLevelMs >= 40) {
                    lastLevelMs = now
                    val db = AudioDsp.levelDb(buf, n)
                    Diagnostics.vadLevelDb = db
                    onLevel(db, now)
                }
                val sink = pcm16kSink
                if (sink != null || recognizerFeed.active) {
                    val pcm16 = resampler.process(buf, n)
                    sink?.invoke(pcm16)
                    if (recognizerFeed.active) recognizerFeed.offer(pcm16)
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "writing audio failed", e)
        } finally {
            try { out?.close() } catch (_: IOException) {}
        }
    }

    /** Monotonic time of frame 0, from the audio HAL timestamp when available. */
    private fun firstFrameNanos(rec: AudioRecord, ts: AudioTimestamp, framesJustRead: Int): Long {
        try {
            if (rec.getTimestamp(ts, AudioTimestamp.TIMEBASE_MONOTONIC) == AudioRecord.SUCCESS && ts.nanoTime > 0) {
                return ts.nanoTime - ts.framePosition * 1_000_000_000L / sampleRate
            }
        } catch (_: Exception) {}
        // Fallback: the chunk we just read ended "now".
        return System.nanoTime() - framesJustRead * 1_000_000_000L / sampleRate
    }

    /**
     * Android 10+ tells an app when its capture is silenced because another app
     * (e.g. a camera app recording video with sound) has priority on the mic.
     */
    @RequiresApi(Build.VERSION_CODES.Q)
    private fun registerSilencingCallback(rec: AudioRecord) {
        val session = rec.audioSessionId
        val cb = object : AudioManager.AudioRecordingCallback() {
            override fun onRecordingConfigChanged(configs: MutableList<AudioRecordingConfiguration>?) {
                val mine = configs?.firstOrNull { it.clientAudioSessionId == session } ?: return
                val silenced = mine.isClientSilenced
                if (Diagnostics.micSilenced != silenced) {
                    Diagnostics.micSilenced = silenced
                    Diagnostics.log(if (silenced) "mic SILENCED by the system" else "mic no longer silenced")
                    onSilencedChanged?.invoke(silenced)
                }
            }
        }
        audioManager.registerAudioRecordingCallback(cb, Handler(Looper.getMainLooper()))
        recordingCallback = cb
        Diagnostics.micSilenced = false
    }

    private fun unregisterSilencingCallback() {
        val cb = recordingCallback ?: return
        recordingCallback = null
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            try { audioManager.unregisterAudioRecordingCallback(cb) } catch (_: Exception) {}
        }
    }

    private companion object {
        const val TAG = "AudioCapture"

        fun sourceName(s: Int) = when (s) {
            MediaRecorder.AudioSource.MIC -> "MIC"
            MediaRecorder.AudioSource.VOICE_RECOGNITION -> "VOICE_RECOGNITION"
            MediaRecorder.AudioSource.CAMCORDER -> "CAMCORDER"
            else -> "source $s"
        }

        fun stateName(s: Int) = when (s) {
            AudioRecord.STATE_INITIALIZED -> "INITIALIZED"
            AudioRecord.STATE_UNINITIALIZED -> "UNINITIALIZED"
            else -> "state $s"
        }

        fun recordingStateName(s: Int) = when (s) {
            AudioRecord.RECORDSTATE_RECORDING -> "RECORDING"
            AudioRecord.RECORDSTATE_STOPPED -> "STOPPED"
            else -> "state $s"
        }
    }
}

/**
 * Hands 16 kHz mono PCM16 to the system speech recognizer through a pipe
 * (EXTRA_AUDIO_SOURCE). Each recognizer session gets a fresh pipe
 * ([openSession]); a dedicated writer thread feeds it.
 *
 * The write end is non-blocking: if the recognizer never reads the pipe (it
 * ignored EXTRA_AUDIO_SOURCE), writes fail with EAGAIN once the pipe buffer is
 * full. That is counted ([Diagnostics.pipeFullDrops]) and is the evidence the
 * health check uses to stop such a recognizer instead of restarting it forever.
 */
class RecognizerAudioFeed {
    private val queue = ArrayBlockingQueue<ShortArray>(QUEUE_CHUNKS)
    @Volatile private var writeSide: ParcelFileDescriptor? = null
    private var readSide: ParcelFileDescriptor? = null
    @Volatile private var writerRunning = false
    private var writer: Thread? = null

    /** True while a recognizer session is attached. */
    val active: Boolean get() = writeSide != null

    fun start() {
        if (writerRunning) return
        writerRunning = true
        writer = Thread({ writeLoop() }, "lensprompt-asr-feed").apply { start() }
    }

    /** New pipe for a new recognizer session; returns the read end to pass to it. */
    @Synchronized
    fun openSession(): ParcelFileDescriptor {
        closeSession()
        val pipe = ParcelFileDescriptor.createPipe()
        try {
            val fd = pipe[1].fileDescriptor
            val flags = Os.fcntlInt(fd, OsConstants.F_GETFL, 0)
            Os.fcntlInt(fd, OsConstants.F_SETFL, flags or OsConstants.O_NONBLOCK)
        } catch (e: ErrnoException) {
            Log.w(TAG, "could not make the recognizer pipe non-blocking", e)
        }
        readSide = pipe[0]
        queue.clear()
        writeSide = pipe[1]
        return pipe[0]
    }

    @Synchronized
    fun closeSession() {
        try { writeSide?.close() } catch (_: IOException) {}
        writeSide = null
        try { readSide?.close() } catch (_: IOException) {}
        readSide = null
    }

    fun offer(samples: ShortArray) {
        if (!queue.offer(samples)) {
            queue.poll() // drop the oldest: the writer is behind
            queue.offer(samples)
        }
    }

    fun stop() {
        writerRunning = false
        writer?.interrupt()
        writer = null
        closeSession()
        queue.clear()
    }

    private fun writeLoop() {
        var bytes = ByteArray(0)
        while (writerRunning) {
            val chunk = try { queue.poll(200, TimeUnit.MILLISECONDS) } catch (_: InterruptedException) { break } ?: continue
            val w = writeSide ?: continue
            val len = chunk.size * 2
            if (bytes.size < len) bytes = ByteArray(len)
            for (i in chunk.indices) {
                val v = chunk[i].toInt()
                bytes[2 * i] = (v and 0xFF).toByte()
                bytes[2 * i + 1] = (v shr 8 and 0xFF).toByte()
            }
            // 20 ms at 16 kHz = 640 bytes < PIPE_BUF, so each write is atomic.
            try {
                val n = Os.write(w.fileDescriptor, bytes, 0, len)
                Diagnostics.pipeBytesWritten.addAndGet(n.toLong())
            } catch (e: ErrnoException) {
                if (e.errno == OsConstants.EAGAIN) {
                    Diagnostics.pipeFullDrops.incrementAndGet() // nobody is reading
                } else {
                    Diagnostics.pipeWriteFailures.incrementAndGet()
                    // Reader closed the pipe (session ended); wait for the next session.
                    synchronized(this) { if (writeSide === w) closeSession() }
                }
            } catch (e: Exception) {
                Diagnostics.pipeWriteFailures.incrementAndGet()
                synchronized(this) { if (writeSide === w) closeSession() }
            }
        }
    }

    private companion object {
        const val TAG = "RecognizerFeed"
        const val QUEUE_CHUNKS = 50 // ~1 s of 20 ms chunks
    }
}
