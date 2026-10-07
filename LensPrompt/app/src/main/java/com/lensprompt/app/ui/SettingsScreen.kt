package com.lensprompt.app.ui

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.data.PromptAlign
import com.lensprompt.app.data.SettingsRepository
import com.lensprompt.app.data.SpeechEngineChoice
import com.lensprompt.app.speech.ModelState
import com.lensprompt.app.speech.SpeechModelManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.TextButton
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.lensprompt.app.overlay.OverlayService

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val app = context.applicationContext as LensPromptApplication
    val s by app.settings.settings.collectAsState()
    val update = app.settings::update

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } },
                title = { Text("Settings") },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
        ) {
            Section("Smart Follow")
            LabeledSlider(
                "Responsiveness", s.responsiveness, 0f..1f, "%.2f",
                hint = "Higher reacts faster to speed changes; lower is calmer.",
            ) { v -> update { it.copy(responsiveness = v) } }
            LabeledSlider(
                "Pause sensitivity", s.pauseSensitivity, 0f..1f, "%.2f",
                hint = "Higher stops the text sooner when you stop speaking.",
            ) { v -> update { it.copy(pauseSensitivity = v) } }
            LabeledSlider(
                "Alignment strictness", s.alignmentStrictness, 0f..1f, "%.2f",
                hint = "Higher needs clearer speech before moving; lower tolerates accents and errors.",
            ) { v -> update { it.copy(alignmentStrictness = v) } }
            Text("Recognition language", modifier = Modifier.padding(top = 8.dp))
            SettingsRepository.LANGUAGES.forEach { (tag, label) ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = s.languageTag == tag, onClick = { update { it.copy(languageTag = tag) } })
                    Text(label)
                }
            }
            LabeledSwitch(
                "Lip tracking", s.lipTracking,
                hint = "Uses the front camera to see when you are talking (on-device, nothing is stored). " +
                    "Helps Smart Follow while recording and in noisy rooms.",
            ) { v -> update { it.copy(lipTracking = v) } }
            OfflineSpeechSection(app, s.languageTag, s.speechEngine) { v -> update { it.copy(speechEngine = v) } }
            LabeledSwitch(
                "Prefer on-device recognition", s.preferOffline,
                hint = "Keeps speech on the phone where the device supports it. Falls back to the online service if the language isn't installed.",
            ) { v -> update { it.copy(preferOffline = v) } }

            Section("Display")
            LabeledSlider("Font size", s.fontSizeSp, 18f..72f, "%.0f sp") { v -> update { it.copy(fontSizeSp = v) } }
            LabeledSlider("Line spacing", s.lineSpacing, 1.0f..2.2f, "%.2f×") { v -> update { it.copy(lineSpacing = v) } }
            LabeledSlider("Margins", s.marginFraction, 0f..0.25f, "%.2f") { v -> update { it.copy(marginFraction = v) } }
            LabeledSlider(
                "Reading anchor", s.anchorFraction, 0.2f..0.7f, "%.2f",
                hint = "Where the line you are reading sits, from the top of the screen.",
            ) { v -> update { it.copy(anchorFraction = v) } }
            LabeledSwitch("Center text", s.align == PromptAlign.CENTER) { v ->
                update { it.copy(align = if (v) PromptAlign.CENTER else PromptAlign.START) }
            }
            LabeledSwitch("Mirror horizontally", s.mirrorHorizontal, hint = "For beam-splitter teleprompter glass.") { v -> update { it.copy(mirrorHorizontal = v) } }
            LabeledSwitch("Mirror vertically", s.mirrorVertical) { v -> update { it.copy(mirrorVertical = v) } }
            LabeledSlider("Manual scroll speed", s.manualSpeed, 1f..10f, "%.1f") { v -> update { it.copy(manualSpeed = v) } }

            Section("Countdown")
            Row {
                listOf(0, 3, 5, 10).forEach { sec ->
                    FilterChip(
                        selected = s.countdownSeconds == sec,
                        onClick = { update { it.copy(countdownSeconds = sec) } },
                        label = { Text(if (sec == 0) "Off" else "$sec s") },
                        modifier = Modifier.padding(end = 8.dp),
                    )
                }
            }

            Section("Camera")
            LabeledSwitch("Camera preview behind text", s.showCamera) { v -> update { it.copy(showCamera = v) } }
            LabeledSlider("Background dim", s.backgroundDim, 0f..1f, "%.2f") { v -> update { it.copy(backgroundDim = v) } }
            LabeledSwitch(
                "Record audio with video", s.recordAudio,
                hint = "LensPrompt records the sound itself, so Smart Follow keeps listening while you film.",
            ) { v -> update { it.copy(recordAudio = v) } }

            Section("Floating teleprompter")
            FloatingModeBanner(Modifier.padding(vertical = 4.dp))
            Text(
                "Shows a movable, resizable, transparent teleprompter above other apps such as Samsung Camera. " +
                    "Start it for a script with \"Use with phone camera\" (script menu or prompter top bar). " +
                    "It follows your voice while the microphone is free and scrolls at the manual speed while " +
                    "the camera app records sound.",
                color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
            )
            LabeledSlider("Overlay opacity", s.overlayOpacity, 0.2f..1f, "%.2f") { v -> update { it.copy(overlayOpacity = v) } }
            Row {
                var showFloating by remember { mutableStateOf(false) }
                Button(onClick = { showFloating = true }) { Text("Start floating teleprompter") }
                if (showFloating) FloatingPrompterDialog(null) { showFloating = false }
                Spacer(Modifier.padding(4.dp))
                OutlinedButton(onClick = { OverlayService.stop(context) }) { Text("Stop") }
            }

            Section("Troubleshooting")
            LabeledSwitch(
                "Diagnostics overlay", s.debugMode,
                hint = "Shows Smart Follow and microphone details on the prompter, with a button to copy them for support.",
            ) { v -> update { it.copy(debugMode = v) } }
            OutlinedButton(onClick = { update { it.copy(firstRunDone = false) } }) { Text("Show quick start again") }
            val verdicts = remember { mutableStateOf(app.recognizerVerdicts.all()) }
            if (verdicts.value.isNotEmpty()) {
                Text(
                    "Recognizers found unable to use LensPrompt's audio while recording:\n" +
                        verdicts.value.entries.joinToString("\n") { "• ${it.key.removePrefix("ext:")}: ${it.value}" },
                    color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
                )
                OutlinedButton(onClick = { app.recognizerVerdicts.clear(); verdicts.value = emptyMap() }) { Text("Forget and test again") }
            }

            Section("Privacy")
            Text(
                "LensPrompt listens only while Smart Follow is running (a green microphone is shown). " +
                    "It never uploads audio itself. With an offline speech pack, speech is turned into text on this phone " +
                    "by LensPrompt. Otherwise your device's speech recognition service does it, which may process it online " +
                    "unless on-device recognition is available and preferred. Sound is stored only in videos you record.",
                color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun Section(title: String) {
    Spacer(Modifier.height(16.dp))
    HorizontalDivider(color = LensColors.SurfaceHigh)
    Spacer(Modifier.height(12.dp))
    Text(title, color = LensColors.Accent, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleSmall)
    Spacer(Modifier.height(4.dp))
}

/**
 * Offline speech packs: what lets Smart Follow keep recognizing words while
 * recording video with sound (LensPrompt's own microphone feeds the recognizer).
 */
@Composable
private fun OfflineSpeechSection(
    app: LensPromptApplication,
    languageTag: String,
    engine: SpeechEngineChoice,
    onEngine: (SpeechEngineChoice) -> Unit,
) {
    val states by app.models.states.collectAsState()
    var importKey by remember { mutableStateOf<String?>(null) }
    val importer = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val key = importKey
        if (uri != null && key != null) app.models.import(key, uri)
    }
    Section("Offline speech")
    Text(
        "Offline speech packs run recognition inside LensPrompt on the same microphone stream that records your " +
            "video, so Smart Follow keeps following your words while you film with sound. Each pack is a one-time " +
            "download from the Vosk project (alphacephei.com); nothing is uploaded.",
        color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
    )
    val current = SpeechModelManager.keyFor(languageTag)
    SpeechModelManager.SPECS.forEach { spec ->
        val st = states[spec.key] ?: ModelState.NotInstalled
        Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    spec.label + if (spec.key == current) "  (recognition language)" else "",
                    fontWeight = if (spec.key == current) FontWeight.SemiBold else FontWeight.Normal,
                    modifier = Modifier.weight(1f),
                )
                when (st) {
                    is ModelState.Installed -> TextButton(onClick = { app.models.delete(spec.key) }) { Text("Delete") }
                    is ModelState.Downloading, ModelState.Installing ->
                        TextButton(onClick = { app.models.cancel(spec.key) }) { Text("Cancel") }
                    else -> {
                        TextButton(onClick = { app.models.download(spec.key) }) { Text("Download ~${spec.approxMb} MB") }
                        TextButton(onClick = { importKey = spec.key; importer.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) }) {
                            Text("Import")
                        }
                    }
                }
            }
            when (st) {
                is ModelState.Installed -> Text("Installed: ${st.name} (${st.sizeMb} MB)", color = LensColors.Accent, style = MaterialTheme.typography.bodySmall)
                is ModelState.Downloading -> {
                    val frac = if (st.total > 0) (st.bytes.toFloat() / st.total).coerceIn(0f, 1f) else 0f
                    LinearProgressIndicator(progress = { frac }, modifier = Modifier.fillMaxWidth().padding(top = 4.dp))
                    Text("Downloading ${st.name}: ${st.bytes / 1_000_000} MB", color = LensColors.Muted, style = MaterialTheme.typography.bodySmall)
                }
                ModelState.Installing -> Text("Installing…", color = LensColors.Muted, style = MaterialTheme.typography.bodySmall)
                is ModelState.Failed -> Text(st.message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                ModelState.NotInstalled -> Unit
            }
        }
    }
    Text("Speech engine", modifier = Modifier.padding(top = 8.dp))
    listOf(
        SpeechEngineChoice.AUTO to "Automatic: system recognizer, offline pack while recording with sound",
        SpeechEngineChoice.OFFLINE to "Offline pack whenever installed",
        SpeechEngineChoice.SYSTEM to "System recognizer only",
    ).forEach { (choice, label) ->
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = engine == choice, onClick = { onEngine(choice) })
            Text(label, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
