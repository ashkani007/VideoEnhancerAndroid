package com.lensprompt.app.data

import android.content.Context
import android.content.SharedPreferences
import com.lensprompt.core.SmartFollowConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class PromptAlign { START, CENTER }

data class AppSettings(
    // display
    val fontSizeSp: Float = 34f,
    val lineSpacing: Float = 1.35f,
    /** Horizontal margin on each side, as a fraction of the screen width. */
    val marginFraction: Float = 0.06f,
    val align: PromptAlign = PromptAlign.START,
    /** Reading anchor position from the top of the prompter area (0..1). */
    val anchorFraction: Float = 0.42f,
    val mirrorHorizontal: Boolean = false,
    val mirrorVertical: Boolean = false,
    /** Darkening over the camera preview behind the text (0..1). */
    val backgroundDim: Float = 0.6f,
    // behaviour
    val countdownSeconds: Int = 3,
    /** Manual auto-scroll speed, 1..10. */
    val manualSpeed: Float = 4f,
    val smartFollow: Boolean = true,
    // smart follow
    val responsiveness: Float = 0.5f,
    val pauseSensitivity: Float = 0.5f,
    val alignmentStrictness: Float = 0.5f,
    /** BCP-47 tag for recognition; empty = device language. */
    val languageTag: String = "",
    val preferOffline: Boolean = false,
    // camera
    val showCamera: Boolean = true,
    val recordAudio: Boolean = true,
    // misc
    val overlayOpacity: Float = 0.75f,
    val debugMode: Boolean = false,
    val firstRunDone: Boolean = false,
) {
    fun smartFollowConfig(): SmartFollowConfig =
        SmartFollowConfig.fromUserSettings(responsiveness, pauseSensitivity, alignmentStrictness)

    /** Manual speed in dp/s. */
    val manualSpeedDp: Float get() = 8f + manualSpeed * 9f
}

/** Settings persisted in SharedPreferences and exposed as a StateFlow. */
class SettingsRepository(context: Context) {

    private val prefs: SharedPreferences = context.getSharedPreferences("lensprompt_settings", Context.MODE_PRIVATE)
    private val _settings = MutableStateFlow(read())
    val settings: StateFlow<AppSettings> = _settings.asStateFlow()

    fun update(transform: (AppSettings) -> AppSettings) {
        val next = transform(_settings.value)
        if (next == _settings.value) return
        _settings.value = next
        write(next)
    }

    private fun read(): AppSettings {
        val d = AppSettings()
        return AppSettings(
            fontSizeSp = prefs.getFloat("fontSizeSp", d.fontSizeSp),
            lineSpacing = prefs.getFloat("lineSpacing", d.lineSpacing),
            marginFraction = prefs.getFloat("marginFraction", d.marginFraction),
            align = runCatching { PromptAlign.valueOf(prefs.getString("align", d.align.name)!!) }.getOrDefault(d.align),
            anchorFraction = prefs.getFloat("anchorFraction", d.anchorFraction),
            mirrorHorizontal = prefs.getBoolean("mirrorHorizontal", d.mirrorHorizontal),
            mirrorVertical = prefs.getBoolean("mirrorVertical", d.mirrorVertical),
            backgroundDim = prefs.getFloat("backgroundDim", d.backgroundDim),
            countdownSeconds = prefs.getInt("countdownSeconds", d.countdownSeconds),
            manualSpeed = prefs.getFloat("manualSpeed", d.manualSpeed),
            smartFollow = prefs.getBoolean("smartFollow", d.smartFollow),
            responsiveness = prefs.getFloat("responsiveness", d.responsiveness),
            pauseSensitivity = prefs.getFloat("pauseSensitivity", d.pauseSensitivity),
            alignmentStrictness = prefs.getFloat("alignmentStrictness", d.alignmentStrictness),
            languageTag = prefs.getString("languageTag", d.languageTag) ?: "",
            preferOffline = prefs.getBoolean("preferOffline", d.preferOffline),
            showCamera = prefs.getBoolean("showCamera", d.showCamera),
            recordAudio = prefs.getBoolean("recordAudio", d.recordAudio),
            overlayOpacity = prefs.getFloat("overlayOpacity", d.overlayOpacity),
            debugMode = prefs.getBoolean("debugMode", d.debugMode),
            firstRunDone = prefs.getBoolean("firstRunDone", d.firstRunDone),
        )
    }

    private fun write(s: AppSettings) {
        prefs.edit()
            .putFloat("fontSizeSp", s.fontSizeSp)
            .putFloat("lineSpacing", s.lineSpacing)
            .putFloat("marginFraction", s.marginFraction)
            .putString("align", s.align.name)
            .putFloat("anchorFraction", s.anchorFraction)
            .putBoolean("mirrorHorizontal", s.mirrorHorizontal)
            .putBoolean("mirrorVertical", s.mirrorVertical)
            .putFloat("backgroundDim", s.backgroundDim)
            .putInt("countdownSeconds", s.countdownSeconds)
            .putFloat("manualSpeed", s.manualSpeed)
            .putBoolean("smartFollow", s.smartFollow)
            .putFloat("responsiveness", s.responsiveness)
            .putFloat("pauseSensitivity", s.pauseSensitivity)
            .putFloat("alignmentStrictness", s.alignmentStrictness)
            .putString("languageTag", s.languageTag)
            .putBoolean("preferOffline", s.preferOffline)
            .putBoolean("showCamera", s.showCamera)
            .putBoolean("recordAudio", s.recordAudio)
            .putFloat("overlayOpacity", s.overlayOpacity)
            .putBoolean("debugMode", s.debugMode)
            .putBoolean("firstRunDone", s.firstRunDone)
            .apply()
    }

    companion object {
        /** Recognition languages offered in settings (tag to label). */
        val LANGUAGES = listOf(
            "" to "Device language",
            "en-US" to "English (US)",
            "en-GB" to "English (UK)",
            "fa-IR" to "فارسی (Persian)",
            "nl-NL" to "Nederlands (Dutch)",
            "de-DE" to "Deutsch",
            "fr-FR" to "Français",
            "es-ES" to "Español",
        )
    }
}
