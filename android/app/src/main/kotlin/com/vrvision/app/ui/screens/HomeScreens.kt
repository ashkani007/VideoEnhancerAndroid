package com.vrvision.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.enhance.JobStatus
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.formatDuration

/** Start screen: quick actions, recent videos and running jobs. */
@Composable
fun HomeScreen(c: AppContainer, nav: Navigator) {
    val originals by remember { c.videos.originals() }.collectAsState(initial = emptyList())
    val enhanced by remember { c.videos.enhanced() }.collectAsState(initial = emptyList())
    val jobs by remember { c.jobs.observeAll() }.collectAsState(initial = emptyList())
    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("VRVision", style = MaterialTheme.typography.headlineMedium)
        Text("Watch, find and enhance VR videos.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { nav.switchRoot(Dest.Library) }) { Text("Import video") }
            FilledTonalButton(onClick = { nav.switchRoot(Dest.Browser) }) { Text("Browse the web") }
        }
        OutlinedButton(onClick = { nav.go(Dest.Calibration) }) { Text("Headset calibration") }

        val running = jobs.filter { it.status !in JobStatus.terminal }
        if (running.isNotEmpty()) SectionCard("Processing") {
            running.forEach { j ->
                Text(
                    "${if (j.isPreview) "Preview" else "Full video"} · ${(j.progress * 100).toInt()}% · ${j.stage}",
                    modifier = Modifier.clickable { nav.go(Dest.Progress(j.id)) }.padding(vertical = 6.dp),
                )
            }
        }
        if (originals.isNotEmpty() || enhanced.isNotEmpty()) SectionCard("Recent") {
            (enhanced.take(3) + originals.take(5)).forEach { v ->
                Column(Modifier.fillMaxWidth().clickable { nav.go(if (v.kind == "ENHANCED") Dest.Player(v.id) else Dest.VideoInfo(v.id)) }.padding(vertical = 6.dp)) {
                    Text(v.displayName, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text("${v.width}×${v.height} · ${formatDuration(v.durationMs)}${if (v.kind == "ENHANCED") " · enhanced" else ""}",
                        color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                }
            }
        } else Text("Import a video or find one in the browser to get started.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(16.dp))
    }
}

/** Enhance tab: pick a library video to enhance, and see enhancement jobs. */
@Composable
fun EnhanceHubScreen(c: AppContainer, nav: Navigator) {
    val originals by remember { c.videos.originals() }.collectAsState(initial = emptyList())
    val jobs by remember { c.jobs.observeAll() }.collectAsState(initial = emptyList())
    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Enhance", style = MaterialTheme.typography.headlineMedium)
        Text(
            "2× AI super resolution (Real-ESRGAN) with AI denoising and conservative sharpening. You always get a " +
                "10-second preview to compare before processing the full video.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SectionCard("Choose a video") {
            if (originals.isEmpty()) Text("No videos yet: import one in the Library or download one from the Browser.")
            originals.take(30).forEach { v ->
                Text(
                    "${v.displayName}  (${v.width}×${v.height})", maxLines = 1, overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.fillMaxWidth().clickable { nav.go(Dest.EnhanceSettings(v.id)) }.padding(vertical = 8.dp),
                )
            }
        }
        if (jobs.isNotEmpty()) SectionCard("Jobs") {
            jobs.take(30).forEach { j ->
                Text(
                    "${if (j.isPreview) "Preview" else "Full"} · ${j.status.lowercase()} · ${(j.progress * 100).toInt()}% · ${j.stage}",
                    modifier = Modifier.fillMaxWidth().clickable {
                        nav.go(if (j.isPreview && j.status == JobStatus.SUCCEEDED) Dest.Compare(j.id) else Dest.Progress(j.id))
                    }.padding(vertical = 8.dp),
                )
            }
        }
    }
}
