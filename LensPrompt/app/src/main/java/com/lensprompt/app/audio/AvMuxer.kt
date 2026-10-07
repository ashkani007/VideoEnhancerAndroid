package com.lensprompt.app.audio

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.media.MediaMuxer
import android.util.Log
import com.lensprompt.core.AudioDsp
import java.io.BufferedInputStream
import java.io.File
import java.io.FileDescriptor
import java.io.FileInputStream
import java.io.IOException
import java.nio.ByteBuffer

/**
 * Combines a CameraX video-only recording with the audio LensPrompt captured
 * itself, aligned to the video's first frame.
 *
 * Steps: PCM → AAC (MediaCodec) into a temporary .m4a with the alignment
 * applied, then both tracks are interleaved by timestamp into the final MP4
 * (MediaMuxer), keeping the video's rotation.
 */
object AvMuxer {

    private const val TAG = "AvMuxer"
    private const val AAC_BITRATE = 128_000

    /**
     * @param videoStartNanos System.nanoTime() of the first video frame.
     * @param output where the final MP4 goes (a MediaStore or file descriptor).
     */
    fun mux(video: File, audio: CapturedAudio, videoStartNanos: Long, output: FileDescriptor, workDir: File) {
        val align = AudioDsp.alignAudioToVideo(audio.startNanos, videoStartNanos, audio.sampleRate)
        val m4a = File(workDir, "lp_audio_${System.nanoTime()}.m4a")
        try {
            encodeAac(audio, align.skipFrames, align.startOffsetUs, m4a)
            interleave(video, m4a, output)
        } finally {
            m4a.delete()
        }
    }

    /** PCM16 mono → AAC-LC in an audio-only MP4 container. */
    fun encodeAac(audio: CapturedAudio, skipFrames: Long, startOffsetUs: Long, out: File) {
        val format = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, audio.sampleRate, 1).apply {
            setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC)
            setInteger(MediaFormat.KEY_BIT_RATE, AAC_BITRATE)
            setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 16 * 1024)
        }
        val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
        val muxer = MediaMuxer(out.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
        var track = -1
        var muxerStarted = false
        val input = BufferedInputStream(FileInputStream(audio.pcmFile), 64 * 1024)
        try {
            codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            codec.start()
            skipFully(input, skipFrames * 2)
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false
            var framesQueued = 0L
            val chunk = ByteArray(8 * 1024)
            while (!outputDone) {
                if (!inputDone) {
                    val inIndex = codec.dequeueInputBuffer(10_000)
                    if (inIndex >= 0) {
                        val buf = codec.getInputBuffer(inIndex)!!
                        buf.clear()
                        val want = minOf(buf.remaining(), chunk.size) and 1.inv()
                        val n = readFully(input, chunk, want)
                        val ptsUs = startOffsetUs + framesQueued * 1_000_000L / audio.sampleRate
                        if (n <= 0) {
                            codec.queueInputBuffer(inIndex, 0, 0, ptsUs, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            buf.put(chunk, 0, n)
                            codec.queueInputBuffer(inIndex, 0, n, ptsUs, 0)
                            framesQueued += n / 2
                        }
                    }
                }
                when (val outIndex = codec.dequeueOutputBuffer(info, 10_000)) {
                    MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        track = muxer.addTrack(codec.outputFormat)
                        muxer.start()
                        muxerStarted = true
                    }
                    MediaCodec.INFO_TRY_AGAIN_LATER -> Unit
                    else -> if (outIndex >= 0) {
                        val buf = codec.getOutputBuffer(outIndex)!!
                        val isConfig = (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0
                        if (!isConfig && info.size > 0 && muxerStarted) {
                            buf.position(info.offset)
                            buf.limit(info.offset + info.size)
                            muxer.writeSampleData(track, buf, info)
                        }
                        codec.releaseOutputBuffer(outIndex, false)
                        if ((info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) outputDone = true
                    }
                }
            }
        } finally {
            try { input.close() } catch (_: IOException) {}
            try { codec.stop() } catch (_: Exception) {}
            codec.release()
            try { if (muxerStarted) muxer.stop() } catch (e: Exception) { Log.w(TAG, "audio muxer stop", e) }
            muxer.release()
        }
    }

    /** Copies the video track and the audio track into one MP4, interleaved by time. */
    fun interleave(video: File, audioM4a: File, output: FileDescriptor) {
        val vEx = MediaExtractor().apply { setDataSource(video.absolutePath) }
        val aEx = MediaExtractor().apply { setDataSource(audioM4a.absolutePath) }
        val muxer = MediaMuxer(output, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
        var started = false
        try {
            val vTrack = selectTrack(vEx, "video/") ?: throw IOException("no video track")
            val aTrack = selectTrack(aEx, "audio/") ?: throw IOException("no audio track")
            val vOut = muxer.addTrack(vEx.getTrackFormat(vTrack))
            val aOut = muxer.addTrack(aEx.getTrackFormat(aTrack))
            muxer.setOrientationHint(rotationOf(video))
            muxer.start()
            started = true

            val buf = ByteBuffer.allocateDirect(4 * 1024 * 1024)
            val info = MediaCodec.BufferInfo()
            var vDone = false
            var aDone = false
            val videoEndUs = durationUs(vEx, vTrack)
            while (!vDone || !aDone) {
                val vt = if (vDone) Long.MAX_VALUE else vEx.sampleTime
                val at = if (aDone) Long.MAX_VALUE else aEx.sampleTime
                if (vt < 0) { vDone = true; continue }
                if (at < 0 || (videoEndUs > 0 && at > videoEndUs)) { aDone = true; continue }
                val useVideo = vt <= at
                val ex = if (useVideo) vEx else aEx
                buf.clear()
                val size = ex.readSampleData(buf, 0)
                if (size < 0) {
                    if (useVideo) vDone = true else aDone = true
                    continue
                }
                info.set(0, size, ex.sampleTime, toCodecFlags(ex.sampleFlags))
                muxer.writeSampleData(if (useVideo) vOut else aOut, buf, info)
                ex.advance()
            }
        } finally {
            try { if (started) muxer.stop() } catch (e: Exception) { Log.w(TAG, "muxer stop", e) }
            muxer.release()
            vEx.release()
            aEx.release()
        }
    }

    private fun selectTrack(ex: MediaExtractor, prefix: String): Int? {
        for (i in 0 until ex.trackCount) {
            val mime = ex.getTrackFormat(i).getString(MediaFormat.KEY_MIME) ?: continue
            if (mime.startsWith(prefix)) { ex.selectTrack(i); return i }
        }
        return null
    }

    private fun durationUs(ex: MediaExtractor, track: Int): Long {
        val f = ex.getTrackFormat(track)
        return if (f.containsKey(MediaFormat.KEY_DURATION)) f.getLong(MediaFormat.KEY_DURATION) else -1
    }

    private fun rotationOf(video: File): Int {
        val r = MediaMetadataRetriever()
        return try {
            r.setDataSource(video.absolutePath)
            r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toIntOrNull() ?: 0
        } catch (_: Exception) {
            0
        } finally {
            r.release()
        }
    }

    private fun toCodecFlags(extractorFlags: Int): Int {
        var f = 0
        if ((extractorFlags and MediaExtractor.SAMPLE_FLAG_SYNC) != 0) f = f or MediaCodec.BUFFER_FLAG_KEY_FRAME
        return f
    }

    private fun skipFully(input: BufferedInputStream, bytes: Long) {
        var left = bytes
        while (left > 0) {
            val s = input.skip(left)
            if (s <= 0) break
            left -= s
        }
    }

    private fun readFully(input: BufferedInputStream, buf: ByteArray, len: Int): Int {
        var total = 0
        while (total < len) {
            val n = input.read(buf, total, len - total)
            if (n < 0) break
            total += n
        }
        return if (total == 0 && len > 0) -1 else total
    }
}
