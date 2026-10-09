package com.vrvision.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Navigator
import com.vrvision.app.ui.components.LabeledSlider
import com.vrvision.app.ui.components.ScreenTopBar
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.SwitchRow

@Composable
fun SettingsScreen(c: AppContainer, nav: Navigator) {
    val p by c.settings.state.collectAsState()
    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        ScreenTopBar("Settings and privacy", onBack = nav::back)
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SectionCard("Privacy") {
                Text(
                    "Videos are processed on this phone by default. VRVision has no analytics, ads or accounts. " +
                        "A video is uploaded only after you confirm it on the cloud consent screen for that video.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                SwitchRow(
                    "Local only", p.privacyLocalOnly, { v -> c.settings.update { it.copy(privacyLocalOnly = v) } },
                    help = "Never recommend or offer cloud processing.",
                )
                SwitchRow(
                    "Enable cloud processing", p.cloudEnabled && !p.privacyLocalOnly,
                    { v -> c.settings.update { it.copy(cloudEnabled = v, privacyLocalOnly = if (v) false else it.privacyLocalOnly) } },
                    help = "Uses a VRVision backend that you or someone you trust runs. No server is preconfigured.",
                )
                if (p.cloudEnabled && !p.privacyLocalOnly) {
                    OutlinedTextField(
                        value = p.cloudUrl, onValueChange = { v -> c.settings.update { it.copy(cloudUrl = v) } },
                        label = { Text("Backend URL (https://…)") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                    )
                    var key by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(c.settings.cloudApiKey ?: "") }
                    OutlinedTextField(
                        value = key, onValueChange = { key = it; c.settings.cloudApiKey = it },
                        label = { Text("API key from the server operator") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                    )
                    Text(
                        "Before any upload VRVision may send the server a quote request containing only the video's size, " +
                            "resolution, frame rate and duration.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (p.cloudUrl.isNotBlank() && !p.cloudUrl.startsWith("https://")) {
                        Text("Plain HTTP is only acceptable for a backend on your own local network during development.", color = MaterialTheme.colorScheme.error)
                    }
                    SwitchRow(
                        "Delete cloud copies right after download", p.deleteCloudDataImmediately,
                        { v -> c.settings.update { it.copy(deleteCloudDataImmediately = v) } },
                        help = "Otherwise the server's retention policy applies (default 24 h).",
                    )
                }
            }
            SectionCard("Enhancement defaults") {
                SwitchRow("AI denoising", p.denoise, { v -> c.settings.update { it.copy(denoise = v) } })
                SwitchRow("Sharpening (conventional filter)", p.sharpen, { v -> c.settings.update { it.copy(sharpen = v) } })
                if (p.sharpen) LabeledSlider("Sharpening amount", p.sharpenAmount, 0f..1f, { v -> c.settings.update { it.copy(sharpenAmount = v) } })
                SwitchRow("Prefer HEVC output", p.preferHevc, { v -> c.settings.update { it.copy(preferHevc = v) } }, help = "Falls back to H.264 only with your confirmation.")
            }
            SectionCard("Player") {
                SwitchRow("Start in headset view", p.headsetModeDefault, { v -> c.settings.update { it.copy(headsetModeDefault = v) } })
                SwitchRow("Head tracking", p.useHeadTracking, { v -> c.settings.update { it.copy(useHeadTracking = v) } })
                SwitchRow(
                    "Keep image clear of camera cutout", p.respectCutout, { v -> c.settings.update { it.copy(respectCutout = v) } },
                    help = "Trims both eye views symmetrically so lens centers stay correct.",
                )
            }
            SectionCard("About") {
                Text("VRVision ${com.vrvision.app.BuildConfig.VERSION_NAME}")
                Text(
                    "AI super resolution: Real-ESRGAN general v3 compact model (BSD-3-Clause, © Xintao Wang et al.), " +
                        "run with ONNX Runtime (MIT).",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}
