package com.vrvision.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.cloud.CloudClient
import com.vrvision.app.enhance.JobModes
import com.vrvision.app.ui.components.InfoRow
import com.vrvision.app.ui.components.ScreenTopBar
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.formatBytes
import com.vrvision.app.ui.theme.Warn
import kotlinx.coroutines.launch

/**
 * Explicit, per-video upload consent. Nothing is uploaded until the box is ticked and the
 * button pressed; the consent time and text version are sent to and recorded by the server.
 */
@Composable
fun CloudConsentScreen(c: AppContainer, nav: Navigator, videoId: Long) {
    val video by c.videos.observe(videoId).collectAsState(initial = null)
    val prefs by c.settings.state.collectAsState()
    val scope = rememberCoroutineScope()
    var agreed by remember { mutableStateOf(false) }
    var retentionHours by remember { mutableStateOf<Int?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(prefs.cloudUrl) {
        retentionHours = try { CloudClient(prefs.cloudUrl, c.settings.cloudApiKey ?: "").health().optInt("retention_hours") } catch (_: Exception) { null }
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        ScreenTopBar("Upload consent", onBack = nav::back)
        val v = video
        if (v == null) { CircularProgressIndicator(Modifier.padding(32.dp)); return@Column }
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SectionCard("What will be uploaded") {
                InfoRow("File", v.displayName)
                InfoRow("Size", formatBytes(v.sizeBytes))
                InfoRow("To server", prefs.cloudUrl)
                InfoRow("Connection", if (prefs.cloudUrl.startsWith("https://")) "Encrypted (HTTPS)" else "NOT encrypted (HTTP)")
                Text(
                    "The whole video file (including audio) is uploaded so the server can process the preview and, " +
                        "if you accept it, the full video. The operator of this server can technically access it.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            SectionCard("Retention") {
                Text(
                    retentionHours?.let { "The server deletes the source and results $it hours after processing, or immediately when you delete the job." }
                        ?: "The server's retention policy could not be read. Check with its operator before uploading.",
                )
                if (prefs.deleteCloudDataImmediately) Text("VRVision will ask the server to delete everything right after downloading the result.")
            }
            if (!prefs.cloudUrl.startsWith("https://")) Text("Warning: this server does not use HTTPS.", color = Warn)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = agreed, onCheckedChange = { agreed = it })
                Text("I agree to upload this video to the server above for processing.")
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                enabled = agreed,
                onClick = {
                    scope.launch {
                        val d = c.draft(v)
                        val plan = c.plan(v, d)
                        val s = settingsFor(v, d, plan)
                        if (s == null) { error = "The chosen output can't be produced; go back to the settings."; return@launch }
                        val consented = s.copy(consentGrantedAtMs = System.currentTimeMillis(), consentTextVersion = CloudClient.CONSENT_TEXT_VERSION)
                        val id = c.jobs.startPreview(v.id, v.durationMs, JobModes.CLOUD, consented, d.previewStartMs)
                        nav.home(); nav.go(Dest.Progress(id))
                    }
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) { Text("Upload and process 10-second preview") }
            OutlinedButton(onClick = nav::back, modifier = Modifier.fillMaxWidth()) { Text("Don't upload") }
            Spacer(Modifier.height(24.dp))
        }
    }
}
