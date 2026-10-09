package com.vrvision.app.ui.screens

import android.os.SystemClock
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.ViewGroup
import android.webkit.WebView
import android.widget.FrameLayout
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.vrvision.app.AppContainer
import com.vrvision.app.browser.CaptureLayout
import com.vrvision.app.player.HeadTracker
import com.vrvision.app.player.RenderConfig
import com.vrvision.app.player.VrSurface
import com.vrvision.app.ui.components.LabeledSlider
import com.vrvision.app.ui.components.SwitchRow
import com.vrvision.core.browser.ControllerAction
import com.vrvision.core.browser.ControllerMap
import com.vrvision.core.browser.DwellClicker
import com.vrvision.core.browser.VirtualScreen
import com.vrvision.core.browser.VrPointer
import com.vrvision.core.calibration.HeadsetCalibration
import com.vrvision.core.projection.FlatScreenConfig
import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.StereoLayout
import java.util.Locale

private const val CAPTURE_W = 1280
private const val CAPTURE_H = 720

/** Sends a tap to the WebView at page-normalized coordinates. */
fun tapWebView(wv: WebView, u: Float, v: Float) {
    val x = u * wv.width; val y = v * wv.height
    val t = SystemClock.uptimeMillis()
    MotionEvent.obtain(t, t, MotionEvent.ACTION_DOWN, x, y, 0).also { wv.dispatchTouchEvent(it); it.recycle() }
    MotionEvent.obtain(t, t + 60, MotionEvent.ACTION_UP, x, y, 0).also { wv.dispatchTouchEvent(it); it.recycle() }
}

/**
 * The page rendered on a virtual screen through the stereo VR renderer (per-eye views, lens
 * pre-distortion, the active calibration profile, head tracking). Selection: gaze reticle with
 * dwell-to-click, a tap anywhere on the phone screen (headset button) clicks at the reticle, and
 * Bluetooth controllers/keyboards map to click, back, scroll and recenter.
 */
@Composable
fun VrBrowserView(c: AppContainer, tabId: Long, onExit: () -> Unit) {
    val context = LocalContext.current
    val prefs by c.settings.state.collectAsState()
    val tracker = remember { HeadTracker(context) }
    val capture = remember { CaptureLayout(context, CAPTURE_W, CAPTURE_H) }
    val dwell = remember { DwellClicker() }
    var calibration by remember { mutableStateOf(HeadsetCalibration()) }
    var screen by remember { mutableStateOf(VirtualScreen(c.settings.vrScreenDistance, c.settings.vrScreenWidth, CAPTURE_W.toFloat() / CAPTURE_H).validated()) }
    var dwellOn by remember { mutableStateOf(c.settings.dwellClick) }
    var progress by remember { mutableFloatStateOf(0f) }
    var panel by remember { mutableStateOf(false) }
    val wv = remember(tabId) { c.browser.webView(tabId) }

    ImmersiveLandscape(keepScreenOn = true)
    LaunchedEffect(Unit) { calibration = c.profiles.active() }

    // Move the tab's WebView into the offscreen capture layout while in VR.
    DisposableEffect(wv) {
        (wv.parent as? ViewGroup)?.removeView(wv)
        capture.addView(wv, FrameLayout.LayoutParams(CAPTURE_W, CAPTURE_H))
        onDispose {
            capture.removeView(wv)
            capture.surface = null
        }
    }

    fun clickAtGaze() {
        VrPointer.hit(tracker.orientation(), screen)?.let { (u, v) -> tapWebView(wv, u, v) }
    }

    // Gaze dwell loop, once per display frame.
    LaunchedEffect(dwellOn, screen, panel) {
        dwell.reset(); progress = 0f
        if (!dwellOn || panel) return@LaunchedEffect
        while (true) {
            withFrameMillis { now ->
                val hit = VrPointer.hit(tracker.orientation(), screen)
                dwell.update(hit, now)?.let { (u, v) -> tapWebView(wv, u, v) }
                progress = dwell.progress
            }
        }
    }

    // Bluetooth controller / keyboard input.
    DisposableEffect(Unit) {
        c.keyHandler = { e: KeyEvent ->
            val action = ControllerMap.action(e.keyCode)
            if (action == null || e.action != KeyEvent.ACTION_DOWN) action != null
            else {
                when (action) {
                    ControllerAction.CLICK -> clickAtGaze()
                    ControllerAction.BACK -> when {
                        panel -> panel = false
                        wv.canGoBack() -> wv.goBack()
                        else -> panel = true
                    }
                    ControllerAction.SCROLL_UP -> c.browser.scrollBy(0, -300)
                    ControllerAction.SCROLL_DOWN -> c.browser.scrollBy(0, 300)
                    ControllerAction.SCROLL_LEFT -> c.browser.scrollBy(-300, 0)
                    ControllerAction.SCROLL_RIGHT -> c.browser.scrollBy(300, 0)
                    ControllerAction.RECENTER -> tracker.recenter()
                    ControllerAction.TOGGLE_DWELL -> dwellOn = !dwellOn
                    ControllerAction.PLAY_PAUSE -> wv.evaluateJavascript("(function(){var v=document.querySelector('video');if(v){v.paused?v.play():v.pause();}})();", null)
                }
                true
            }
        }
        onDispose { c.keyHandler = null }
    }
    BackHandler { panel = !panel }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        // Attached but invisible: draws only into the VR surface.
        AndroidView(factory = { capture }, modifier = Modifier.fillMaxSize())
        VrSurface(
            config = RenderConfig(
                layout = StereoLayout.MONO, projection = ProjectionType.FLAT,
                flatScreen = FlatScreenConfig(screen.distanceMeters, screen.widthMeters),
                calibration = calibration, headsetMode = true,
                reticle = !panel, reticleProgress = progress,
            ),
            videoSize = CAPTURE_W to CAPTURE_H,
            tracker = tracker,
            respectCutout = prefs.respectCutout,
            modifier = Modifier.fillMaxSize(),
            onSurface = { capture.surface = it },
            onTap = { if (!panel) clickAtGaze() },
            onDoubleTap = { panel = !panel },
            sourceBufferSize = CAPTURE_W to CAPTURE_H,
        )
        if (panel) {
            Column(
                Modifier.align(Alignment.CenterEnd).fillMaxHeight().width(400.dp).background(Color(0xEE0E1116))
                    .verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("VR browser", style = MaterialTheme.typography.titleLarge)
                Text(
                    "Look at a link and hold still to click, or press the headset button / controller A. " +
                        "B or back = page back, D-pad = scroll, Y = recenter, X = toggle dwell. " +
                        "Type text in normal mode or with a Bluetooth keyboard.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
                )
                LabeledSlider("Screen distance (m)", screen.distanceMeters, VirtualScreen.MIN_DISTANCE..VirtualScreen.MAX_DISTANCE, {
                    screen = screen.copy(distanceMeters = it).validated(); c.settings.vrScreenDistance = screen.distanceMeters
                }) { String.format(Locale.US, "%.1f", it) }
                LabeledSlider("Screen width (m)", screen.widthMeters, VirtualScreen.MIN_WIDTH..VirtualScreen.MAX_WIDTH, {
                    screen = screen.copy(widthMeters = it).validated(); c.settings.vrScreenWidth = screen.widthMeters
                }) { String.format(Locale.US, "%.1f", it) }
                SwitchRow("Dwell to click", dwellOn, { dwellOn = it; c.settings.dwellClick = it })
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { tracker.recenter() }) { Text("Recenter") }
                    OutlinedButton(onClick = { if (wv.canGoBack()) wv.goBack() }) { Text("Page back") }
                }
                Text("Lens profile: ${calibration.name} (change it under Headset)", style = MaterialTheme.typography.bodyMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { panel = false }) { Text("Resume") }
                    OutlinedButton(onClick = onExit) { Text("Exit VR") }
                }
            }
        }
    }
}
