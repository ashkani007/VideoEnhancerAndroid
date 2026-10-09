package com.vrvision.app.enhance

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import com.vrvision.core.enhance.SrEngine
import org.json.JSONObject
import java.nio.FloatBuffer
import java.security.MessageDigest

/** Metadata of a bundled AI model (assets/models/models.json). */
data class ModelInfo(
    val id: String,
    val file: String,
    val name: String,
    val version: String,
    val sha256: String,
    val scale: Int,
    val denoiseStrength: Float,
    val denoiseLabel: String,
    val license: String,
    val runtime: String,
)

class ModelUnavailableException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Lists and loads bundled models. Every load verifies the SHA-256 recorded at conversion time,
 * so a corrupted or substituted file is reported as unavailable instead of being run.
 */
class ModelRegistry(private val context: Context) {

    val models: List<ModelInfo> by lazy {
        try {
            val json = context.assets.open("models/models.json").bufferedReader().use { it.readText() }
            val arr = JSONObject(json).getJSONArray("models")
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                ModelInfo(
                    id = o.getString("id"), file = o.getString("file"), name = o.getString("name"),
                    version = o.getString("version"), sha256 = o.getString("sha256"), scale = o.getInt("scale"),
                    denoiseStrength = o.getDouble("denoise_strength").toFloat(), denoiseLabel = o.getString("denoise_label"),
                    license = o.getString("license"), runtime = o.getString("runtime"),
                )
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    /** The model for the user's denoise choice (strong denoise variant when enabled). */
    fun forDenoise(denoise: Boolean): ModelInfo? =
        models.firstOrNull { (it.denoiseStrength >= 0.5f) == denoise }

    fun loadVerified(info: ModelInfo): ByteArray {
        val bytes = try {
            context.assets.open("models/${info.file}").use { it.readBytes() }
        } catch (e: Exception) {
            throw ModelUnavailableException("Model file ${info.file} is missing.", e)
        }
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        if (!digest.equals(info.sha256, ignoreCase = true)) {
            throw ModelUnavailableException("Model ${info.file} failed its integrity check and will not be used.")
        }
        return bytes
    }
}

/**
 * Real-ESRGAN compact network executed by ONNX Runtime's default CPU execution provider.
 * GPU/NPU execution providers are not enabled because they have not been benchmarked or
 * validated on target devices.
 */
class OrtSrEngine(modelBytes: ByteArray, override val window: Int = 128, threads: Int = 4) : SrEngine, AutoCloseable {
    override val scale: Int = 4
    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val session: OrtSession
    private val shape = longArrayOf(1, 3, window.toLong(), window.toLong())
    private val output = FloatArray(3 * window * scale * window * scale)

    init {
        val opts = OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(threads)
            setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        }
        session = env.createSession(modelBytes, opts)
    }

    override fun run(input: FloatArray): FloatArray {
        OnnxTensor.createTensor(env, FloatBuffer.wrap(input), shape).use { tensor ->
            session.run(mapOf("input" to tensor)).use { result ->
                val out = result.get(0) as OnnxTensor
                val fb = out.floatBuffer
                check(fb.remaining() == output.size) { "Unexpected model output size ${fb.remaining()}" }
                fb.get(output)
            }
        }
        return output
    }

    override fun close() {
        session.close()
    }
}
