package com.vrvision.app.enhance

import android.content.Context
import android.media.Image
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.media.MediaMuxer
import android.net.Uri
import android.os.PowerManager
import android.os.SystemClock
import com.vrvision.core.enhance.ColorMatrix
import com.vrvision.core.enhance.FrameUpscaler
import com.vrvision.core.enhance.PixelOps
import com.vrvision.core.enhance.SrEngine
import com.vrvision.core.enhance.Yuv420
import com.vrvision.core.stereo.StereoLayout
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.io.File
import java.nio.ByteBuffer
import kotlin.math.abs

class UnsupportedProcessingException(message: String, cause: Throwable? = null) : Exception(message, cause)

data class LocalRequest(
    val source: Uri,
    val startUs: Long,
    /** Exclusive end; Long.MAX_VALUE for the whole file. */
    val endUs: Long,
    val outWidth: Int,
    val outHeight: Int,
    val layout: StereoLayout,
    val outputMime: String,
    val bitrate: Int,
    /** 0 disables sharpening. Conventional unsharp mask on luma, not AI. */
    val sharpenAmount: Float,
    val output: File,
)

data class LocalProgress(val framesDone: Int, val framesExpected: Int, val stage: String, val msPerSourceMegapixel: Double?)

data class ValidationReport(
    val ok: Boolean,
    val width: Int,
    val height: Int,
    val durationUs: Long,
    val videoMime: String?,
    val frameCount: Int?,
    val hasAudio: Boolean,
    val firstFrameDecodes: Boolean,
    val problems: List<String>,
)

data class LocalResult(
    val framesIn: Int,
    val framesOut: Int,
    val elapsedMs: Long,
    val msPerSourceMegapixel: Double,
    val audioRemuxed: Boolean,
    val audioNote: String?,
    val validation: ValidationReport,
)

/**
 * Local AI enhancement: decode → (8-bit RGB) → tiled AI super resolution (4x native, area
 * resampled to the requested size) → optional conventional sharpening → encode → mux with the
 * original AAC audio → validate. Frames keep their original presentation timestamps (shifted
 * so the output starts at 0) and order.
 */
class LocalEnhancer(private val context: Context, private val engine: SrEngine) {

    private val timeoutUs = 10_000L

    suspend fun run(req: LocalRequest, onProgress: suspend (LocalProgress) -> Unit): LocalResult {
        val started = SystemClock.elapsedRealtime()
        val extractor = MediaExtractor()
        var decoder: MediaCodec? = null
        var encoder: MediaCodec? = null
        var muxer: MediaMuxer? = null
        val audio = AudioCopier(context, req)
        var success = false
        try {
            extractor.setDataSource(context, req.source, null)
            val vTrack = (0 until extractor.trackCount).firstOrNull {
                extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("video/") == true
            } ?: throw UnsupportedProcessingException("No video track.")
            val inFormat = extractor.getTrackFormat(vTrack)
            val inMime = inFormat.getString(MediaFormat.KEY_MIME)!!
            val srcW = inFormat.getInteger(MediaFormat.KEY_WIDTH)
            val srcH = inFormat.getInteger(MediaFormat.KEY_HEIGHT)
            val fps = if (inFormat.containsKey(MediaFormat.KEY_FRAME_RATE)) inFormat.getInteger(MediaFormat.KEY_FRAME_RATE) else 30
            val durationUs = if (inFormat.containsKey(MediaFormat.KEY_DURATION)) inFormat.getLong(MediaFormat.KEY_DURATION) else 0L
            val rotation = if (inFormat.containsKey(MediaFormat.KEY_ROTATION)) inFormat.getInteger(MediaFormat.KEY_ROTATION) else 0
            val segmentUs = (minOf(req.endUs, durationUs) - req.startUs).coerceAtLeast(0)
            val framesExpected = (segmentUs * fps / 1_000_000L).toInt().coerceAtLeast(1)
            if (req.outWidth > srcW * engine.scale || req.outHeight > srcH * engine.scale) {
                throw UnsupportedProcessingException("Requested size exceeds the model's ${engine.scale}× native scale.")
            }

            extractor.selectTrack(vTrack)
            extractor.seekTo(req.startUs, MediaExtractor.SEEK_TO_PREVIOUS_SYNC)
            inFormat.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
            decoder = MediaCodec.createDecoderByType(inMime).apply { configure(inFormat, null, null, 0); start() }

            val outFormat = MediaFormat.createVideoFormat(req.outputMime, req.outWidth, req.outHeight).apply {
                setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
                setInteger(MediaFormat.KEY_BIT_RATE, req.bitrate)
                setInteger(MediaFormat.KEY_FRAME_RATE, fps)
                setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
                setInteger(MediaFormat.KEY_COLOR_STANDARD, MediaFormat.COLOR_STANDARD_BT709)
                setInteger(MediaFormat.KEY_COLOR_RANGE, MediaFormat.COLOR_RANGE_LIMITED)
                setInteger(MediaFormat.KEY_COLOR_TRANSFER, MediaFormat.COLOR_TRANSFER_SDR_VIDEO)
            }
            encoder = try {
                MediaCodec.createEncoderByType(req.outputMime).apply { configure(outFormat, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE); start() }
            } catch (e: Exception) {
                throw UnsupportedProcessingException("The ${req.outputMime} encoder rejected ${req.outWidth}×${req.outHeight}.", e)
            }

            req.output.parentFile?.mkdirs()
            muxer = MediaMuxer(req.output.path, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4).apply { setOrientationHint(rotation) }
            val muxState = MuxState(muxer, audio)

            val upscaler = FrameUpscaler(engine)
            val srcRgb = ByteArray(srcW * srcH * 3)
            val outRgb = ByteArray(req.outWidth * req.outHeight * 3)
            val outYuv = Yuv420.i420(req.outWidth, req.outHeight)
            val inPlanes = PlaneCopy()
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var decodeDone = false
            var framesIn = 0
            var framesOut = 0
            var lastPtsOut = -1L
            var srMs = 0L
            val pm = context.getSystemService(PowerManager::class.java)
            val srcMp = srcW.toDouble() * srcH / 1e6

            while (!decodeDone) {
                currentCoroutineContext().ensureActive()
                if (pm.currentThermalStatus >= PowerManager.THERMAL_STATUS_SEVERE) {
                    throw UnsupportedProcessingException("Stopped because the phone became too hot. Let it cool down and try again.")
                }
                if (!inputDone) {
                    val idx = decoder.dequeueInputBuffer(timeoutUs)
                    if (idx >= 0) {
                        val buf = decoder.getInputBuffer(idx)!!
                        val size = extractor.readSampleData(buf, 0)
                        val t = extractor.sampleTime
                        if (size < 0 || t >= req.endUs) {
                            decoder.queueInputBuffer(idx, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            decoder.queueInputBuffer(idx, 0, size, t, extractor.sampleFlags and MediaCodec.BUFFER_FLAG_KEY_FRAME)
                            extractor.advance()
                        }
                    }
                }
                val outIdx = decoder.dequeueOutputBuffer(info, timeoutUs)
                if (outIdx < 0) continue
                val eos = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                val pts = info.presentationTimeUs
                if (info.size > 0 && pts >= req.startUs && pts < req.endUs) {
                    val image = decoder.getOutputImage(outIdx) ?: throw UnsupportedProcessingException("Decoder produced no image buffer.")
                    val matrix = colorMatrix(decoder.outputFormat, srcH)
                    PixelOps.yuvToRgb(inPlanes.from(image, srcW, srcH), matrix, srcRgb)
                    decoder.releaseOutputBuffer(outIdx, false)
                    framesIn++

                    val t0 = SystemClock.elapsedRealtime()
                    upscaler.upscale(srcRgb, srcW, srcH, req.layout, outRgb, req.outWidth, req.outHeight)
                    srMs += SystemClock.elapsedRealtime() - t0
                    PixelOps.rgbPackedToYuv(outRgb, req.outWidth, req.outHeight, outYuv, ColorMatrix.BT709)
                    if (req.sharpenAmount > 0f) PixelOps.unsharpLuma(outYuv, req.sharpenAmount)

                    val outPts = pts - req.startUs
                    check(outPts > lastPtsOut) { "Non-increasing timestamp $outPts after $lastPtsOut" }
                    lastPtsOut = outPts
                    feedEncoder(encoder, outYuv, outPts, eos = false)
                    framesOut += drainEncoder(encoder, muxState, endOfStream = false)
                    onProgress(LocalProgress(framesIn, framesExpected, "Enhancing frame $framesIn", srMs.toDouble() / framesIn / srcMp))
                } else {
                    decoder.releaseOutputBuffer(outIdx, false)
                }
                if (eos) decodeDone = true
            }
            if (framesIn == 0) throw UnsupportedProcessingException("No frames were decoded in the selected range.")
            feedEncoder(encoder, null, lastPtsOut + 1, eos = true)
            framesOut += drainEncoder(encoder, muxState, endOfStream = true)
            muxState.finishAudio()
            muxer.stop()
            muxer.release(); muxer = null

            onProgress(LocalProgress(framesIn, framesExpected, "Validating output", null))
            val validation = OutputValidator.validate(context, req.output, req.outWidth, req.outHeight, req.outputMime, framesOut, lastPtsOut, muxState.audioAdded)
            success = validation.ok
            val elapsed = SystemClock.elapsedRealtime() - started
            return LocalResult(
                framesIn = framesIn, framesOut = framesOut, elapsedMs = elapsed,
                msPerSourceMegapixel = elapsed.toDouble() / framesIn / srcMp,
                audioRemuxed = muxState.audioAdded, audioNote = audio.note, validation = validation,
            )
        } catch (e: OutOfMemoryError) {
            throw UnsupportedProcessingException("Not enough memory for ${req.outWidth}×${req.outHeight} on this phone.", e)
        } finally {
            try { decoder?.stop() } catch (_: Exception) { }
            decoder?.release()
            try { encoder?.stop() } catch (_: Exception) { }
            encoder?.release()
            try { muxer?.release() } catch (_: Exception) { }
            extractor.release()
            audio.release()
            if (!success) req.output.delete()
        }
    }

    private fun colorMatrix(format: MediaFormat, height: Int): ColorMatrix =
        when (if (format.containsKey(MediaFormat.KEY_COLOR_STANDARD)) format.getInteger(MediaFormat.KEY_COLOR_STANDARD) else -1) {
            MediaFormat.COLOR_STANDARD_BT709 -> ColorMatrix.BT709
            MediaFormat.COLOR_STANDARD_BT601_PAL, MediaFormat.COLOR_STANDARD_BT601_NTSC -> ColorMatrix.BT601
            else -> ColorMatrix.forHeight(height)
        }

    private fun feedEncoder(encoder: MediaCodec, yuv: Yuv420?, ptsUs: Long, eos: Boolean) {
        while (true) {
            val idx = encoder.dequeueInputBuffer(timeoutUs)
            if (idx < 0) continue
            if (eos || yuv == null) {
                encoder.queueInputBuffer(idx, 0, 0, ptsUs, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                return
            }
            val image = encoder.getInputImage(idx) ?: throw UnsupportedProcessingException("Encoder offers no image input.")
            writeImage(yuv, image)
            encoder.queueInputBuffer(idx, 0, yuv.width * yuv.height * 3 / 2, ptsUs, 0)
            return
        }
    }

    /** Writes encoded samples; returns the number of video frames written. */
    private fun drainEncoder(encoder: MediaCodec, mux: MuxState, endOfStream: Boolean): Int {
        val info = MediaCodec.BufferInfo()
        var frames = 0
        while (true) {
            val idx = encoder.dequeueOutputBuffer(info, timeoutUs)
            when {
                idx == MediaCodec.INFO_TRY_AGAIN_LATER -> if (!endOfStream) return frames
                idx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> mux.start(encoder.outputFormat)
                idx >= 0 -> {
                    val buf = encoder.getOutputBuffer(idx)!!
                    if (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) info.size = 0
                    if (info.size > 0) {
                        check(mux.started) { "Encoder output before format" }
                        buf.position(info.offset); buf.limit(info.offset + info.size)
                        mux.writeVideo(buf, info)
                        frames++
                    }
                    encoder.releaseOutputBuffer(idx, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) return frames
                }
            }
        }
    }

    private fun writeImage(src: Yuv420, image: Image) {
        val planes = image.planes
        val w = src.width; val h = src.height
        copyPlane(src.y, src.yOffset, src.yRowStride, 1, planes[0].buffer, planes[0].rowStride, planes[0].pixelStride, w, h)
        copyPlane(src.u, src.uOffset, src.uRowStride, src.uPixelStride, planes[1].buffer, planes[1].rowStride, planes[1].pixelStride, (w + 1) / 2, (h + 1) / 2)
        copyPlane(src.v, src.vOffset, src.vRowStride, src.vPixelStride, planes[2].buffer, planes[2].rowStride, planes[2].pixelStride, (w + 1) / 2, (h + 1) / 2)
    }

    private fun copyPlane(src: ByteArray, off: Int, rowStride: Int, pixStride: Int, dst: ByteBuffer, dRow: Int, dPix: Int, w: Int, h: Int) {
        for (row in 0 until h) {
            if (pixStride == 1 && dPix == 1) {
                dst.position(row * dRow)
                dst.put(src, off + row * rowStride, w)
            } else {
                for (col in 0 until w) dst.put(row * dRow + col * dPix, src[off + row * rowStride + col * pixStride])
            }
        }
    }

    /** Copies decoder Image planes into reusable arrays. */
    private class PlaneCopy {
        private var y = ByteArray(0); private var u = ByteArray(0); private var v = ByteArray(0)
        fun from(image: Image, w: Int, h: Int): Yuv420 {
            val p = image.planes
            y = read(p[0].buffer, y); u = read(p[1].buffer, u); v = read(p[2].buffer, v)
            return Yuv420(w, h, y, 0, p[0].rowStride, u, 0, p[1].rowStride, p[1].pixelStride, v, 0, p[2].rowStride, p[2].pixelStride)
        }
        private fun read(b: ByteBuffer, reuse: ByteArray): ByteArray {
            val n = b.remaining()
            val arr = if (reuse.size >= n) reuse else ByteArray(n)
            b.get(arr, 0, n)
            return arr
        }
    }

    /** Starts the muxer once the encoder format is known and interleaves audio by timestamp. */
    private class MuxState(private val muxer: MediaMuxer, private val audio: AudioCopier) {
        var started = false; private set
        var audioAdded = false; private set
        private var videoTrack = -1
        fun start(videoFormat: MediaFormat) {
            if (started) return
            videoTrack = muxer.addTrack(videoFormat)
            audioAdded = audio.addTrack(muxer)
            muxer.start()
            started = true
        }
        fun writeVideo(buf: ByteBuffer, info: MediaCodec.BufferInfo) {
            muxer.writeSampleData(videoTrack, buf, info)
            if (audioAdded) audio.copyUntil(muxer, info.presentationTimeUs)
        }
        fun finishAudio() { if (audioAdded) audio.copyUntil(muxer, Long.MAX_VALUE) }
    }
}

/** Copies the source's AAC audio for the processed range, timestamps shifted like the video. */
private class AudioCopier(context: Context, private val req: LocalRequest) {
    private val extractor = MediaExtractor()
    private var track = -1
    private var muxTrack = -1
    private var buffer: ByteBuffer? = null
    private var done = false
    var note: String? = null; private set

    init {
        try {
            extractor.setDataSource(context, req.source, null)
            for (i in 0 until extractor.trackCount) {
                val mime = extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("audio/")) {
                    if (mime == MediaFormat.MIMETYPE_AUDIO_AAC) { track = i } else note = "Audio ($mime) can't be copied into MP4 without re-encoding; output has no audio."
                    break
                }
            }
            if (track < 0 && note == null) note = "Source has no audio track."
        } catch (e: Exception) {
            note = "Audio could not be read: ${e.message}"
        }
    }

    fun addTrack(muxer: MediaMuxer): Boolean {
        if (track < 0) return false
        val f = extractor.getTrackFormat(track)
        muxTrack = muxer.addTrack(f)
        extractor.selectTrack(track)
        extractor.seekTo(req.startUs, MediaExtractor.SEEK_TO_CLOSEST_SYNC)
        buffer = ByteBuffer.allocate(if (f.containsKey(MediaFormat.KEY_MAX_INPUT_SIZE)) f.getInteger(MediaFormat.KEY_MAX_INPUT_SIZE) else 256 * 1024)
        return true
    }

    fun copyUntil(muxer: MediaMuxer, videoPtsUs: Long) {
        val buf = buffer ?: return
        val info = MediaCodec.BufferInfo()
        while (!done) {
            val t = extractor.sampleTime
            if (t < 0 || t >= req.endUs) { done = true; return }
            val outPts = t - req.startUs
            if (outPts > videoPtsUs) return
            buf.clear()
            val size = extractor.readSampleData(buf, 0)
            if (size < 0) { done = true; return }
            if (outPts >= 0) {
                info.set(0, size, outPts, if (extractor.sampleFlags and MediaExtractor.SAMPLE_FLAG_SYNC != 0) MediaCodec.BUFFER_FLAG_KEY_FRAME else 0)
                muxer.writeSampleData(muxTrack, buf, info)
            }
            extractor.advance()
        }
    }

    fun release() = extractor.release()
}

object OutputValidator {
    fun validate(
        context: Context, file: java.io.File, width: Int, height: Int, mime: String,
        framesWritten: Int, lastPtsUs: Long, expectAudio: Boolean,
    ): ValidationReport {
        val problems = mutableListOf<String>()
        var w = 0; var h = 0; var dur = 0L; var vMime: String? = null; var hasAudio = false
        val ex = MediaExtractor()
        try {
            ex.setDataSource(file.path)
            for (i in 0 until ex.trackCount) {
                val f = ex.getTrackFormat(i)
                val m = f.getString(MediaFormat.KEY_MIME) ?: continue
                if (m.startsWith("video/")) {
                    vMime = m; w = f.getInteger(MediaFormat.KEY_WIDTH); h = f.getInteger(MediaFormat.KEY_HEIGHT)
                    if (f.containsKey(MediaFormat.KEY_DURATION)) dur = f.getLong(MediaFormat.KEY_DURATION)
                }
                if (m.startsWith("audio/")) hasAudio = true
            }
        } catch (e: Exception) {
            problems += "Output can't be opened: ${e.message}"
        } finally { ex.release() }

        var frameCount: Int? = null
        var firstFrame = false
        val r = MediaMetadataRetriever()
        try {
            r.setDataSource(file.path)
            frameCount = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_FRAME_COUNT)?.toIntOrNull()
            firstFrame = r.getFrameAtTime(0) != null
        } catch (_: Exception) {
        } finally { try { r.release() } catch (_: Exception) { } }

        if (vMime != mime) problems += "Video codec is $vMime, expected $mime."
        if (w != width || h != height) problems += "Resolution is ${w}×$h, expected ${width}×$height."
        if (frameCount != null && frameCount != framesWritten) problems += "Container has $frameCount frames, $framesWritten were encoded."
        if (dur > 0 && abs(dur - lastPtsUs) > 200_000) problems += "Duration ${dur / 1000} ms does not match the last frame time ${lastPtsUs / 1000} ms."
        if (expectAudio && !hasAudio) problems += "Audio track missing."
        if (!firstFrame) problems += "The first frame could not be decoded."
        return ValidationReport(problems.isEmpty(), w, h, dur, vMime, frameCount, hasAudio, firstFrame, problems)
    }
}
