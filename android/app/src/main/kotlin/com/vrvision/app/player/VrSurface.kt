package com.vrvision.app.player

import android.annotation.SuppressLint
import android.opengl.GLSurfaceView
import android.view.MotionEvent
import android.view.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.vrvision.core.tracking.DisplayRotation
import kotlin.math.max

/**
 * Hosts the stereo renderer. [config] is pushed to the GL thread on every recomposition;
 * [onSurface] receives the decoder output surface once the GL context exists.
 */
@SuppressLint("ClickableViewAccessibility")
@Composable
fun VrSurface(
    config: RenderConfig,
    videoSize: Pair<Int, Int>,
    tracker: HeadTracker,
    respectCutout: Boolean,
    modifier: Modifier = Modifier,
    onSurface: (Surface) -> Unit = {},
    onTap: () -> Unit = {},
    onDoubleTap: () -> Unit = {},
    sourceBufferSize: Pair<Int, Int>? = null,
) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val metrics = context.resources.displayMetrics
    val holder = remember { arrayOfNulls<VrRenderer>(1) }
    val cutoutInset = remember { intArrayOf(0) }

    val view = remember {
        GLSurfaceView(context).apply {
            setEGLContextClientVersion(3)
            preserveEGLContextOnPause = true
            val renderer = VrRenderer(
                onSurfaceReady = { s -> post { onSurface(s) } },
                orientation = { tracker.orientation() },
                sourceBufferSize = sourceBufferSize,
            )
            holder[0] = renderer
            setRenderer(renderer)
            renderMode = GLSurfaceView.RENDERMODE_CONTINUOUSLY

            ViewCompat.setOnApplyWindowInsetsListener(this) { _, insets ->
                val c = insets.getInsets(WindowInsetsCompat.Type.displayCutout())
                cutoutInset[0] = max(c.left, c.right)
                insets
            }

            var lastX = 0f; var lastY = 0f; var downTime = 0L; var lastTap = 0L; var moved = false
            setOnTouchListener { v, e ->
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { lastX = e.x; lastY = e.y; downTime = e.eventTime; moved = false }
                    MotionEvent.ACTION_MOVE -> {
                        val dx = e.x - lastX; val dy = e.y - lastY
                        if (kotlin.math.abs(dx) + kotlin.math.abs(dy) > 4f) moved = true
                        // Drag to look around (useful without a headset); 1 screen width ≈ 180°.
                        tracker.drag(dx / v.width * Math.PI.toFloat(), dy / v.height * Math.PI.toFloat() / 2f)
                        lastX = e.x; lastY = e.y
                    }
                    MotionEvent.ACTION_UP -> if (!moved && e.eventTime - downTime < 300) {
                        if (e.eventTime - lastTap < 300) { onDoubleTap(); lastTap = 0 } else { onTap(); lastTap = e.eventTime }
                    }
                }
                true
            }
        }
    }

    LaunchedEffect(config, videoSize, respectCutout) {
        val r = holder[0] ?: return@LaunchedEffect
        r.videoWidth = videoSize.first
        r.videoHeight = videoSize.second
        r.config = config.copy(
            xdpi = metrics.xdpi,
            ydpi = metrics.ydpi,
            horizontalInsetPx = if (respectCutout) cutoutInset[0] else 0,
        )
    }

    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> {
                    @Suppress("DEPRECATION")
                    tracker.displayRotation = DisplayRotation.fromSurface(view.display?.rotation ?: Surface.ROTATION_90)
                    tracker.start(); view.onResume()
                }
                Lifecycle.Event.ON_PAUSE -> { tracker.stop(); view.onPause() }
                else -> Unit
            }
        }
        lifecycle.addObserver(observer)
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) { tracker.start(); view.onResume() }
        onDispose {
            lifecycle.removeObserver(observer)
            tracker.stop()
            view.queueEvent { holder[0]?.release() }
            view.onPause()
        }
    }

    AndroidView(
        factory = { view },
        modifier = modifier,
        update = {
            tracker.displayRotation = DisplayRotation.fromSurface(it.display?.rotation ?: Surface.ROTATION_90)
        },
    )
}
