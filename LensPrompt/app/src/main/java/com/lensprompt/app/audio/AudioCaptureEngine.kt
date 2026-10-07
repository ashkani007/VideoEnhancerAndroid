package com.lensprompt.app.audio

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTimestamp
import android.media.MediaRecorder
import android.os.ParcelFileDescriptor
import android.os.Process
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat
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
 * The one microphone stream while video is being recorded.
 *
 * Why it exists: CameraX records sound from the CAMCORDER source, which Android
 * treats as privacy-sensitive; while it is captured, other apps (including the
 * system speech-recognition service) receive silence. So during recording
 * LensPrompt captures the microphone once, itself, and fans the samples out:
 *  1. raw PCM to a file, later encoded and muxed into the video,
 *  2. levels for voice-activity detection (Smart Follow pacing),
 *  3. 16 kHz PCM to the speech recognizer through a pipe (Android 13+).
 *
 * The capture thread never blocks on consumers: the recognizer feed has its own
 * writer thread and drops old chunks if the recognizer falls behind.
 */
class AudioCaptureEngine(private val context: Context) {

    private var record: AudioRecord? = null
    private var thread: Thread? = null
    @Volatile private var running = false

    private var sampleRate = 48_000
    private var pcmFile: File? = null
    @Volatile private var startNanos = 0L
    @Volatile private var frames = 0L

    val recognizerFeed = RecognizerAudioFeed()

    /**
     * @param onLevel called on the capture thread ~25×/s with (level dB, elapsedRealtime ms).
     * @return false if the microphone could not be opened (permission, in use, no mic).
     */
    @SuppressLint("MissingPermission") // checked below
    fun start(pcmOut: File, onLevel: (Float, Long) -> Unit): Boolean {
        stop()
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            return false
        }
        val rec = openRecord() ?: return false
        record = rec
        pcmFile = pcmOut
        frames = 0
        startNanos = 0
        try {
            rec.startRecording()
        } catch (e: Exception) {
            Log.e(TAG, "startRecording failed", e)
            rec.release(); record = null
            return false
        }
        if (rec.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
            Log.e(TAG, "microphone did not start (in use by another app?)")
            rec.release(); record = null
            return false
        }
        running = true
        recognizerFeed.start()
        thread = Thread({ captureLoop(rec, pcmOut, onLevel) }, "lensprompt-mic").apply { start() }
        return true
    }

    /** Stops capture and returns what was recorded (null if nothing usable). */
    fun stop(): CapturedAudio? {
        if (!running && record == null) return null
        running = false
        thread?.join(2_000)
        thread = null
        try { record?.stop() } catch (_: Exception) {}
        record?.release()
        record = null
        recognizerFeed.stop()
        val file = pcmFile ?: return null
        pcmFile = null
        return if (frames > 0 && startNanos != 0L) CapturedAudio(file, sampleRate, startNanos, frames) else null
    }

    @SuppressLint("MissingPermission")
    private fun openRecord(): AudioRecord? {
        for (rate in intArrayOf(48_000, 44_100, 16_000)) {
            for (source in intArrayOf(MediaRecorder.AudioSource.CAMCORDER, MediaRecorder.AudioSource.MIC)) {
                val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
                if (min <= 0) continue
                try {
                    val r = AudioRecord(source, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(min * 4, rate / 5 * 2))
                    if (r.state == AudioRecord.STATE_INITIALIZED) {
                        sampleRate = rate
                        return r
                    }
                    r.release()
                } catch (e: Exception) {
                    Log.w(TAG, "AudioRecord($source, $rate) failed", e)
                }
            }
        }
        return null
    }

    private fun captureLoop(rec: AudioRecord, pcmOut: File, onLevel: (Float, Long) -> Unit) {
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO)
        val chunk = sampleRate / 50 // 20 ms
        val buf = ShortArray(chunk)
        val bytes = ByteArray(chunk * 2)
        val resampler = AudioDsp.To16k(sampleRate)
        val ts = AudioTimestamp()
        var lastLevelMs = 0L
        var out: OutputStream? = null
        try {
            out = BufferedOutputStream(FileOutputStream(pcmOut), 64 * 1024)
            while (running) {
                val n = rec.read(buf, 0, chunk)
                if (n <= 0) {
                    if (n < 0) Log.w(TAG, "read error $n")
                    continue
                }
                if (startNanos == 0L) startNanos = firstFrameNanos(rec, ts, n)
                for (i in 0 until n) {
                    val v = buf[i].toInt()
                    bytes[2 * i] = (v and 0xFF).toByte()
                    bytes[2 * i + 1] = (v shr 8 and 0xFF).toByte()
                }
                out.write(bytes, 0, n * 2)
                frames += n

                val now = SystemClock.elapsedRealtime()
                if (now - lastLevelMs >= 40) {
                    lastLevelMs = now
                    onLevel(AudioDsp.levelDb(buf, n), now)
                }
                if (recognizerFeed.active) recognizerFeed.offer(resampler.process(buf, n))
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

    private companion object { const val TAG = "AudioCapture" }
}

/**
 * Hands 16 kHz mono PCM16 to a speech recognizer through a pipe. Each
 * recognizer session gets a fresh pipe ([openSession]); a dedicated writer
 * thread feeds it so a slow or finished reader can never stall capture.
 */
class RecognizerAudioFeed {
    private val queue = ArrayBlockingQueue<ShortArray>(QUEUE_CHUNKS)
    @Volatile private var out: ParcelFileDescriptor.AutoCloseOutputStream? = null
    private var readSide: ParcelFileDescriptor? = null
    @Volatile private var writerRunning = false
    private var writer: Thread? = null

    /** True while a recognizer session is attached. */
    val active: Boolean get() = out != null

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
        readSide = pipe[0]
        queue.clear()
        out = ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])
        return pipe[0]
    }

    @Synchronized
    fun closeSession() {
        try { out?.close() } catch (_: IOException) {}
        out = null
        try { readSide?.close() } catch (_: IOException) {}
        readSide = null
    }

    fun offer(samples: ShortArray) {
        if (!queue.offer(samples)) {
            queue.poll() // drop the oldest: the recognizer is behind
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
            val o = out ?: continue
            if (bytes.size < chunk.size * 2) bytes = ByteArray(chunk.size * 2)
            for (i in chunk.indices) {
                val v = chunk[i].toInt()
                bytes[2 * i] = (v and 0xFF).toByte()
                bytes[2 * i + 1] = (v shr 8 and 0xFF).toByte()
            }
            try {
                o.write(bytes, 0, chunk.size * 2)
            } catch (_: IOException) {
                // Reader closed the pipe (session ended); wait for the next session.
                synchronized(this) { if (out === o) out = null }
            }
        }
    }

    private companion object { const val QUEUE_CHUNKS = 50 } // ~1 s of 20 ms chunks
}
