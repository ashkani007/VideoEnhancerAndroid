package com.lensprompt.app

import android.app.Application
import com.lensprompt.app.billing.DisabledProRepository
import com.lensprompt.app.billing.PlayBillingRepository
import com.lensprompt.app.billing.ProRepository
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
    /** LensPrompt Pro. Google Play Billing only when explicitly enabled for the build. */
    val pro: ProRepository by lazy {
        if (BuildConfig.BILLING_ENABLED) PlayBillingRepository(this) else DisabledProRepository()
    }
}
