package com.vrvision.app.ui.screens

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.ActivityInfo
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.vrvision.app.AppContainer
import com.vrvision.app.Navigator
import com.vrvision.app.data.toFormat
import com.vrvision.app.player.HeadTracker
import com.vrvision.app.player.PlayerController
import com.vrvision.app.player.RenderConfig
import com.vrvision.app.player.TestPattern
import com.vrvision.app.player.VrSurface
import com.vrvision.app.ui.components.formatDuration
import com.vrvision.core.calibration.HeadsetCalibration
import com.vrvision.core.media.PlaybackErrorClassifier
import com.vrvision.core.media.PlaybackPhase
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

fun Context.findActivity(): Activity? {
    var c: Context? = this
    while (c is ContextWrapper) { if (c is Activity) return c; c = c.baseContext }
    return null
}

/** Landscape, immersive, keeps the screen on only while playing. Restores everything on exit. */
@Composable
fun ImmersiveLandscape(keepScreenOn: Boolean) {
    val view = LocalView.current
    val activity = LocalContext.current.findActivity()
    DisposableEffect(activity) {
        val previous = activity?.requestedOrientation
        activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        val controller = activity?.window?.let { WindowCompat.getInsetsController(it, view) }
        controller?.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller?.hide(WindowInsetsCompat.Type.systemBars())
        onDispose {
            controller?.show(WindowInsetsCompat.Type.systemBars())
            activity?.requestedOrientation = previous ?: ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
            view.keepScreenOn = false
        }
    }
    LaunchedEffect(keepScreenOn) { view.keepScreenOn = keepScreenOn }
}

@Composable
fun PlayerScreen(c: AppContainer, nav: Navigator, videoId: Long) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs by c.settings.state.collectAsState()
    val video by c.videos.observe(videoId).collectAsState(initial = null)
    val player = remember { PlayerController(context, scope) }
    val tracker = remember { HeadTracker(context) }
    val state by player.state.collectAsState()
    val cues by player.cues.collectAsState()
    val videoSize by player.videoSize.collectAsState()
    var calibration by remember { mutableStateOf(HeadsetCalibration()) }
    var headsetMode by remember { mutableStateOf(prefs.headsetModeDefault) }
    var pattern by remember { mutableStateOf(TestPattern.NONE) }
    var controlsVisible by remember { mutableStateOf(true) }
    var interaction by remember { mutableIntStateOf(0) }
    var loaded by remember { mutableStateOf(false) }
    var seeking by remember { mutableStateOf<Float?>(null) }
    var volume by remember { mutableFloatStateOf(1f) }

    LaunchedEffect(Unit) { calibration = c.profiles.active() }
    LaunchedEffect(prefs.useHeadTracking) { tracker.enabled = prefs.useHeadTracking }
    LaunchedEffect(video?.id) {
        val v = video ?: return@LaunchedEffect
        if (!loaded) { player.load(Uri.parse(v.uri), v.lastPositionMs); loaded = true }
    }
    // Auto-hide controls 4 s after the last interaction while playing.
    LaunchedEffect(controlsVisible, interaction, state.isPlaying) {
        if (controlsVisible && state.isPlaying) { delay(4000); controlsVisible = false }
    }
    DisposableEffect(Unit) {
        onDispose {
            val pos = player.currentPositionMs()
            scope.launch { c.videos.savePosition(videoId, pos) }
            player.release()
        }
    }
    ImmersiveLandscape(keepScreenOn = state.keepScreenOn)

    val format = video?.toFormat()
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (format != null) {
            VrSurface(
                config = RenderConfig(
                    layout = format.layout, packing = format.packing, projection = format.projection,
                    swapEyes = format.swapEyes, calibration = calibration, headsetMode = headsetMode, pattern = pattern,
                ),
                videoSize = videoSize,
                tracker = tracker,
                respectCutout = prefs.respectCutout,
                modifier = Modifier.fillMaxSize(),
                onSurface = { player.setSurface(it) },
                onTap = { controlsVisible = !controlsVisible; interaction++ },
                onDoubleTap = { tracker.recenter() },
            )
        }

        // Subtitles: drawn once per eye so they are readable in the headset.
        if (cues.isNotBlank() && state.subtitlesEnabled) {
            Row(Modifier.fillMaxSize().padding(bottom = 48.dp), verticalAlignment = Alignment.Bottom) {
                repeat(if (headsetMode) 2 else 1) {
                    Box(Modifier.weight(1f), contentAlignment = Alignment.BottomCenter) {
                        Text(
                            cues, color = Color.White, fontSize = if (headsetMode) 14.sp else 20.sp, textAlign = TextAlign.Center,
                            modifier = Modifier.background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 4.dp),
                        )
                    }
                }
            }
        }

        (state.phase as? PlaybackPhase.Failed)?.let { failed ->
            Column(
                Modifier.align(Alignment.Center).background(Color(0xE0161B22), RoundedCornerShape(16.dp)).padding(24.dp).width(420.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("Can't play this video", style = MaterialTheme.typography.titleLarge)
                Text(PlaybackErrorClassifier.userMessage(failed.kind))
                Text(failed.detail, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                Button(onClick = nav::back) { Text("Back to library") }
            }
        }

        if (controlsVisible && state.phase !is PlaybackPhase.Failed) {
            Column(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth()
                    .background(Color(0xC0000000)).padding(horizontal = 24.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(formatDuration(seeking?.toLong() ?: state.positionMs), color = Color.White)
                    Slider(
                        value = (seeking ?: state.positionMs.toFloat()).coerceIn(0f, state.durationMs.coerceAtLeast(1).toFloat()),
                        onValueChange = { seeking = it; interaction++ },
                        onValueChangeFinished = { seeking?.let { player.seekTo(it.toLong()) }; seeking = null },
                        valueRange = 0f..state.durationMs.coerceAtLeast(1).toFloat(),
                        enabled = state.canControl,
                        modifier = Modifier.weight(1f).padding(horizontal = 12.dp),
                    )
                    Text(formatDuration(state.durationMs), color = Color.White)
                }
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    BigButton("Back") { nav.back() }
                    BigButton("−10 s") { player.seekBy(-10_000); interaction++ }
                    Button(onClick = { player.togglePlay(); interaction++ }, modifier = Modifier.height(64.dp).width(120.dp)) {
                        Text(if (state.playWhenReady && state.phase != PlaybackPhase.Ended) "Pause" else "Play", fontSize = 18.sp)
                    }
                    BigButton("+10 s") { player.seekBy(10_000); interaction++ }
                    BigButton("Recenter") { tracker.recenter(); interaction++ }
                    BigButton(if (headsetMode) "Phone view" else "Headset view") { headsetMode = !headsetMode; interaction++ }
                    BigButton(when (pattern) { TestPattern.NONE -> "Grid"; TestPattern.GRID -> "Checker"; TestPattern.CHECKERBOARD -> "Video" }) {
                        pattern = TestPattern.entries[(pattern.ordinal + 1) % TestPattern.entries.size]; interaction++
                    }
                    if (state.subtitlesAvailable) BigButton(if (state.subtitlesEnabled) "Subs off" else "Subs on") {
                        player.setSubtitles(!state.subtitlesEnabled); interaction++
                    }
                    Column(Modifier.width(160.dp)) {
                        Text("Volume", color = Color.White, style = MaterialTheme.typography.bodyMedium)
                        Slider(value = volume, onValueChange = { volume = it; player.setVolume(it); interaction++ })
                    }
                }
                if (!tracker.hasSensor) Text("No rotation sensor: drag to look around.", color = Color.White)
                Text(
                    "Tap to show/hide controls · double-tap to recenter · drag to look around",
                    color = Color(0xFF9DA9B5), style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun BigButton(text: String, onClick: () -> Unit) {
    FilledTonalButton(onClick = onClick, modifier = Modifier.height(64.dp)) { Text(text, fontSize = 16.sp) }
}
