package com.vrvision.app

import android.graphics.Bitmap
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.vrvision.app.enhance.LocalEnhancer
import com.vrvision.app.enhance.LocalRequest
import com.vrvision.app.enhance.ModelRegistry
import com.vrvision.app.enhance.OrtSrEngine
import com.vrvision.core.stereo.StereoLayout
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import kotlin.math.abs

/**
 * Runs the real local enhancement pipeline on the device/emulator: MediaCodec decode, ONNX Runtime
 * inference with the bundled Real-ESRGAN model, encode, AAC remux and output validation.
 */
@RunWith(AndroidJUnit4::class)
class LocalEnhancerDeviceTest {

    private val ctx get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val testCtx get() = InstrumentationRegistry.getInstrumentation().context

    @Test
    fun enhancesStereoClipWithRealModel(): Unit = runBlocking {
        val src = File(ctx.cacheDir, "test_sbs.mp4")
        testCtx.assets.open("test_sbs.mp4").use { input -> src.outputStream().use { input.copyTo(it) } }
        val registry = ModelRegistry(ctx)
        val model = registry.forDenoise(true)!!
        val out = File(ctx.cacheDir, "enhanced.mp4").apply { delete() }
        val started = System.nanoTime()
        val result = OrtSrEngine(registry.loadVerified(model)).use { engine ->
            LocalEnhancer(ctx, engine).run(
                LocalRequest(
                    source = Uri.fromFile(src), startUs = 0, endUs = Long.MAX_VALUE,
                    outWidth = 320, outHeight = 128, layout = StereoLayout.SIDE_BY_SIDE,
                    outputMime = "video/avc", bitrate = 2_000_000, sharpenAmount = 0.3f, output = out,
                ),
            ) { }
        }
        val seconds = (System.nanoTime() - started) / 1e9
        println("VRVISION_DEVICE_TEST frames=${result.framesOut} seconds=$seconds msPerMp=${result.msPerSourceMegapixel} audio=${result.audioRemuxed} note=${result.audioNote}")
        assertTrue(result.validation.problems.joinToString(), result.validation.ok)
        assertEquals(15, result.framesIn)
        assertEquals(15, result.framesOut)
        assertEquals(320, result.validation.width)
        assertEquals(128, result.validation.height)
        assertTrue("AAC audio should be copied", result.audioRemuxed)

        // The clip's eyes are identical; after per-eye AI processing they must stay (nearly)
        // identical — only codec noise may differ.
        val frame: Bitmap = MediaMetadataRetriever().run {
            setDataSource(out.path)
            getFrameAtTime(0, MediaMetadataRetriever.OPTION_CLOSEST)!!.also { release() }
        }
        var diff = 0L
        for (y in 0 until frame.height) for (x in 0 until frame.width / 2) {
            val a = frame.getPixel(x, y); val b = frame.getPixel(x + frame.width / 2, y)
            diff += abs((a shr 16 and 0xFF) - (b shr 16 and 0xFF)) + abs((a shr 8 and 0xFF) - (b shr 8 and 0xFF)) + abs((a and 0xFF) - (b and 0xFF))
        }
        val mean = diff.toDouble() / (frame.height * frame.width / 2 * 3)
        println("VRVISION_DEVICE_TEST eyeMeanAbsDiff=$mean")
        assertTrue("eyes diverged: $mean", mean < 4.0)
    }

    @Test
    fun corruptedModelIsRefused() {
        val registry = ModelRegistry(ctx)
        val bad = registry.models.first().copy(sha256 = "0".repeat(64))
        try {
            registry.loadVerified(bad)
            throw AssertionError("A model with a wrong checksum must not load")
        } catch (_: com.vrvision.app.enhance.ModelUnavailableException) {
        }
    }
}
