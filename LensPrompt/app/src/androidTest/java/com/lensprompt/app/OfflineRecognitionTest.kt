package com.lensprompt.app

import android.net.Uri
import android.os.ParcelFileDescriptor
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.lensprompt.app.speech.ModelState
import com.lensprompt.app.speech.OfflineModelCache
import com.lensprompt.app.speech.SpeechEvent
import com.lensprompt.app.speech.SpeechModelManager
import com.lensprompt.app.speech.VoskSpeechEngine
import com.lensprompt.core.SmartFollowController
import com.lensprompt.core.TextNormalizer
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Collections

/**
 * Real offline recognition on the emulator: a Vosk model and synthesized
 * speech (espeak-ng, 16 kHz mono PCM16) are pushed by CI to
 * /data/local/tmp/lp/. The test installs the model through the same import
 * path the app uses, streams the PCM in 20 ms chunks (as AudioCaptureEngine
 * does) through VoskSpeechEngine, and feeds the recognized words to the Smart
 * Follow controller. Skipped when the files are not present.
 */
@RunWith(AndroidJUnit4::class)
class OfflineRecognitionTest {

    private val instr = InstrumentationRegistry.getInstrumentation()
    private val app = instr.targetContext.applicationContext as LensPromptApplication

    @Test
    fun englishSpeechIsRecognizedAndFollowed() = run(
        key = "en", tag = "en-US",
        script = "The quick brown fox jumps over the lazy dog. Today we talk about a simple way to record better videos with a teleprompter.",
        strict = true,
    )

    @Test
    fun dutchSpeechRunsThroughTheOfflineEngine() = run(
        key = "nl", tag = "nl-NL",
        script = "Vandaag praten we over een eenvoudige manier om betere video's op te nemen met een teleprompter.",
        strict = false,
    )

    @Test
    fun persianSpeechRunsThroughTheOfflineEngine() = run(
        key = "fa", tag = "fa-IR",
        script = "امروز درباره یک روش ساده برای ضبط ویدیوهای بهتر صحبت می کنیم.",
        strict = false,
    )

    private fun run(key: String, tag: String, script: String, strict: Boolean) = runBlocking {
        val zip = pull("/data/local/tmp/lp/$key.zip")
        val pcm = pull("/data/local/tmp/lp/$key.raw")
        assumeTrue("no model/audio pushed for $key", zip != null && pcm != null)

        // Install through the app's own import path.
        app.models.import(key, Uri.fromFile(zip))
        val state = withTimeout(180_000) {
            app.models.states.first { val s = it[key]; s is ModelState.Installed || s is ModelState.Failed }[key]
        }
        assertTrue("install failed: $state", state is ModelState.Installed)
        val dir = app.models.modelDirFor(tag)!!
        val model = OfflineModelCache.load(dir)

        val engine = VoskSpeechEngine(model, key)
        val events = Collections.synchronizedList(ArrayList<SpeechEvent>())
        val collector = launch(Dispatchers.Default, start = CoroutineStart.UNDISPATCHED) {
            engine.events.collect { events.add(it) }
        }
        assertTrue(engine.start())

        val samples = readPcm(pcm!!)
        val chunk = 320 // 20 ms at 16 kHz
        var i = 0
        while (i < samples.size) {
            val n = minOf(chunk, samples.size - i)
            engine.accept(samples.copyOfRange(i, i + n))
            i += n
            Thread.sleep(20) // real time, like the microphone
        }
        // One second of silence lets Vosk end the utterance.
        repeat(50) { engine.accept(ShortArray(chunk)); Thread.sleep(20) }
        Thread.sleep(1_500)
        engine.stop()
        collector.cancel()

        val partials = events.filterIsInstance<SpeechEvent.Partial>()
        val finals = events.filterIsInstance<SpeechEvent.Final>()
        val recognized = finals.joinToString(" ") { it.text }
        val norm = TextNormalizer(tag)
        val scriptWords = norm.tokenize(script).map { it.text }.toSet()
        val heard = norm.tokenize(recognized).map { it.text }
        val overlap = heard.count { it in scriptWords }.toDouble() / scriptWords.size

        // Smart Follow on the real recognizer output.
        val c = SmartFollowController(script, tag)
        var t = 0L
        c.start(t, 0)
        for (e in events) {
            t += 50
            when (e) {
                is SpeechEvent.Partial -> c.onPartialResult(e.text, t)
                is SpeechEvent.Final -> c.onFinalResult(e.text, t)
                else -> Unit
            }
            c.tick(t)
        }
        val out = c.tick(t + 16)
        Log.i(TAG, "[$key] partials=${partials.size} finals=${finals.size} overlap=${"%.2f".format(overlap)} " +
            "matched=${out.matchedIndex}/${c.scriptTokenCount} text=\"$recognized\"")

        assertTrue("[$key] no partial results", partials.isNotEmpty() || !strict)
        if (strict) {
            assertTrue("[$key] recognized too little of the script ($overlap): $recognized", overlap >= 0.5)
            assertTrue("[$key] Smart Follow did not advance: ${out.matchedIndex}", out.matchedIndex >= c.scriptTokenCount / 2)
        }
        File(app.filesDir, "vosk/$key").deleteRecursively()
        OfflineModelCache.release()
    }

    /** Copies a file pushed by adb (shell-owned) into the app's cache, or null. */
    private fun pull(path: String): File? {
        val out = File(instr.targetContext.cacheDir, File(path).name)
        val pfd = instr.uiAutomation.executeShellCommand("cat $path")
        ParcelFileDescriptor.AutoCloseInputStream(pfd).use { input -> out.outputStream().use { input.copyTo(it) } }
        return out.takeIf { it.length() > 1_000 }
    }

    private fun readPcm(f: File): ShortArray {
        val bytes = FileInputStream(f).use { it.readBytes() }
        val sb = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        return ShortArray(sb.remaining()).also { sb.get(it) }
    }

    private companion object { const val TAG = "LPVoskTest" }
}
