package com.vrvision.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
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
import com.vrvision.app.ui.theme.VRVisionTheme

/** App destinations. A simple back stack keeps navigation explicit and dependency-free. */
sealed interface Dest {
    data object Library : Dest
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
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val container = (application as VRVisionApp).container
        setContent {
            VRVisionTheme {
                val stack = remember { mutableStateListOf<Dest>(Dest.Library) }
                val nav = remember { Navigator(stack) }
                BackHandler(enabled = stack.size > 1) { nav.back() }
                Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
                    Route(stack.last(), nav, container)
                }
            }
        }
    }
}

@Composable
private fun Route(dest: Dest, nav: Navigator, c: AppContainer) {
    when (dest) {
        Dest.Library -> LibraryScreen(c, nav)
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
