package com.vrvision.app.enhance

import org.json.JSONObject

/** Everything a job needs, stored with the job so it can resume after process death. */
data class EnhanceSettings(
    val outWidth: Int,
    val outHeight: Int,
    val scale: Double,
    val outputMime: String,
    val bitrate: Int,
    val denoise: Boolean,
    val sharpen: Boolean,
    val sharpenAmount: Float,
    val layout: String,
    val projection: String,
    /** Set only for cloud jobs, when the user ticked the consent box. */
    val consentGrantedAtMs: Long? = null,
    val consentTextVersion: String? = null,
) {
    fun toJson(): String = JSONObject().apply {
        put("outWidth", outWidth); put("outHeight", outHeight); put("scale", scale)
        put("outputMime", outputMime); put("bitrate", bitrate); put("denoise", denoise)
        put("sharpen", sharpen); put("sharpenAmount", sharpenAmount.toDouble())
        put("layout", layout); put("projection", projection)
        consentGrantedAtMs?.let { put("consentGrantedAtMs", it) }
        consentTextVersion?.let { put("consentTextVersion", it) }
    }.toString()

    companion object {
        fun fromJson(s: String): EnhanceSettings {
            val o = JSONObject(s)
            return EnhanceSettings(
                outWidth = o.getInt("outWidth"), outHeight = o.getInt("outHeight"), scale = o.getDouble("scale"),
                outputMime = o.getString("outputMime"), bitrate = o.getInt("bitrate"), denoise = o.getBoolean("denoise"),
                sharpen = o.getBoolean("sharpen"), sharpenAmount = o.getDouble("sharpenAmount").toFloat(),
                layout = o.getString("layout"), projection = o.getString("projection"),
                consentGrantedAtMs = if (o.has("consentGrantedAtMs")) o.getLong("consentGrantedAtMs") else null,
                consentTextVersion = if (o.has("consentTextVersion")) o.getString("consentTextVersion") else null,
            )
        }
    }
}

object JobModes {
    const val LOCAL_AI = "LOCAL_AI"
    const val LOCAL_CONVENTIONAL = "LOCAL_CONVENTIONAL"
    const val CLOUD = "CLOUD"
}

object JobStatus {
    const val QUEUED = "QUEUED"
    const val RUNNING = "RUNNING"
    const val SUCCEEDED = "SUCCEEDED"
    const val FAILED = "FAILED"
    const val CANCELLED = "CANCELLED"
    const val UNSUPPORTED = "UNSUPPORTED"
    const val REJECTED = "REJECTED"
    val terminal = setOf(SUCCEEDED, FAILED, CANCELLED, UNSUPPORTED, REJECTED)
}
