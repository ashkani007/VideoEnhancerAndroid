package com.vrvision.app.ui.screens

import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.browser.BookmarkEntity
import com.vrvision.app.ui.theme.Ok
import com.vrvision.app.ui.theme.Warn
import com.vrvision.core.browser.UrlPolicy
import kotlinx.coroutines.launch

enum class BrowserPanel { NONE, TABS, BOOKMARKS, HISTORY, DOWNLOADS, MEDIA }

@Composable
fun BrowserScreen(c: AppContainer, nav: Navigator) {
    val context = LocalContext.current
    val browser = c.browser
    val scope = rememberCoroutineScope()
    val tabs by browser.tabs.collectAsState()
    val uiMap by browser.ui.collectAsState()
    val prompt by browser.prompt.collectAsState()
    val fullscreen by browser.fullscreen.collectAsState()
    var panel by remember { mutableStateOf(BrowserPanel.NONE) }
    var vrMode by remember { mutableStateOf(false) }
    var address by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf(false) }
    var inputError by remember { mutableStateOf<String?>(null) }
    var menu by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { browser.restore(c.settings.restoreBrowserSession); c.downloads.ensurePolling() }
    DisposableEffect(context) {
        browser.attach(context)
        onDispose { browser.detach() }
    }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val obs = LifecycleEventObserver { _, e ->
            if (e == Lifecycle.Event.ON_PAUSE) browser.onPause()
            if (e == Lifecycle.Event.ON_RESUME) browser.onResume()
        }
        lifecycle.addObserver(obs)
        onDispose { lifecycle.removeObserver(obs) }
    }
    // A download the user asked to play or enhance has finished and is in the library.
    LaunchedEffect(Unit) {
        c.downloads.imported.collect { d ->
            when (d.purpose) {
                "ENHANCE" -> nav.go(Dest.EnhanceSettings(d.videoId))
                "PLAY" -> nav.go(Dest.Player(d.videoId))
            }
        }
    }

    val activeId = tabs.activeId
    val ui = activeId?.let { uiMap[it] }
    LaunchedEffect(ui?.url, editing) { if (!editing) address = ui?.url?.takeIf { it != UrlPolicy.HOME_URL }.orEmpty() }

    BackHandler(enabled = fullscreen != null || panel != BrowserPanel.NONE || editing || (activeId != null && ui?.canGoBack == true)) {
        when {
            fullscreen != null -> browser.exitFullscreen()
            panel != BrowserPanel.NONE -> panel = BrowserPanel.NONE
            editing -> editing = false
            else -> browser.back()
        }
    }

    if (vrMode && activeId != null) {
        VrBrowserView(c, activeId, onExit = { vrMode = false })
        BrowserPrompts(c, nav)
        return
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {
            // Address bar
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    if (ui?.secure == true) Icons.Filled.Lock else Icons.Filled.Warning,
                    contentDescription = if (ui?.secure == true) "Secure connection" else "Not secure",
                    tint = if (ui?.secure == true) Ok else Warn,
                    modifier = Modifier.size(20.dp),
                )
                TextField(
                    value = address,
                    onValueChange = { address = it; inputError = null },
                    singleLine = true,
                    placeholder = { Text("Search or enter address") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
                    keyboardActions = KeyboardActions(onGo = {
                        inputError = browser.submit(address)
                        if (inputError == null) editing = false
                    }),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = MaterialTheme.colorScheme.surface,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                    ),
                    shape = RoundedCornerShape(24.dp),
                    modifier = Modifier.weight(1f).padding(horizontal = 6.dp).onFocusChanged { editing = it.isFocused },
                )
                OutlinedButton(onClick = { panel = BrowserPanel.TABS }, modifier = Modifier.height(40.dp)) { Text("${tabs.tabs.size}") }
                Box {
                    IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, "Browser menu") }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        DropdownMenuItem(text = { Text("New tab") }, onClick = { menu = false; browser.newTab() })
                        DropdownMenuItem(text = { Text("Bookmark this page") }, onClick = {
                            menu = false
                            ui?.takeIf { UrlPolicy.isSecure(it.url) }?.let { u -> scope.launch { c.browserDb.dao().addBookmark(BookmarkEntity(url = u.url, title = u.title.ifBlank { u.url })) } }
                        })
                        DropdownMenuItem(text = { Text("Bookmarks") }, onClick = { menu = false; panel = BrowserPanel.BOOKMARKS })
                        DropdownMenuItem(text = { Text("History") }, onClick = { menu = false; panel = BrowserPanel.HISTORY })
                        DropdownMenuItem(text = { Text("Downloads") }, onClick = { menu = false; panel = BrowserPanel.DOWNLOADS })
                        DropdownMenuItem(text = { Text("Find videos on this page") }, onClick = { menu = false; browser.detectMedia(); panel = BrowserPanel.MEDIA })
                        DropdownMenuItem(text = { Text("VR browser mode") }, onClick = { menu = false; vrMode = true })
                        DropdownMenuItem(text = { Text("Clear browsing data") }, onClick = {
                            menu = false
                            scope.launch { browser.clearBrowsingData() }
                        })
                    }
                }
            }
            inputError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp)) }
            if (ui?.loading == true) LinearProgressIndicator(progress = { (ui.progress / 100f).coerceIn(0.02f, 1f) }, modifier = Modifier.fillMaxWidth().height(2.dp))
            else Box(Modifier.height(2.dp))

            // Page
            Box(Modifier.weight(1f).fillMaxWidth().background(Color.White)) {
                if (activeId != null) WebViewHost(c, activeId)
                ui?.error?.let { err ->
                    Surface(color = MaterialTheme.colorScheme.surface, modifier = Modifier.fillMaxSize()) {
                        Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("Page not shown", style = MaterialTheme.typography.titleLarge)
                            Text(err)
                            OutlinedButton(onClick = { browser.reload() }) { Text("Try again") }
                        }
                    }
                }
                if (ui?.url == UrlPolicy.HOME_URL || ui?.url.isNullOrBlank()) StartPage(c) { url -> browser.load(url) }
                val count = ui?.media?.size ?: 0
                if (count > 0) {
                    ExtendedFloatingActionButton(
                        onClick = { browser.detectMedia(); panel = BrowserPanel.MEDIA },
                        text = { Text(if (count == 1) "1 video" else "$count videos") },
                        icon = { Icon(Icons.Filled.Star, null) },
                        modifier = Modifier.align(Alignment.BottomEnd).padding(16.dp),
                    )
                }
            }

            // Toolbar
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.SpaceAround) {
                IconButton(onClick = browser::back, enabled = ui?.canGoBack == true) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                IconButton(onClick = browser::forward, enabled = ui?.canGoForward == true) { Icon(Icons.AutoMirrored.Filled.ArrowForward, "Forward") }
                IconButton(onClick = { if (ui?.loading == true) browser.stop() else browser.reload() }) {
                    Icon(if (ui?.loading == true) Icons.Filled.Close else Icons.Filled.Refresh, if (ui?.loading == true) "Stop" else "Reload")
                }
                IconButton(onClick = browser::home) { Icon(Icons.Filled.Home, "Home page") }
                OutlinedButton(onClick = { vrMode = true }) { Text("VR") }
            }
        }

        when (panel) {
            BrowserPanel.NONE -> Unit
            BrowserPanel.MEDIA -> MediaPanel(c, nav, ui) { panel = BrowserPanel.NONE }
            else -> BrowserListPanel(c, nav, panel) { panel = BrowserPanel.NONE }
        }

        fullscreen?.let { view ->
            ImmersiveLandscape(keepScreenOn = true)
            AndroidView(
                factory = { ctx -> FrameLayout(ctx).apply { setBackgroundColor(android.graphics.Color.BLACK) } },
                update = { frame ->
                    if (view.parent !== frame) {
                        (view.parent as? ViewGroup)?.removeView(view)
                        frame.removeAllViews()
                        frame.addView(view, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
    BrowserPrompts(c, nav)
}

/** Shows the active tab's WebView; moves it here from wherever it was (e.g. the VR capture). */
@Composable
private fun WebViewHost(c: AppContainer, tabId: Long) {
    AndroidView(
        factory = { ctx -> FrameLayout(ctx) },
        update = { frame ->
            val wv = c.browser.webView(tabId)
            if (wv.parent !== frame) {
                (wv.parent as? ViewGroup)?.removeView(wv)
                frame.removeAllViews()
                frame.addView(wv, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            }
        },
        onRelease = { frame -> frame.removeAllViews() },
        modifier = Modifier.fillMaxSize(),
    )
}

@Composable
private fun StartPage(c: AppContainer, open: (String) -> Unit) {
    val bookmarks by remember { c.browserDb.dao().bookmarks() }.collectAsState(initial = emptyList())
    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("VRVision Browser", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Find videos on the web and open compatible ones in the VR player. Secure (HTTPS) pages only; " +
                    "DRM-protected and login-only videos stay in the page.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (bookmarks.isNotEmpty()) Text("Bookmarks", style = MaterialTheme.typography.titleMedium)
            bookmarks.take(8).forEach { b ->
                OutlinedButton(onClick = { open(b.url) }, modifier = Modifier.fillMaxWidth()) {
                    Text(b.title, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.width(280.dp))
                }
            }
        }
    }
}
