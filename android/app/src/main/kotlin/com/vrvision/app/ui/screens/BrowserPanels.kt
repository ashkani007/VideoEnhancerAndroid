package com.vrvision.app.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.browser.BrowserPrompt
import com.vrvision.app.browser.TabUi
import com.vrvision.app.ui.components.ChoiceChips
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.StatusPill
import com.vrvision.app.ui.components.SwitchRow
import com.vrvision.app.ui.components.formatBytes
import com.vrvision.app.ui.theme.Danger
import com.vrvision.app.ui.theme.Ok
import com.vrvision.app.ui.theme.Warn
import com.vrvision.core.browser.DownloadCategory
import com.vrvision.core.browser.DownloadDecision
import com.vrvision.core.browser.DownloadPolicy
import com.vrvision.core.browser.DownloadRequest
import com.vrvision.core.browser.MediaAssessment
import com.vrvision.core.browser.MediaDetector
import com.vrvision.core.media.VideoFormat
import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.StereoLayout
import kotlinx.coroutines.launch

@Composable
private fun PanelFrame(title: String, onClose: () -> Unit, content: @Composable () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f).padding(start = 8.dp))
                IconButton(onClick = onClose) { Icon(Icons.Filled.Close, "Close") }
            }
            content()
        }
    }
}

@Composable
private fun Row2(title: String, subtitle: String, onClick: () -> Unit, trailing: @Composable () -> Unit = {}) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title.ifBlank { subtitle }, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyLarge)
            Text(subtitle, maxLines = 1, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
        }
        trailing()
    }
}

/** Tabs, bookmarks, history and downloads. */
@Composable
fun BrowserListPanel(c: AppContainer, nav: Navigator, panel: BrowserPanel, onClose: () -> Unit) {
    val browser = c.browser
    val dao = c.browserDb.dao()
    val scope = rememberCoroutineScope()
    when (panel) {
        BrowserPanel.TABS -> PanelFrame("Tabs", onClose) {
            val tabs by browser.tabs.collectAsState()
            val ui by browser.ui.collectAsState()
            Button(onClick = { browser.newTab(); onClose() }, modifier = Modifier.padding(horizontal = 16.dp)) { Text("New tab") }
            LazyColumn {
                items(tabs.tabs, key = { it.id }) { t ->
                    val u = ui[t.id]
                    Row2(
                        (if (t.id == tabs.activeId) "● " else "") + (u?.title?.ifBlank { null } ?: t.title.ifBlank { "New tab" }),
                        u?.url ?: t.url,
                        onClick = { browser.select(t.id); onClose() },
                    ) { IconButton(onClick = { browser.close(t.id) }) { Icon(Icons.Filled.Close, "Close tab") } }
                }
            }
        }
        BrowserPanel.BOOKMARKS -> PanelFrame("Bookmarks", onClose) {
            val list by remember { dao.bookmarks() }.collectAsState(initial = emptyList())
            if (list.isEmpty()) Text("No bookmarks yet. Use the menu → Bookmark this page.", modifier = Modifier.padding(16.dp))
            LazyColumn {
                items(list, key = { it.id }) { b ->
                    Row2(b.title, b.url, onClick = { browser.load(b.url); onClose() }) {
                        IconButton(onClick = { scope.launch { dao.removeBookmark(b.url) } }) { Icon(Icons.Filled.Delete, "Remove bookmark") }
                    }
                }
            }
        }
        BrowserPanel.HISTORY -> PanelFrame("History", onClose) {
            val list by remember { dao.history() }.collectAsState(initial = emptyList())
            TextButton(onClick = { scope.launch { dao.clearHistory() } }, modifier = Modifier.padding(horizontal = 8.dp)) { Text("Clear history") }
            LazyColumn {
                items(list, key = { it.id }) { h -> Row2(h.title, h.url, onClick = { browser.load(h.url); onClose() }) }
            }
        }
        BrowserPanel.DOWNLOADS -> PanelFrame("Downloads", onClose) {
            val list by remember { c.downloads.all() }.collectAsState(initial = emptyList())
            LaunchedEffect(Unit) { c.downloads.ensurePolling() }
            if (list.isEmpty()) Text("No downloads. Files are saved privately inside VRVision.", modifier = Modifier.padding(16.dp))
            LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(list, key = { it.id }) { d ->
                    SectionCard(d.fileName) {
                        StatusPill(d.status.lowercase(), when (d.status) { "SUCCESSFUL" -> Ok; "FAILED" -> Danger; "RUNNING", "PENDING" -> MaterialTheme.colorScheme.primary; else -> Warn })
                        if (d.status == "RUNNING") {
                            if (d.bytesTotal > 0) LinearProgressIndicator(progress = { d.bytesDone.toFloat() / d.bytesTotal }, modifier = Modifier.fillMaxWidth())
                            else LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                            Text("${formatBytes(d.bytesDone)} of ${if (d.bytesTotal > 0) formatBytes(d.bytesTotal) else "?"}")
                            OutlinedButton(onClick = { c.downloads.cancel(d) }) { Text("Cancel") }
                        }
                        d.failure?.let { Text(it, color = Danger) }
                        if (d.status == "SUCCESSFUL" && d.category == DownloadCategory.VIDEO.name) {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                FilledTonalButton(onClick = {
                                    scope.launch { c.downloads.importToLibrary(d)?.let { id -> onClose(); nav.go(Dest.VideoInfo(id)) } }
                                }) { Text(if (d.importedVideoId != null) "Open in library" else "Add to library") }
                                Button(onClick = {
                                    scope.launch { c.downloads.importToLibrary(d)?.let { id -> onClose(); nav.go(Dest.EnhanceSettings(id)) } }
                                }) { Text("Enhance") }
                            }
                        }
                    }
                }
            }
        }
        else -> Unit
    }
}

/** Detected videos on the current page, with honest play/enhance availability. */
@Composable
fun MediaPanel(c: AppContainer, nav: Navigator, ui: TabUi?, onClose: () -> Unit) {
    val formats = remember { mutableStateMapOf<String, VideoFormat>() }
    var confirm by remember { mutableStateOf<Pair<MediaAssessment, DownloadDecision>?>(null) }
    PanelFrame("Videos on this page", onClose) {
        val items = ui?.media.orEmpty().map { MediaDetector.assess(it) }
        Text(
            "Only sources the page exposes directly are listed. Protected (DRM), login-only and script-generated " +
                "streams can't be opened outside the page. Not every site will work.",
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = 16.dp),
        )
        if (items.isEmpty()) Text("No videos found yet. Start playback in the page, then look again.", modifier = Modifier.padding(16.dp))
        LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(items, key = { it.candidate.url }) { a ->
                val f = formats[a.candidate.url] ?: VideoFormat(layout = a.format.layout, projection = a.format.projection)
                SectionCard(a.candidate.kind.label) {
                    Text(a.candidate.url, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (a.canPlay) {
                        Text("Projection (suggested: ${a.format.reasons.firstOrNull() ?: "none"})", style = MaterialTheme.typography.labelLarge)
                        ChoiceChips(ProjectionType.entries, f.projection, { it.label() }) { formats[a.candidate.url] = f.copy(projection = it) }
                        ChoiceChips(StereoLayout.entries, f.layout, { it.label() }) { formats[a.candidate.url] = f.copy(layout = it) }
                        if (f.layout.isStereo) SwitchRow("Swap eyes", f.swapEyes, { formats[a.candidate.url] = f.copy(swapEyes = it) })
                        Button(onClick = {
                            onClose()
                            nav.go(Dest.StreamPlayer(a.candidate.url, a.candidate.kind.mime, f))
                        }) { Text("Open in VRVision Player") }
                    } else Text(a.playReason, color = Warn)
                    if (a.canEnhance) {
                        FilledTonalButton(onClick = {
                            val req = DownloadRequest(a.candidate.url, a.candidate.kind.mime, null, -1, userInitiated = true)
                            confirm = a to DownloadPolicy.evaluate(req)
                        }) { Text("Enhance Video…") }
                    } else if (a.canPlay) Text("Enhancement unavailable: ${a.enhanceReason}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
    confirm?.let { (a, decision) ->
        val f = formats[a.candidate.url] ?: VideoFormat(layout = a.format.layout, projection = a.format.projection)
        when (decision) {
            is DownloadDecision.Block -> AlertDialog(
                onDismissRequest = { confirm = null },
                confirmButton = { TextButton(onClick = { confirm = null }) { Text("OK") } },
                title = { Text("Can't enhance this video") }, text = { Text(decision.reason) },
            )
            is DownloadDecision.Confirm -> AlertDialog(
                onDismissRequest = { confirm = null },
                title = { Text("Download to enhance?") },
                text = {
                    Text(
                        "VRVision will download \"${decision.fileName}\" from ${decision.host} into its private storage, then open " +
                            "the enhancement analysis (estimate, 10-second preview, comparison, full processing). Only download videos " +
                            "you are allowed to save. No login cookies are sent; if the site requires one, the download will fail." +
                            decision.warnings.joinToString("") { "\n• $it" },
                    )
                },
                confirmButton = {
                    TextButton(onClick = {
                        confirm = null
                        // App scope: the panel closes right away, the download must still be queued.
                        c.appScope.launch { c.downloads.enqueue(a.candidate.url, decision.fileName, a.candidate.kind.mime, decision.category, "ENHANCE", f) }
                        onClose()
                    }) { Text("Download") }
                },
                dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } },
            )
        }
    }
}

/** Dialogs the page triggers: external apps, downloads, protected media, file chooser, messages. */
@Composable
fun BrowserPrompts(c: AppContainer, nav: Navigator) {
    val browser = c.browser
    val prompt by browser.prompt.collectAsState()
    val chooser = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris: List<Uri> ->
        (browser.prompt.value as? BrowserPrompt.FileChooser)?.let { browser.answerFileChooser(it, uris.ifEmpty { null }) }
    }
    when (val p = prompt) {
        null -> Unit
        is BrowserPrompt.External -> AlertDialog(
            onDismissRequest = browser::dismissPrompt,
            title = { Text("Open in another app?") },
            text = { Text("This page wants to open a ${p.scheme}: link:\n${p.url.take(200)}") },
            confirmButton = { TextButton(onClick = { browser.openExternal(p.url) }) { Text("Open") } },
            dismissButton = { TextButton(onClick = browser::dismissPrompt) { Text("Cancel") } },
        )
        is BrowserPrompt.Download -> when (val d = p.decision) {
            is DownloadDecision.Block -> AlertDialog(
                onDismissRequest = browser::dismissPrompt,
                confirmButton = { TextButton(onClick = browser::dismissPrompt) { Text("OK") } },
                title = { Text("Download blocked") }, text = { Text(d.reason) },
            )
            is DownloadDecision.Confirm -> AlertDialog(
                onDismissRequest = browser::dismissPrompt,
                title = { Text("Download file?") },
                text = {
                    Text(
                        "${d.fileName}\nfrom ${d.host}\n${if (p.request.contentLength > 0) formatBytes(p.request.contentLength) else "Size unknown"}" +
                            d.warnings.joinToString("") { "\n• $it" } + "\n\nSaved privately inside VRVision.",
                    )
                },
                confirmButton = {
                    TextButton(onClick = {
                        browser.dismissPrompt()
                        c.appScope.launch { c.downloads.enqueue(p.request.url, d.fileName, p.request.mimeType, d.category) }
                    }) { Text("Download") }
                },
                dismissButton = { TextButton(onClick = browser::dismissPrompt) { Text("Cancel") } },
            )
        }
        is BrowserPrompt.ProtectedMedia -> AlertDialog(
            onDismissRequest = { browser.answerProtectedMedia(p, false) },
            title = { Text("Protected content") },
            text = { Text("${p.origin} wants to play DRM-protected media inside the page. It can only be watched in the page, not opened or enhanced in VRVision.") },
            confirmButton = { TextButton(onClick = { browser.answerProtectedMedia(p, true) }) { Text("Allow") } },
            dismissButton = { TextButton(onClick = { browser.answerProtectedMedia(p, false) }) { Text("Block") } },
        )
        is BrowserPrompt.FileChooser -> LaunchedEffect(p) {
            val types = p.params.acceptTypes.filter { it.isNotBlank() }.ifEmpty { listOf("*/*") }
            try { chooser.launch(types.toTypedArray()) } catch (_: Exception) { browser.answerFileChooser(p, null) }
        }
        is BrowserPrompt.Message -> AlertDialog(
            onDismissRequest = browser::dismissPrompt,
            confirmButton = { TextButton(onClick = browser::dismissPrompt) { Text("OK") } },
            title = { Text(p.title) }, text = { Text(p.text) },
        )
    }
}
