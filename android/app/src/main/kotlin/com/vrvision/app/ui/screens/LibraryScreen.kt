package com.vrvision.app.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.data.ImportResult
import com.vrvision.app.data.VideoEntity
import com.vrvision.app.data.toFormat
import com.vrvision.app.ui.components.StatusPill
import com.vrvision.app.ui.components.formatBytes
import com.vrvision.app.ui.components.formatDuration
import com.vrvision.app.ui.theme.Accent
import com.vrvision.app.ui.theme.Ok
import com.vrvision.app.ui.theme.Warn
import kotlinx.coroutines.launch

@Composable
fun LibraryScreen(c: AppContainer, nav: Navigator) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    val originals by c.videos.originals().collectAsState(initial = null)
    val enhanced by c.videos.enhanced().collectAsState(initial = null)
    val jobs by c.jobs.observeAll().collectAsState(initial = emptyList())
    val scope = rememberCoroutineScope()
    var importing by remember { mutableStateOf(false) }
    var importError by remember { mutableStateOf<String?>(null) }

    // SAF picker: the user grants access to exactly the files they choose; no storage permission.
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            importing = true
            scope.launch {
                when (val r = c.videos.import(uri)) {
                    is ImportResult.Imported -> nav.go(Dest.VideoInfo(r.id))
                    is ImportResult.Failed -> importError = r.reason
                }
                importing = false
            }
        }
    }

    Box(Modifier.fillMaxSize().safeDrawingPadding()) {
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 8.dp, top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("VRVision", style = MaterialTheme.typography.headlineMedium)
                    Text("Local VR player and video enhancer", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                OutlinedButton(onClick = { nav.go(Dest.Calibration) }) { Text("Headset") }
                IconButton(onClick = { nav.go(Dest.Settings) }, modifier = Modifier.size(56.dp)) {
                    Icon(Icons.Filled.Settings, contentDescription = "Settings and privacy")
                }
            }
            TabRow(selectedTabIndex = tab, containerColor = MaterialTheme.colorScheme.background, modifier = Modifier.padding(top = 8.dp)) {
                Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Library") })
                Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Enhanced") })
                Tab(selected = tab == 2, onClick = { tab = 2 }, text = { Text("Jobs") })
            }
            val list = if (tab == 0) originals else enhanced
            if (tab == 2) {
                if (jobs.isEmpty()) Text("No processing jobs yet.", modifier = Modifier.padding(24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(jobs, key = { it.id }) { j ->
                        Card(
                            modifier = Modifier.fillMaxWidth().clickable {
                                nav.go(if (j.isPreview && j.status == "SUCCEEDED") Dest.Compare(j.id) else Dest.Progress(j.id))
                            },
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        ) {
                            Column(Modifier.padding(14.dp)) {
                                Text((if (j.isPreview) "Preview" else "Full video") + " · " + j.mode.replace('_', ' ').lowercase(), style = MaterialTheme.typography.titleMedium)
                                Text("${j.status.lowercase()} · ${(j.progress * 100).toInt()}% · ${j.stage}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            } else when {
                list == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                list.isEmpty() -> EmptyState(tab == 0)
                else -> LazyColumn(
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 120.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(list, key = { it.id }) { v ->
                        VideoCard(v) { nav.go(if (v.kind == VideoEntity.KIND_ENHANCED) Dest.Player(v.id) else Dest.VideoInfo(v.id)) }
                    }
                }
            }
        }
        ExtendedFloatingActionButton(
            onClick = { if (!importing) picker.launch(arrayOf("video/*")) },
            icon = { if (importing) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Icon(Icons.Filled.Add, null) },
            text = { Text(if (importing) "Reading video…" else "Import video") },
            modifier = Modifier.align(Alignment.BottomEnd).padding(24.dp),
        )
    }

    importError?.let { msg ->
        AlertDialog(
            onDismissRequest = { importError = null },
            confirmButton = { TextButton(onClick = { importError = null }) { Text("OK") } },
            title = { Text("Can't import this file") },
            text = { Text(msg) },
        )
    }
}

@Composable
private fun EmptyState(originals: Boolean) {
    Column(Modifier.fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(if (originals) "No videos yet" else "No enhanced videos yet", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(8.dp))
        Text(
            if (originals) "Import a local video. Files stay on your phone; VRVision only stores a reference to them."
            else "Enhanced outputs appear here after processing completes and passes validation.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun VideoCard(v: VideoEntity, onClick: () -> Unit) {
    val f = v.toFormat()
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(v.displayName, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(
                "${v.width}×${v.height} · ${formatDuration(v.durationMs)} · ${v.frameRate?.let { "%.2f fps".format(it) } ?: "fps ?"} · ${formatBytes(v.sizeBytes)}",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill(f.projection.label(), Accent)
                StatusPill(f.layout.label(), Accent)
                if (v.kind == VideoEntity.KIND_ENHANCED) StatusPill("Enhanced", Ok)
                else if (!v.formatConfirmed) StatusPill("Confirm format", Warn)
            }
        }
    }
}
