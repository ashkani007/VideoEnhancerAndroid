package com.vrvision.app

import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.material3.MaterialTheme
import com.vrvision.app.ui.screens.CalibrationScreen
import com.vrvision.app.ui.screens.LibraryScreen
import com.vrvision.app.ui.screens.PlayerScreen
import com.vrvision.app.ui.screens.SettingsScreen
import com.vrvision.app.ui.screens.VideoInfoScreen
import com.vrvision.app.ui.screens.EnhanceSettingsScreen
import com.vrvision.app.ui.screens.RecommendationScreen
import com.vrvision.app.ui.screens.CloudConsentScreen
import com.vrvision.app.ui.screens.ProgressScreen
import com.vrvision.app.ui.screens.CompareScreen
import com.vrvision.app.ui.screens.BrowserScreen
import com.vrvision.app.ui.screens.EnhanceHubScreen
import com.vrvision.app.ui.screens.HomeScreen
import com.vrvision.app.ui.screens.StreamPlayerScreen
import com.vrvision.app.ui.theme.VRVisionTheme
import com.vrvision.core.media.VideoFormat

/** App destinations. A simple back stack keeps navigation explicit and dependency-free. */
sealed interface Dest {
    data object Home : Dest
    data object Library : Dest
    data object Browser : Dest
    data object EnhanceHub : Dest
    /** A network video handed off from the browser. */
    data class StreamPlayer(val url: String, val mime: String?, val format: VideoFormat) : Dest
    data class VideoInfo(val videoId: Long) : Dest
    data class Player(val videoId: Long) : Dest
    data object Calibration : Dest
    data object Settings : Dest
    data class EnhanceSettings(val videoId: Long) : Dest
    data class Recommendation(val videoId: Long) : Dest
    data class CloudConsent(val videoId: Long) : Dest
    data class Progress(val jobId: Long) : Dest
    data class Compare(val jobId: Long) : Dest
}

class Navigator(private val stack: MutableList<Dest>) {
    val current: Dest get() = stack.last()
    val canGoBack: Boolean get() = stack.size > 1
    fun go(d: Dest) { stack.add(d) }
    fun replace(d: Dest) { stack.removeAt(stack.lastIndex); stack.add(d) }
    fun back() { if (canGoBack) stack.removeAt(stack.lastIndex) }
    fun home() { while (stack.size > 1) stack.removeAt(stack.lastIndex) }
    /** Bottom-bar destinations each start their own stack. */
    fun switchRoot(d: Dest) { stack.clear(); stack.add(d) }
    val root: Dest get() = stack.first()
}

private val rootDestinations = listOf(Dest.Home, Dest.Library, Dest.Browser, Dest.EnhanceHub, Dest.Settings)

class MainActivity : ComponentActivity() {
    private val container get() = (application as VRVisionApp).container

    /** Bluetooth controllers/keyboards go to the screen that registered for them (VR browser). */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean =
        container.keyHandler?.invoke(event) == true || super.dispatchKeyEvent(event)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VRVisionTheme {
                val stack = remember { mutableStateListOf<Dest>(Dest.Home) }
                val nav = remember { Navigator(stack) }
                BackHandler(enabled = stack.size > 1) { nav.back() }
                Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
                    Box(Modifier.weight(1f).fillMaxWidth()) { Route(stack.last(), nav, container) }
                    if (stack.size == 1) BottomBar(nav)
                }
            }
        }
    }
}

@Composable
private fun BottomBar(nav: Navigator) {
    NavigationBar(modifier = Modifier.navigationBarsPadding()) {
        rootDestinations.forEach { d ->
            val (label, icon) = when (d) {
                Dest.Home -> "Home" to Icons.Filled.Home
                Dest.Library -> "Library" to Icons.AutoMirrored.Filled.List
                Dest.Browser -> "Browser" to Icons.Filled.Search
                Dest.EnhanceHub -> "Enhance" to Icons.Filled.Build
                else -> "Settings" to Icons.Filled.Settings
            }
            NavigationBarItem(
                selected = nav.root == d,
                onClick = { if (nav.root != d) nav.switchRoot(d) },
                icon = { Icon(icon, contentDescription = label) },
                label = { Text(label) },
            )
        }
    }
}

@Composable
private fun Route(dest: Dest, nav: Navigator, c: AppContainer) {
    when (dest) {
        Dest.Home -> HomeScreen(c, nav)
        Dest.Library -> LibraryScreen(c, nav)
        Dest.Browser -> BrowserScreen(c, nav)
        Dest.EnhanceHub -> EnhanceHubScreen(c, nav)
        is Dest.StreamPlayer -> StreamPlayerScreen(c, nav, dest.url, dest.mime, dest.format)
        is Dest.VideoInfo -> VideoInfoScreen(c, nav, dest.videoId)
        is Dest.Player -> PlayerScreen(c, nav, dest.videoId)
        Dest.Calibration -> CalibrationScreen(c, nav)
        Dest.Settings -> SettingsScreen(c, nav)
        is Dest.EnhanceSettings -> EnhanceSettingsScreen(c, nav, dest.videoId)
        is Dest.Recommendation -> RecommendationScreen(c, nav, dest.videoId)
        is Dest.CloudConsent -> CloudConsentScreen(c, nav, dest.videoId)
        is Dest.Progress -> ProgressScreen(c, nav, dest.jobId)
        is Dest.Compare -> CompareScreen(c, nav, dest.jobId)
    }
}
