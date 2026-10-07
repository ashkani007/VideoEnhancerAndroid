package com.lensprompt.app.data

import android.content.Context
import android.content.SharedPreferences
import com.lensprompt.core.SmartFollowConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class PromptAlign { START, CENTER }

/**
 * Which speech recognizer Smart Follow uses.
 *  AUTO: the system recognizer normally; the offline pack (LensPrompt's own mic)
 *        while recording video with sound, when the pack is installed.
 *  OFFLINE: always the offline pack when installed (fully on-device, no restarts).
 *  SYSTEM: always the system recognizer.
 */
enum class SpeechEngineChoice { AUTO, OFFLINE, SYSTEM }

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
    val speechEngine: SpeechEngineChoice = SpeechEngineChoice.AUTO,
    // camera
    val showCamera: Boolean = true,
    val recordAudio: Boolean = true,
    /** Use front-camera lip movement as a talking signal for Smart Follow. */
    val lipTracking: Boolean = true,
    // misc
    val overlayOpacity: Float = 0.75f,
    val overlayFontSp: Float = 28f,
    /** Floating window position and size in px (−1 = default). */
    val overlayX: Int = -1,
    val overlayY: Int = -1,
    val overlayW: Int = -1,
    val overlayH: Int = -1,
    val overlaySmartFollow: Boolean = true,
    val overlayLineSpacing: Float = 1.25f,
    /** Text opacity in the floating window (background opacity is [overlayOpacity]). */
    val overlayTextOpacity: Float = 1f,
    val overlayAlignCenter: Boolean = false,
    val overlayMirror: Boolean = false,
    val overlayLocked: Boolean = false,
    val overlayAutoHide: Boolean = true,
    /** Screen size the overlay position was saved for (to adapt after rotation). */
    val overlayScreenW: Int = -1,
    val overlayScreenH: Int = -1,
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
            speechEngine = runCatching { SpeechEngineChoice.valueOf(prefs.getString("speechEngine", d.speechEngine.name)!!) }
                .getOrDefault(d.speechEngine),
            showCamera = prefs.getBoolean("showCamera", d.showCamera),
            recordAudio = prefs.getBoolean("recordAudio", d.recordAudio),
            lipTracking = prefs.getBoolean("lipTracking", d.lipTracking),
            overlayOpacity = prefs.getFloat("overlayOpacity", d.overlayOpacity),
            overlayFontSp = prefs.getFloat("overlayFontSp", d.overlayFontSp),
            overlayX = prefs.getInt("overlayX", d.overlayX),
            overlayY = prefs.getInt("overlayY", d.overlayY),
            overlayW = prefs.getInt("overlayW", d.overlayW),
            overlayH = prefs.getInt("overlayH", d.overlayH),
            overlaySmartFollow = prefs.getBoolean("overlaySmartFollow", d.overlaySmartFollow),
            overlayLineSpacing = prefs.getFloat("overlayLineSpacing", d.overlayLineSpacing),
            overlayTextOpacity = prefs.getFloat("overlayTextOpacity", d.overlayTextOpacity),
            overlayAlignCenter = prefs.getBoolean("overlayAlignCenter", d.overlayAlignCenter),
            overlayMirror = prefs.getBoolean("overlayMirror", d.overlayMirror),
            overlayLocked = prefs.getBoolean("overlayLocked", d.overlayLocked),
            overlayAutoHide = prefs.getBoolean("overlayAutoHide", d.overlayAutoHide),
            overlayScreenW = prefs.getInt("overlayScreenW", d.overlayScreenW),
            overlayScreenH = prefs.getInt("overlayScreenH", d.overlayScreenH),
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
            .putString("speechEngine", s.speechEngine.name)
            .putBoolean("showCamera", s.showCamera)
            .putBoolean("recordAudio", s.recordAudio)
            .putBoolean("lipTracking", s.lipTracking)
            .putFloat("overlayOpacity", s.overlayOpacity)
            .putFloat("overlayFontSp", s.overlayFontSp)
            .putInt("overlayX", s.overlayX)
            .putInt("overlayY", s.overlayY)
            .putInt("overlayW", s.overlayW)
            .putInt("overlayH", s.overlayH)
            .putBoolean("overlaySmartFollow", s.overlaySmartFollow)
            .putFloat("overlayLineSpacing", s.overlayLineSpacing)
            .putFloat("overlayTextOpacity", s.overlayTextOpacity)
            .putBoolean("overlayAlignCenter", s.overlayAlignCenter)
            .putBoolean("overlayMirror", s.overlayMirror)
            .putBoolean("overlayLocked", s.overlayLocked)
            .putBoolean("overlayAutoHide", s.overlayAutoHide)
            .putInt("overlayScreenW", s.overlayScreenW)
            .putInt("overlayScreenH", s.overlayScreenH)
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
