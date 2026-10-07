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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.R
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
fun SettingsScreen(onBack: () -> Unit, onPro: () -> Unit = {}, onAbout: () -> Unit = {}) {
    val context = LocalContext.current
    val app = context.applicationContext as LensPromptApplication
    val s by app.settings.settings.collectAsState()
    val update = app.settings::update

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.common_back)) } },
                title = { Text(stringResource(R.string.common_settings)) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
        ) {
            OutlinedButton(onClick = onPro, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.pro_title)) }
            Section("Smart Follow")
            LabeledSlider(
                stringResource(R.string.settings_responsiveness), s.responsiveness, 0f..1f, "%.2f",
                hint = stringResource(R.string.settings_responsiveness_hint),
            ) { v -> update { it.copy(responsiveness = v) } }
            LabeledSlider(
                stringResource(R.string.settings_pause_sensitivity), s.pauseSensitivity, 0f..1f, "%.2f",
                hint = stringResource(R.string.settings_pause_sensitivity_hint),
            ) { v -> update { it.copy(pauseSensitivity = v) } }
            LabeledSlider(
                stringResource(R.string.settings_alignment_strictness), s.alignmentStrictness, 0f..1f, "%.2f",
                hint = stringResource(R.string.settings_alignment_strictness_hint),
            ) { v -> update { it.copy(alignmentStrictness = v) } }
            Text(stringResource(R.string.settings_recognition_language), modifier = Modifier.padding(top = 8.dp))
            SettingsRepository.LANGUAGES.forEach { (tag, label) ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = s.languageTag == tag, onClick = { update { it.copy(languageTag = tag) } })
                    Text(label)
                }
            }
            LabeledSwitch(
                stringResource(R.string.settings_lip_tracking), s.lipTracking,
                hint = stringResource(R.string.settings_lip_tracking_hint),
            ) { v -> update { it.copy(lipTracking = v) } }
            OfflineSpeechSection(app, s.languageTag, s.speechEngine) { v -> update { it.copy(speechEngine = v) } }
            LabeledSwitch(
                stringResource(R.string.settings_prefer_offline), s.preferOffline,
                hint = stringResource(R.string.settings_prefer_offline_hint),
            ) { v -> update { it.copy(preferOffline = v) } }

            Section(stringResource(R.string.settings_section_display))
            LabeledSlider(stringResource(R.string.settings_font_size), s.fontSizeSp, 18f..72f, "%.0f sp") { v -> update { it.copy(fontSizeSp = v) } }
            LabeledSlider(stringResource(R.string.settings_line_spacing), s.lineSpacing, 1.0f..2.2f, "%.2f×") { v -> update { it.copy(lineSpacing = v) } }
            LabeledSlider(stringResource(R.string.settings_margins), s.marginFraction, 0f..0.25f, "%.2f") { v -> update { it.copy(marginFraction = v) } }
            LabeledSlider(
                stringResource(R.string.settings_reading_anchor), s.anchorFraction, 0.2f..0.7f, "%.2f",
                hint = stringResource(R.string.settings_reading_anchor_hint),
            ) { v -> update { it.copy(anchorFraction = v) } }
            LabeledSwitch(stringResource(R.string.settings_center_text), s.align == PromptAlign.CENTER) { v ->
                update { it.copy(align = if (v) PromptAlign.CENTER else PromptAlign.START) }
            }
            LabeledSwitch(stringResource(R.string.settings_mirror_horizontal), s.mirrorHorizontal, hint = stringResource(R.string.settings_mirror_horizontal_hint)) { v -> update { it.copy(mirrorHorizontal = v) } }
            LabeledSwitch(stringResource(R.string.settings_mirror_vertical), s.mirrorVertical) { v -> update { it.copy(mirrorVertical = v) } }
            LabeledSlider(stringResource(R.string.settings_manual_scroll_speed), s.manualSpeed, 1f..10f, "%.1f") { v -> update { it.copy(manualSpeed = v) } }

            Section(stringResource(R.string.settings_section_countdown))
            Row {
                listOf(0, 3, 5, 10).forEach { sec ->
                    FilterChip(
                        selected = s.countdownSeconds == sec,
                        onClick = { update { it.copy(countdownSeconds = sec) } },
                        label = { Text(if (sec == 0) stringResource(R.string.settings_countdown_off) else stringResource(R.string.settings_countdown_seconds, sec)) },
                        modifier = Modifier.padding(end = 8.dp),
                    )
                }
            }

            Section(stringResource(R.string.settings_section_camera))
            LabeledSwitch(stringResource(R.string.settings_camera_preview_behind_text), s.showCamera) { v -> update { it.copy(showCamera = v) } }
            LabeledSlider(stringResource(R.string.settings_background_dim), s.backgroundDim, 0f..1f, "%.2f") { v -> update { it.copy(backgroundDim = v) } }
            LabeledSwitch(
                stringResource(R.string.settings_record_audio), s.recordAudio,
                hint = stringResource(R.string.settings_record_audio_hint),
            ) { v -> update { it.copy(recordAudio = v) } }

            Section(stringResource(R.string.settings_section_floating))
            FloatingModeBanner(Modifier.padding(vertical = 4.dp))
            Text(
                stringResource(R.string.settings_floating_description),
                color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
            )
            LabeledSlider(stringResource(R.string.settings_overlay_opacity), s.overlayOpacity, 0.2f..1f, "%.2f") { v -> update { it.copy(overlayOpacity = v) } }
            Row {
                var showFloating by remember { mutableStateOf(false) }
                Button(onClick = { showFloating = true }) { Text(stringResource(R.string.settings_start_floating)) }
                if (showFloating) FloatingPrompterDialog(null) { showFloating = false }
                Spacer(Modifier.padding(4.dp))
                OutlinedButton(onClick = { OverlayService.stop(context) }) { Text(stringResource(R.string.common_stop)) }
            }

            Section(stringResource(R.string.settings_section_troubleshooting))
            LabeledSwitch(
                stringResource(R.string.settings_diagnostics_overlay), s.debugMode,
                hint = stringResource(R.string.settings_diagnostics_overlay_hint),
            ) { v -> update { it.copy(debugMode = v) } }
            OutlinedButton(onClick = { update { it.copy(firstRunDone = false) } }) { Text(stringResource(R.string.settings_show_quick_start)) }
            val verdicts = remember { mutableStateOf(app.recognizerVerdicts.all()) }
            if (verdicts.value.isNotEmpty()) {
                Text(
                    stringResource(R.string.settings_recognizers_unable) + "\n" +
                        verdicts.value.entries.joinToString("\n") { "• ${it.key.removePrefix("ext:")}: ${it.value}" },
                    color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
                )
                OutlinedButton(onClick = { app.recognizerVerdicts.clear(); verdicts.value = emptyMap() }) { Text(stringResource(R.string.settings_forget_and_retest)) }
            }

            Section(stringResource(R.string.settings_section_about))
            OutlinedButton(onClick = onAbout) { Text(stringResource(R.string.settings_about_button)) }
            Section(stringResource(R.string.settings_section_privacy))
            Text(
                stringResource(R.string.settings_privacy_text),
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
    Section(stringResource(R.string.settings_section_offline_speech))
    Text(
        stringResource(R.string.settings_offline_speech_description),
        color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
    )
    val current = SpeechModelManager.keyFor(languageTag)
    SpeechModelManager.SPECS.forEach { spec ->
        val st = states[spec.key] ?: ModelState.NotInstalled
        Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    spec.label + if (spec.key == current) "  " + stringResource(R.string.settings_recognition_language_marker) else "",
                    fontWeight = if (spec.key == current) FontWeight.SemiBold else FontWeight.Normal,
                    modifier = Modifier.weight(1f),
                )
                when (st) {
                    is ModelState.Installed -> TextButton(onClick = { app.models.delete(spec.key) }) { Text(stringResource(R.string.common_delete)) }
                    is ModelState.Downloading, ModelState.Installing ->
                        TextButton(onClick = { app.models.cancel(spec.key) }) { Text(stringResource(R.string.common_cancel)) }
                    else -> {
                        TextButton(onClick = { app.models.download(spec.key) }) { Text(stringResource(R.string.settings_model_download, spec.approxMb)) }
                        TextButton(onClick = { importKey = spec.key; importer.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) }) {
                            Text(stringResource(R.string.settings_model_import))
                        }
                    }
                }
            }
            when (st) {
                is ModelState.Installed -> Text(stringResource(R.string.settings_model_installed, st.name, st.sizeMb), color = LensColors.Accent, style = MaterialTheme.typography.bodySmall)
                is ModelState.Downloading -> {
                    val frac = if (st.total > 0) (st.bytes.toFloat() / st.total).coerceIn(0f, 1f) else 0f
                    LinearProgressIndicator(progress = { frac }, modifier = Modifier.fillMaxWidth().padding(top = 4.dp))
                    Text(stringResource(R.string.settings_model_downloading, st.name, st.bytes / 1_000_000), color = LensColors.Muted, style = MaterialTheme.typography.bodySmall)
                }
                ModelState.Installing -> Text(stringResource(R.string.settings_model_installing), color = LensColors.Muted, style = MaterialTheme.typography.bodySmall)
                is ModelState.Failed -> Text(st.message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                ModelState.NotInstalled -> Unit
            }
        }
    }
    Text(stringResource(R.string.settings_speech_engine), modifier = Modifier.padding(top = 8.dp))
    listOf(
        SpeechEngineChoice.AUTO to stringResource(R.string.settings_engine_auto),
        SpeechEngineChoice.OFFLINE to stringResource(R.string.settings_engine_offline),
        SpeechEngineChoice.SYSTEM to stringResource(R.string.settings_engine_system),
    ).forEach { (choice, label) ->
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = engine == choice, onClick = { onEngine(choice) })
            Text(label, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
