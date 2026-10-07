package com.lensprompt.app.ui

import android.content.ClipboardManager
import android.content.Context
import android.text.format.DateUtils
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.data.Script

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryScreen(onOpen: (String) -> Unit, onEdit: (String) -> Unit, onSettings: () -> Unit) {
    val context = LocalContext.current
    val app = context.applicationContext as LensPromptApplication
    val scripts by app.scripts.scripts.collectAsState()
    val settings by app.settings.settings.collectAsState()
    val storageError by app.scripts.lastError.collectAsState()
    var query by rememberSaveable { mutableStateOf("") }
    var renaming by remember { mutableStateOf<Script?>(null) }
    var deleting by remember { mutableStateOf<Script?>(null) }
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(storageError) {
        storageError?.let { snackbar.showSnackbar(it); app.scripts.clearError() }
    }

    val filtered = remember(scripts, query) {
        if (query.isBlank()) scripts
        else scripts.filter { it.title.contains(query, ignoreCase = true) || it.body.contains(query, ignoreCase = true) }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            TopAppBar(
                title = { Text("LensPrompt", fontWeight = FontWeight.SemiBold) },
                actions = {
                    IconButton(onClick = {
                        val text = (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager)
                            .primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)?.toString()
                        if (!text.isNullOrBlank()) {
                            val title = text.lineSequence().firstOrNull { it.isNotBlank() }?.trim()?.take(40) ?: "Pasted script"
                            onEdit(app.scripts.create(title, text.trim()).id)
                        }
                    }) { Icon(Icons.Filled.ContentPaste, contentDescription = "New script from clipboard") }
                    IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, contentDescription = "Settings") }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { onEdit(app.scripts.create().id) },
                // M3 clears the text slot's semantics; label the button explicitly for TalkBack.
                modifier = Modifier.semantics { contentDescription = "New script" },
                icon = { Icon(Icons.Filled.Add, contentDescription = null) },
                text = { Text("New script") },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (!settings.firstRunDone) {
                item { FirstRunCard(onDismiss = { app.settings.update { it.copy(firstRunDone = true) } }) }
            }
            item {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                    placeholder = { Text("Search scripts") },
                )
            }
            if (filtered.isEmpty()) {
                item {
                    Text(
                        if (query.isBlank()) "No scripts yet. Tap “New script” or paste one." else "No scripts match “$query”.",
                        color = LensColors.Muted,
                        modifier = Modifier.padding(24.dp),
                    )
                }
            }
            items(filtered, key = { it.id }) { s ->
                ScriptRow(
                    script = s,
                    onOpen = { onOpen(s.id) },
                    onEdit = { onEdit(s.id) },
                    onRename = { renaming = s },
                    onDuplicate = { app.scripts.duplicate(s.id) },
                    onDelete = { deleting = s },
                )
            }
        }
    }

    renaming?.let { s ->
        var title by remember(s.id) { mutableStateOf(s.title) }
        AlertDialog(
            onDismissRequest = { renaming = null },
            title = { Text("Rename script") },
            text = { OutlinedTextField(value = title, onValueChange = { title = it }, singleLine = true) },
            confirmButton = { TextButton(onClick = { app.scripts.rename(s.id, title.trim()); renaming = null }) { Text("Rename") } },
            dismissButton = { TextButton(onClick = { renaming = null }) { Text("Cancel") } },
        )
    }
    deleting?.let { s ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Delete script?") },
            text = { Text("“${s.title.ifBlank { "Untitled" }}” will be permanently deleted.") },
            confirmButton = { TextButton(onClick = { app.scripts.delete(s.id); deleting = null }) { Text("Delete", color = LensColors.Recording) } },
            dismissButton = { TextButton(onClick = { deleting = null }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun FirstRunCard(onDismiss: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = LensColors.SurfaceHigh)) {
        Column(Modifier.padding(16.dp)) {
            Text("Quick start", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            listOf(
                "Add or paste a script.",
                "Choose Smart Follow (follows your voice) or Manual (fixed speed).",
                "Allow the microphone when asked — Smart Follow needs it.",
                "Press play and start reading at your own pace.",
            ).forEachIndexed { i, line ->
                Row(Modifier.padding(vertical = 3.dp)) {
                    Text("${i + 1}.", color = LensColors.Accent, modifier = Modifier.width(22.dp), fontWeight = FontWeight.Bold)
                    Text(line)
                }
            }
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
                TextButton(onClick = onDismiss) { Text("Got it") }
            }
        }
    }
}

@Composable
private fun ScriptRow(
    script: Script,
    onOpen: () -> Unit,
    onEdit: () -> Unit,
    onRename: () -> Unit,
    onDuplicate: () -> Unit,
    onDelete: () -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onEdit),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = LensColors.Surface),
    ) {
        Row(Modifier.padding(start = 16.dp, top = 12.dp, bottom = 12.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    script.title.ifBlank { "Untitled" },
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    script.body.replace('\n', ' ').take(120).ifBlank { "Empty script" },
                    color = LensColors.Muted,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodyMedium,
                )
                val words = script.wordCount
                val minutes = (words / 150.0)
                Text(
                    "$words words · ~${if (minutes < 1) "<1" else "%.0f".format(minutes)} min · " +
                        DateUtils.getRelativeTimeSpanString(script.updatedAt),
                    color = LensColors.Muted,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            FilledIconButton(onClick = onOpen, modifier = Modifier.size(48.dp)) {
                Icon(Icons.Filled.PlayArrow, contentDescription = "Start prompting")
            }
            Box {
                IconButton(onClick = { menu = true }, modifier = Modifier.size(48.dp)) {
                    Icon(Icons.Filled.MoreVert, contentDescription = "More actions")
                }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Edit") }, onClick = { menu = false; onEdit() })
                    DropdownMenuItem(text = { Text("Rename") }, onClick = { menu = false; onRename() })
                    DropdownMenuItem(text = { Text("Duplicate") }, onClick = { menu = false; onDuplicate() })
                    DropdownMenuItem(text = { Text("Delete") }, onClick = { menu = false; onDelete() })
                }
            }
        }
    }
}
