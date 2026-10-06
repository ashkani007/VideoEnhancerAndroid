package com.lensprompt.app

import android.app.Application
import com.lensprompt.app.data.ScriptRepository
import com.lensprompt.app.data.SettingsRepository

/** Holds the app-wide singletons (a tiny manual DI container). */
class LensPromptApplication : Application() {
    val scripts: ScriptRepository by lazy { ScriptRepository(this) }
    val settings: SettingsRepository by lazy { SettingsRepository(this) }
}
