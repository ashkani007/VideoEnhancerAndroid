package com.vrvision.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.data.toFormat
import com.vrvision.app.data.toInfo
import com.vrvision.app.ui.components.ChoiceChips
import com.vrvision.app.ui.components.InfoRow
import com.vrvision.app.ui.components.ScreenTopBar
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.SwitchRow
import com.vrvision.app.ui.components.formatBytes
import com.vrvision.app.ui.components.formatDuration
import com.vrvision.core.media.VideoFormat
import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.StereoLayout
import com.vrvision.core.stereo.StereoPacking
import kotlinx.coroutines.launch

@Composable
fun VideoInfoScreen(c: AppContainer, nav: Navigator, videoId: Long) {
    val video by remember(videoId) { c.videos.observe(videoId) }.collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    var format by remember { mutableStateOf<VideoFormat?>(null) }
    LaunchedEffect(video?.id) { if (format == null) video?.let { format = it.toFormat() } }

    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        ScreenTopBar("Video information", onBack = nav::back)
        val v = video
        val f = format
        if (v == null || f == null) {
            CircularProgressIndicator(Modifier.padding(32.dp))
            return@Column
        }
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(v.displayName, style = MaterialTheme.typography.titleLarge)
            SectionCard("Source") {
                InfoRow("Resolution", "${v.width} × ${v.height}" + if (v.rotationDegrees != 0) " (rotated ${v.rotationDegrees}°)" else "")
                InfoRow("Duration", formatDuration(v.durationMs))
                InfoRow("Frame rate", v.frameRate?.let { "%.3f fps".format(it) } ?: "Not detectable")
                InfoRow("Video codec", buildString {
                    append(v.toInfo().codecLabel)
                    v.codecProfile?.let { append(" · $it") }
                })
                InfoRow("Bit depth", v.bitDepth?.let { "$it-bit" } ?: "Not detectable")
                InfoRow("HDR", when (v.hdr) { true -> "Yes"; false -> "No"; null -> "Not signalled" })
                InfoRow("Bitrate", v.bitrate?.let { "%.1f Mbit/s".format(it / 1e6) } ?: "Unknown")
                InfoRow("Audio", if (v.audioTrackCount == 0) "None" else "${v.audioTrackCount} track(s): ${v.audioSummary}")
                InfoRow("Subtitles", if (v.subtitleTrackCount == 0) "None embedded" else "${v.subtitleTrackCount} track(s)")
                InfoRow("File size", formatBytes(v.sizeBytes))
            }

            SectionCard("How should this video be shown?") {
                Text(
                    "Stereo layout can't always be detected automatically. " +
                        if (v.formatConfirmed) "You confirmed this format." else "Suggested: ${v.formatHint.ifBlank { "no hints found" }}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text("Projection", style = MaterialTheme.typography.labelLarge)
                ChoiceChips(ProjectionType.entries, f.projection, { it.label() }) { format = f.copy(projection = it) }
                Text("Stereo layout", style = MaterialTheme.typography.labelLarge)
                ChoiceChips(StereoLayout.entries, f.layout, { it.label() }) { format = f.copy(layout = it) }
                if (f.layout.isStereo) {
                    Text("Eye packing", style = MaterialTheme.typography.labelLarge)
                    ChoiceChips(StereoPacking.entries, f.packing, { it.label() }) { format = f.copy(packing = it) }
                    SwitchRow(
                        "Swap left/right eyes", f.swapEyes, { format = f.copy(swapEyes = it) },
                        help = "Use if depth looks inverted (near objects appear far).",
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { format = v.toFormat() }) { Text("Reset") }
                    OutlinedButton(onClick = { scope.launch { c.videos.setFormat(v.id, f) } }) {
                        Text(if (v.formatConfirmed && f == v.toFormat()) "Saved" else "Save format")
                    }
                }
            }

            Button(
                onClick = { scope.launch { c.videos.setFormat(v.id, f); nav.go(Dest.Player(v.id)) } },
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) { Text("Play in VR") }
            androidx.compose.material3.FilledTonalButton(
                onClick = { scope.launch { c.videos.setFormat(v.id, f); nav.go(Dest.EnhanceSettings(v.id)) } },
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) { Text("Enhance (2× AI super resolution)…") }
            OutlinedButton(
                onClick = { scope.launch { c.videos.remove(v.id); nav.back() } },
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) { Text("Remove from library (file is kept)") }
            androidx.compose.foundation.layout.Spacer(Modifier.height(24.dp))
        }
    }
}
