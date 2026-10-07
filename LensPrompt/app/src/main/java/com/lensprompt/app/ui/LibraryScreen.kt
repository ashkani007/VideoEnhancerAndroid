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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.R
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
    var floating by remember { mutableStateOf<Script?>(null) }
    val snackbar = remember { SnackbarHostState() }
    val pastedScript = stringResource(R.string.library_pasted_script)
    val newScript = stringResource(R.string.library_new_script)
    val untitled = stringResource(R.string.common_untitled)

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
                            val title = text.lineSequence().firstOrNull { it.isNotBlank() }?.trim()?.take(40) ?: pastedScript
                            onEdit(app.scripts.create(title, text.trim()).id)
                        }
                    }) { Icon(Icons.Filled.ContentPaste, contentDescription = stringResource(R.string.library_new_from_clipboard)) }
                    IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, contentDescription = stringResource(R.string.common_settings)) }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { onEdit(app.scripts.create().id) },
                // M3 clears the text slot's semantics; label the button explicitly for TalkBack.
                modifier = Modifier.semantics { contentDescription = newScript },
                icon = { Icon(Icons.Filled.Add, contentDescription = null) },
                text = { Text(newScript) },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item { FloatingModeBanner(Modifier.padding(top = 4.dp)) }
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
                    placeholder = { Text(stringResource(R.string.library_search_hint)) },
                )
            }
            if (filtered.isEmpty()) {
                item {
                    Text(
                        if (query.isBlank()) stringResource(R.string.library_empty) else stringResource(R.string.library_no_match, query),
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
                    onFloating = { floating = s },
                )
            }
        }
    }

    floating?.let { s -> FloatingPrompterDialog(s.id) { floating = null } }
    renaming?.let { s ->
        var title by remember(s.id) { mutableStateOf(s.title) }
        AlertDialog(
            onDismissRequest = { renaming = null },
            title = { Text(stringResource(R.string.library_rename_title)) },
            text = { OutlinedTextField(value = title, onValueChange = { title = it }, singleLine = true) },
            confirmButton = { TextButton(onClick = { app.scripts.rename(s.id, title.trim()); renaming = null }) { Text(stringResource(R.string.common_rename)) } },
            dismissButton = { TextButton(onClick = { renaming = null }) { Text(stringResource(R.string.common_cancel)) } },
        )
    }
    deleting?.let { s ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text(stringResource(R.string.library_delete_title)) },
            text = { Text(stringResource(R.string.library_delete_message, s.title.ifBlank { untitled })) },
            confirmButton = { TextButton(onClick = { app.scripts.delete(s.id); deleting = null }) { Text(stringResource(R.string.common_delete), color = LensColors.Recording) } },
            dismissButton = { TextButton(onClick = { deleting = null }) { Text(stringResource(R.string.common_cancel)) } },
        )
    }
}

@Composable
private fun FirstRunCard(onDismiss: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = LensColors.SurfaceHigh)) {
        Column(Modifier.padding(16.dp)) {
            Text(stringResource(R.string.library_quick_start), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            listOf(
                stringResource(R.string.library_quick_start_step1),
                stringResource(R.string.library_quick_start_step2),
                stringResource(R.string.library_quick_start_step3),
                stringResource(R.string.library_quick_start_step4),
            ).forEachIndexed { i, line ->
                Row(Modifier.padding(vertical = 3.dp)) {
                    Text("${i + 1}.", color = LensColors.Accent, modifier = Modifier.width(22.dp), fontWeight = FontWeight.Bold)
                    Text(line)
                }
            }
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
                TextButton(onClick = onDismiss) { Text(stringResource(R.string.library_got_it)) }
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
    onFloating: () -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    val untitled = stringResource(R.string.common_untitled)
    val emptyScript = stringResource(R.string.library_empty_script)
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onEdit),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = LensColors.Surface),
    ) {
        Row(Modifier.padding(start = 16.dp, top = 12.dp, bottom = 12.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    script.title.ifBlank { untitled },
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    script.body.replace('\n', ' ').take(120).ifBlank { emptyScript },
                    color = LensColors.Muted,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodyMedium,
                )
                val words = script.wordCount
                val minutes = (words / 150.0)
                Text(
                    stringResource(
                        R.string.library_script_meta, words, if (minutes < 1) "<1" else "%.0f".format(minutes),
                        DateUtils.getRelativeTimeSpanString(script.updatedAt),
                    ),
                    color = LensColors.Muted,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            FilledIconButton(onClick = onOpen, modifier = Modifier.size(48.dp)) {
                Icon(Icons.Filled.PlayArrow, contentDescription = stringResource(R.string.library_start_prompting))
            }
            Box {
                IconButton(onClick = { menu = true }, modifier = Modifier.size(48.dp)) {
                    Icon(Icons.Filled.MoreVert, contentDescription = stringResource(R.string.library_more_actions))
                }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text(stringResource(R.string.floating_title)) }, onClick = { menu = false; onFloating() })
                    DropdownMenuItem(text = { Text(stringResource(R.string.common_edit)) }, onClick = { menu = false; onEdit() })
                    DropdownMenuItem(text = { Text(stringResource(R.string.common_rename)) }, onClick = { menu = false; onRename() })
                    DropdownMenuItem(text = { Text(stringResource(R.string.library_duplicate)) }, onClick = { menu = false; onDuplicate() })
                    DropdownMenuItem(text = { Text(stringResource(R.string.common_delete)) }, onClick = { menu = false; onDelete() })
                }
            }
        }
    }
}
