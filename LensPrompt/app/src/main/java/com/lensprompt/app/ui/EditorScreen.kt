package com.lensprompt.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.R
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EditorScreen(scriptId: String, onBack: () -> Unit, onPrompt: () -> Unit) {
    val app = LocalContext.current.applicationContext as LensPromptApplication
    val loaded by app.scripts.loaded.collectAsState()
    val initial = app.scripts.get(scriptId)
    var title by rememberSaveable(scriptId, loaded) { mutableStateOf(initial?.title.orEmpty()) }
    var body by rememberSaveable(scriptId, loaded) { mutableStateOf(initial?.body.orEmpty()) }
    var saved by rememberSaveable { mutableStateOf(true) }

    // Autosave shortly after typing stops; the repository writes atomically.
    LaunchedEffect(title, body) {
        saved = false
        delay(600)
        app.scripts.save(scriptId, title, body)
        saved = true
    }
    // And immediately when leaving the editor.
    val latestTitle by rememberUpdatedState(title)
    val latestBody by rememberUpdatedState(body)
    DisposableEffect(scriptId) {
        onDispose { app.scripts.save(scriptId, latestTitle, latestBody) }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.common_back)) }
                },
                title = {
                    Text(if (saved) stringResource(R.string.editor_saved) else stringResource(R.string.editor_saving), color = LensColors.Muted, style = MaterialTheme.typography.labelLarge)
                },
                actions = {
                    TextButton(onClick = { app.scripts.save(scriptId, title, body); onPrompt() }, enabled = body.isNotBlank()) {
                        Icon(Icons.Filled.PlayArrow, contentDescription = null)
                        Text(stringResource(R.string.editor_prompt))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp).imePadding(),
        ) {
            OutlinedTextField(
                value = title,
                onValueChange = { title = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text(stringResource(R.string.editor_title_hint)) },
                textStyle = TextStyle(fontSize = 20.sp, textDirection = TextDirection.Content),
            )
            OutlinedTextField(
                value = body,
                onValueChange = { body = it },
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = 12.dp, bottom = 12.dp),
                placeholder = { Text(stringResource(R.string.editor_body_hint)) },
                textStyle = TextStyle(fontSize = 18.sp, lineHeight = 26.sp, textDirection = TextDirection.Content),
            )
        }
    }
}
