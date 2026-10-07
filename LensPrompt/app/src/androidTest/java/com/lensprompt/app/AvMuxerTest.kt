package com.lensprompt.app

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.lensprompt.app.audio.AvMuxer
import com.lensprompt.app.audio.CapturedAudio
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import kotlin.math.PI
import kotlin.math.sin

/**
 * The recording-with-sound path on a real Android media stack: a video-only MP4
 * (as CameraX produces while LensPrompt owns the microphone) is muxed with
 * app-captured PCM, aligned to the video's first frame.
 */
@RunWith(AndroidJUnit4::class)
class AvMuxerTest {

    private val dir: File get() = InstrumentationRegistry.getInstrumentation().targetContext.cacheDir

    @Test
    fun appCapturedAudioIsMuxedAlignedAndTrimmed() {
        val video = File(dir, "t_video.mp4").also { writeTestVideo(it, seconds = 2, fps = 15) }
        // Audio capture started 250 ms before the first video frame and ran 2.5 s.
        val rate = 48_000
        val pcm = File(dir, "t_audio.pcm")
        val frames = writeSinePcm(pcm, rate, seconds = 2.5)
        val audioStart = 10_000_000_000L
        val videoStart = audioStart + 250_000_000L
        val out = File(dir, "t_out.mp4").also { it.delete() }

        RandomAccessFile(out, "rw").use { raf ->
            AvMuxer.mux(video, CapturedAudio(pcm, rate, audioStart, frames), videoStart, raf.fd, dir)
        }

        val ex = MediaExtractor().apply { setDataSource(out.absolutePath) }
        var videoTracks = 0
        var audioTrack = -1
        for (i in 0 until ex.trackCount) {
            val mime = ex.getTrackFormat(i).getString(MediaFormat.KEY_MIME)!!
            if (mime.startsWith("video/")) videoTracks++
            if (mime.startsWith("audio/")) audioTrack = i
        }
        assertEquals(1, videoTracks)
        assertTrue("no audio track", audioTrack >= 0)

        ex.selectTrack(audioTrack)
        val first = ex.sampleTime
        var last = first
        var samples = 0
        while (ex.sampleTime >= 0) {
            last = ex.sampleTime
            samples++
            ex.advance()
        }
        ex.release()
        assertTrue("audio should start at the first video frame, was $first us", first in 0..50_000)
        // 2.5 s captured − 0.25 s before video = 2.25 s, trimmed to the 2 s video.
        assertTrue("audio should end with the video, last=$last us", last in 1_800_000..2_150_000)
        assertTrue("too few audio frames: $samples", samples > 80)

        video.delete(); pcm.delete(); out.delete()
    }

    private fun writeSinePcm(file: File, rate: Int, seconds: Double): Long {
        val n = (rate * seconds).toInt()
        val bytes = ByteArray(n * 2)
        for (i in 0 until n) {
            val v = (8_000 * sin(2 * PI * 440 * i / rate)).toInt()
            bytes[2 * i] = (v and 0xFF).toByte()
            bytes[2 * i + 1] = ((v shr 8) and 0xFF).toByte()
        }
        FileOutputStream(file).use { it.write(bytes) }
        return n.toLong()
    }

    /** Small H.264 clip written with MediaCodec + MediaMuxer (gray frames). */
    private fun writeTestVideo(file: File, seconds: Int, fps: Int, w: Int = 320, h: Int = 240) {
        val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, w, h).apply {
            setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
            setInteger(MediaFormat.KEY_BIT_RATE, 400_000)
            setInteger(MediaFormat.KEY_FRAME_RATE, fps)
            setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
        }
        val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
        codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        codec.start()
        val muxer = MediaMuxer(file.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
        var track = -1
        var started = false
        val total = seconds * fps
        var queued = 0
        var inputDone = false
        val info = MediaCodec.BufferInfo()
        try {
            while (true) {
                if (!inputDone) {
                    val idx = codec.dequeueInputBuffer(10_000)
                    if (idx >= 0) {
                        val pts = queued * 1_000_000L / fps
                        if (queued >= total) {
                            codec.queueInputBuffer(idx, 0, 0, pts, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            val image = codec.getInputImage(idx)!!
                            for ((p, plane) in image.planes.withIndex()) {
                                val pw = if (p == 0) w else w / 2
                                val ph = if (p == 0) h else h / 2
                                val value = (if (p == 0) 60 + queued * 3 else 128).toByte()
                                val buf = plane.buffer
                                for (y in 0 until ph) for (x in 0 until pw) {
                                    val pos = y * plane.rowStride + x * plane.pixelStride
                                    if (pos < buf.capacity()) buf.put(pos, value)
                                }
                            }
                            codec.queueInputBuffer(idx, 0, w * h * 3 / 2, pts, 0)
                            queued++
                        }
                    }
                }
                val out = codec.dequeueOutputBuffer(info, 10_000)
                if (out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    track = muxer.addTrack(codec.outputFormat)
                    muxer.start()
                    started = true
                } else if (out >= 0) {
                    val buf = codec.getOutputBuffer(out)!!
                    if ((info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0 && info.size > 0 && started) {
                        buf.position(info.offset); buf.limit(info.offset + info.size)
                        muxer.writeSampleData(track, buf, info)
                    }
                    codec.releaseOutputBuffer(out, false)
                    if ((info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) break
                }
            }
        } finally {
            codec.stop(); codec.release()
            if (started) muxer.stop()
            muxer.release()
        }
    }
}
