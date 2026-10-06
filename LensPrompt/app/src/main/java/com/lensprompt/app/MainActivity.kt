package com.lensprompt.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.lensprompt.app.ui.EditorScreen
import com.lensprompt.app.ui.LensColors
import com.lensprompt.app.ui.LensPromptTheme
import com.lensprompt.app.ui.LibraryScreen
import com.lensprompt.app.ui.PrompterScreen
import com.lensprompt.app.ui.SettingsScreen

/** App destinations. Kept deliberately simple: four screens, explicit back stack. */
sealed class Screen {
    data object Library : Screen()
    data object Settings : Screen()
    data class Editor(val scriptId: String) : Screen()
    data class Prompter(val scriptId: String) : Screen()

    fun encode(): String = when (this) {
        Library -> "library"
        Settings -> "settings"
        is Editor -> "editor:$scriptId"
        is Prompter -> "prompter:$scriptId"
    }

    companion object {
        fun decode(s: String): Screen = when {
            s.startsWith("editor:") -> Editor(s.removePrefix("editor:"))
            s.startsWith("prompter:") -> Prompter(s.removePrefix("prompter:"))
            s == "settings" -> Settings
            else -> Library
        }
    }
}

private val backStackSaver = Saver<List<Screen>, String>(
    save = { stack -> stack.joinToString("|") { it.encode() } },
    restore = { s -> s.split("|").filter { it.isNotEmpty() }.map { Screen.decode(it) }.ifEmpty { listOf(Screen.Library) } },
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            LensPromptTheme { AppRoot() }
        }
    }
}

@Composable
private fun AppRoot() {
    var stack by rememberSaveable(stateSaver = backStackSaver) { mutableStateOf(listOf<Screen>(Screen.Library)) }
    val current = stack.last()
    fun push(s: Screen) { stack = stack + s }
    fun pop() { if (stack.size > 1) stack = stack.dropLast(1) }
    fun replace(s: Screen) { stack = stack.dropLast(1) + s }

    BackHandler(enabled = stack.size > 1) { pop() }

    Box(Modifier.fillMaxSize().background(LensColors.Background)) {
        when (current) {
            Screen.Library -> LibraryScreen(
                onOpen = { push(Screen.Prompter(it)) },
                onEdit = { push(Screen.Editor(it)) },
                onSettings = { push(Screen.Settings) },
            )
            Screen.Settings -> SettingsScreen(onBack = ::pop)
            is Screen.Editor -> EditorScreen(
                scriptId = current.scriptId,
                onBack = ::pop,
                onPrompt = { replace(Screen.Prompter(current.scriptId)) },
            )
            is Screen.Prompter -> PrompterScreen(
                scriptId = current.scriptId,
                onBack = ::pop,
                onEdit = { replace(Screen.Editor(current.scriptId)) },
                onSettings = { push(Screen.Settings) },
            )
        }
    }
}
