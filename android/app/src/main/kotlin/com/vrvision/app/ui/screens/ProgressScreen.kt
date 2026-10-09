package com.vrvision.app.ui.screens

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.enhance.JobModes
import com.vrvision.app.enhance.JobStatus
import com.vrvision.app.ui.components.InfoRow
import com.vrvision.app.ui.components.ScreenTopBar
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.StatusPill
import com.vrvision.app.ui.components.formatDuration
import com.vrvision.app.ui.theme.Danger
import com.vrvision.app.ui.theme.Ok
import com.vrvision.app.ui.theme.Warn
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Real progress only: frames processed (local) or the server's reported progress (cloud). */
@Composable
fun ProgressScreen(c: AppContainer, nav: Navigator, jobId: Long) {
    val job by c.jobs.observe(jobId).collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) { while (true) { delay(1000); now = System.currentTimeMillis() } }
    val notifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    LaunchedEffect(Unit) { if (Build.VERSION.SDK_INT >= 33) notifications.launch(Manifest.permission.POST_NOTIFICATIONS) }

    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        ScreenTopBar("Processing", onBack = nav::back)
        val j = job
        if (j == null) { CircularProgressIndicator(Modifier.padding(32.dp)); return@Column }
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionCard(if (j.isPreview) "10-second preview" else "Full video") {
                StatusPill(
                    when (j.status) { JobStatus.QUEUED -> "Queued"; JobStatus.RUNNING -> "Running"; JobStatus.SUCCEEDED -> "Done"; JobStatus.UNSUPPORTED -> "Not supported"; else -> j.status.lowercase().replaceFirstChar { it.uppercase() } },
                    when (j.status) { JobStatus.SUCCEEDED -> Ok; JobStatus.FAILED, JobStatus.UNSUPPORTED -> Danger; JobStatus.CANCELLED, JobStatus.REJECTED -> Warn; else -> MaterialTheme.colorScheme.primary },
                )
                InfoRow("Mode", when (j.mode) { JobModes.LOCAL_AI -> "On this phone, AI (Real-ESRGAN)"; JobModes.LOCAL_CONVENTIONAL -> "On this phone, conventional Lanczos (not AI)"; else -> "Cloud, AI (Real-ESRGAN)" })
                if (j.status == JobStatus.RUNNING || j.status == JobStatus.QUEUED) {
                    if (j.progress > 0f) LinearProgressIndicator(progress = { j.progress }, modifier = Modifier.fillMaxWidth())
                    else LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    Text(j.stage.ifBlank { "Waiting to start" })
                }
                j.startedAt?.let { start ->
                    val end = j.finishedAt ?: now
                    InfoRow("Elapsed", formatDuration(end - start))
                    if (j.status == JobStatus.RUNNING && j.progress > 0.02f) {
                        val remaining = ((end - start) / j.progress * (1 - j.progress)).toLong()
                        InfoRow("Estimated remaining", "about ${formatDuration(remaining)} (from measured speed)")
                    }
                }
                if (j.message.isNotBlank()) Text(j.message, color = if (j.status == JobStatus.SUCCEEDED) MaterialTheme.colorScheme.onSurface else Danger)
            }

            when (j.status) {
                JobStatus.QUEUED, JobStatus.RUNNING -> {
                    OutlinedButton(onClick = { scope.launch { c.jobs.cancel(j.id) } }, modifier = Modifier.fillMaxWidth().height(52.dp)) {
                        Text("Cancel (partial output is deleted)")
                    }
                    Text("You can leave this screen; processing continues with a notification.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                JobStatus.SUCCEEDED -> if (j.isPreview) {
                    Button(onClick = { nav.replace(Dest.Compare(j.id)) }, modifier = Modifier.fillMaxWidth().height(56.dp)) { Text("Compare original and enhanced") }
                } else {
                    j.outputVideoId?.let { out ->
                        Button(onClick = { nav.home(); nav.go(Dest.Player(out)) }, modifier = Modifier.fillMaxWidth().height(56.dp)) { Text("Play enhanced video in VR") }
                    }
                }
                else -> {
                    OutlinedButton(onClick = { nav.home(); nav.go(Dest.Player(j.videoId)) }, modifier = Modifier.fillMaxWidth()) { Text("Play the original instead") }
                    OutlinedButton(onClick = { nav.home(); nav.go(Dest.EnhanceSettings(j.videoId)) }, modifier = Modifier.fillMaxWidth()) { Text("Change settings") }
                }
            }
        }
    }
}
