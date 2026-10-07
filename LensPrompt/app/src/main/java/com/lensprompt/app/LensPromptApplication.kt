package com.lensprompt.app

import android.app.Application
import com.lensprompt.app.data.ScriptRepository
import com.lensprompt.app.data.SettingsRepository
import com.lensprompt.app.speech.RecognizerVerdicts
import com.lensprompt.app.speech.SpeechModelManager

/** Holds the app-wide singletons (a tiny manual DI container). */
class LensPromptApplication : Application() {
    val scripts: ScriptRepository by lazy { ScriptRepository(this) }
    val settings: SettingsRepository by lazy { SettingsRepository(this) }
    val models: SpeechModelManager by lazy { SpeechModelManager(this) }
    /** Per-recognition-service verdicts ("does it honour EXTRA_AUDIO_SOURCE?"). */
    val recognizerVerdicts: RecognizerVerdicts by lazy { RecognizerVerdicts(this) }
}
