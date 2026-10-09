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
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.ui.components.ChoiceChips
import com.vrvision.app.ui.components.InfoRow
import com.vrvision.app.ui.components.LabeledSlider
import com.vrvision.app.ui.components.ScreenTopBar
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.SwitchRow
import com.vrvision.app.ui.components.formatBytes
import com.vrvision.app.ui.components.formatDuration
import com.vrvision.app.ui.theme.Danger
import com.vrvision.app.ui.theme.Warn
import com.vrvision.core.enhance.PreviewSegment
import com.vrvision.core.planning.IssueSeverity
import com.vrvision.core.planning.OutputPlan

@Composable
fun EnhanceSettingsScreen(c: AppContainer, nav: Navigator, videoId: Long) {
    val video by remember(videoId) { c.videos.observe(videoId) }.collectAsState(initial = null)
    var draft by remember { mutableStateOf<EnhanceDraft?>(null) }
    var plan by remember { mutableStateOf<OutputPlan?>(null) }
    LaunchedEffect(video?.id) { video?.let { draft = c.draft(it) } }
    LaunchedEffect(video?.id, draft) {
        val v = video; val d = draft
        if (v != null && d != null) { c.drafts[v.id] = d; plan = c.plan(v, d) }
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        ScreenTopBar("Enhancement settings", onBack = nav::back)
        val v = video; val d = draft
        if (v == null || d == null) { CircularProgressIndicator(Modifier.padding(32.dp)); return@Column }
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SectionCard("Quality") {
                Text("Super resolution", style = MaterialTheme.typography.labelLarge)
                ChoiceChips(listOf(2.0, 1.5), d.scale, { if (it == 2.0) "2× (default)" else "1.5×" }) { draft = d.copy(scale = it, alternative = null) }
                Text(
                    "AI super resolution with Real-ESRGAN. 2× doubles width and height (4× the pixels); " +
                        "it reconstructs plausible detail, which is not guaranteed to match the real scene.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
                )
                SwitchRow("AI denoising", d.denoise, { draft = d.copy(denoise = it) },
                    help = if (d.denoise) "Strong-denoise model variant" else "Weak-denoise variant (keeps more grain)")
                SwitchRow("Sharpening", d.sharpen, { draft = d.copy(sharpen = it) }, help = "Conventional unsharp mask applied after AI, not AI itself")
                if (d.sharpen) LabeledSlider("Sharpening amount", d.sharpenAmount, 0.1f..0.8f, { draft = d.copy(sharpenAmount = it) })
                SwitchRow("Prefer HEVC output", d.preferHevc, { draft = d.copy(preferHevc = it, acceptAvc = false) })
            }

            SectionCard("Processing mode") {
                ChoiceChips(ModePreference.entries, d.mode, { when (it) { ModePreference.HYBRID -> "Hybrid (recommended)"; ModePreference.LOCAL -> "On this phone"; ModePreference.CLOUD -> "Cloud" } }) {
                    draft = d.copy(mode = it)
                }
                Text("Nothing is uploaded without a separate confirmation for this video.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            SectionCard("10-second preview segment") {
                val len = PreviewSegment.length(v.durationMs)
                val maxStart = (v.durationMs - len).coerceAtLeast(0)
                Text("Preview ${formatDuration(d.previewStartMs)} – ${formatDuration(d.previewStartMs + len)} of ${formatDuration(v.durationMs)}")
                if (maxStart > 0) LabeledSlider("Start", d.previewStartMs.toFloat(), 0f..maxStart.toFloat(),
                    { draft = d.copy(previewStartMs = it.toLong()) }) { formatDuration(it.toLong()) }
                Text("Choose a representative segment with detail and motion.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            SectionCard("Analysis") {
                val p = plan
                if (p == null) { CircularProgressIndicator(); return@SectionCard }
                InfoRow("Source", "${v.width}×${v.height} · ${v.frameRate?.let { "%.2f fps".format(it) } ?: "fps ?"} · ${v.videoMime ?: "?"}${v.bitDepth?.let { " · $it-bit" } ?: ""}")
                InfoRow("Stereo / projection", "${v.layout.lowercase()} · ${v.projection.lowercase()}")
                InfoRow("Requested output", "${p.requested.width}×${p.requested.height} (${"%.0f".format(p.pixelCountFactor)}× pixels)")
                InfoRow("Output codec", p.codec?.label ?: "None can encode this size")
                InfoRow("Playable on this phone", if (p.playableOnDevice) "Yes" else "No")
                InfoRow("Estimated file size", formatBytes(p.estimatedOutputBytes))
                val ds = c.device.deviceState()
                InfoRow("Free storage", formatBytes(ds.freeStorageBytes))
                InfoRow("Battery", ds.batteryPercent?.let { "$it%${if (ds.charging) " (charging)" else ""}" } ?: "Unknown")
                InfoRow("Thermal state", ds.thermal.name.lowercase())
                p.issues.forEach { issue ->
                    Text(
                        (if (issue.severity == IssueSeverity.BLOCKING) "✕ " else if (issue.severity == IssueSeverity.WARNING) "! " else "• ") + issue.message,
                        color = when (issue.severity) { IssueSeverity.BLOCKING -> Danger; IssueSeverity.WARNING -> Warn; IssueSeverity.INFO -> MaterialTheme.colorScheme.onSurfaceVariant },
                    )
                    if (issue.code == "HEVC_UNAVAILABLE") SwitchRow("Accept H.264 output", d.acceptAvc, { draft = d.copy(acceptAvc = it) })
                }
                if (p.alternatives.isNotEmpty()) {
                    Text("Sizes this phone can handle (your selection is not changed unless you pick one):", style = MaterialTheme.typography.labelLarge)
                    p.alternatives.forEach { alt ->
                        FilterChip(selected = d.alternative == alt, onClick = { draft = d.copy(alternative = if (d.alternative == alt) null else alt) },
                            label = { Text("${alt.width}×${alt.height} (${"%.2f".format(alt.scale)}×)") })
                    }
                }
            }

            val ready = plan?.let { !it.blocking && settingsFor(v, d, it) != null } == true
            Button(onClick = { nav.go(Dest.Recommendation(v.id)) }, enabled = ready, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                Text(if (ready) "Continue" else "Resolve the issues above to continue")
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}
