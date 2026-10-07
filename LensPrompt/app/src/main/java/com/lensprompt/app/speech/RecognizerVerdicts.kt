package com.lensprompt.app.speech

import android.content.Context
import android.os.Build

/**
 * Remembers, per recognition service and Android version, that the service
 * ignores LensPrompt's audio stream (EXTRA_AUDIO_SOURCE). Such a service is not
 * tried again while recording: Smart Follow goes straight to the offline pack
 * or to pacing instead of restarting a recognizer that can never hear anything.
 */
class RecognizerVerdicts(context: Context) {
    private val prefs = context.getSharedPreferences("lensprompt_recognizer_verdicts", Context.MODE_PRIVATE)

    private fun key(component: String) = "ext:$component:${Build.VERSION.SDK_INT}"

    fun externalAudioBroken(component: String): String? = prefs.getString(key(component), null)

    fun markExternalAudioBroken(component: String, reason: String) {
        prefs.edit().putString(key(component), reason).apply()
    }

    fun all(): Map<String, String> = prefs.all.mapValues { it.value.toString() }

    fun clear() = prefs.edit().clear().apply()
}
