package com.vrvision.core.browser

import com.vrvision.core.math.Quaternion
import com.vrvision.core.math.Vec3
import kotlin.math.hypot

/**
 * The virtual browser screen: a flat panel centered straight ahead (−Z) at [distanceMeters],
 * [widthMeters] wide, with the page's aspect ratio. Rendered through the same per-eye,
 * lens-corrected pipeline as flat videos.
 */
data class VirtualScreen(val distanceMeters: Float = 2.0f, val widthMeters: Float = 2.4f, val aspect: Float = 16f / 9f) {
    fun validated() = VirtualScreen(
        distanceMeters.coerceIn(MIN_DISTANCE, MAX_DISTANCE),
        widthMeters.coerceIn(MIN_WIDTH, MAX_WIDTH),
        aspect.coerceIn(0.5f, 3f),
    )
    val heightMeters: Float get() = widthMeters / aspect

    companion object {
        const val MIN_DISTANCE = 1.0f
        const val MAX_DISTANCE = 6.0f
        const val MIN_WIDTH = 0.8f
        const val MAX_WIDTH = 6.0f
    }
}

object VrPointer {
    /**
     * Where the gaze ray (camera forward) hits the screen, as page coordinates (0,0 top-left …
     * 1,1 bottom-right), or null when looking away from the screen.
     */
    fun hit(camera: Quaternion, screen: VirtualScreen): Pair<Float, Float>? {
        val s = screen.validated()
        val d: Vec3 = camera.rotate(Vec3(0f, 0f, -1f))
        if (d.z >= -1e-4f) return null // facing away from the screen plane
        val t = -s.distanceMeters / d.z
        val x = d.x * t; val y = d.y * t
        val u = x / s.widthMeters + 0.5f
        val v = 0.5f - y / s.heightMeters
        return if (u in 0f..1f && v in 0f..1f) Pair(u, v) else null
    }
}

/**
 * Gaze "dwell" selection: holding the pointer still for [dwellMs] produces one click, then
 * requires the pointer to move away before it can click again (no repeated clicks).
 */
class DwellClicker(private val dwellMs: Long = 1500, private val radius: Float = 0.015f) {
    private var anchor: Pair<Float, Float>? = null
    private var since = 0L
    private var fired = false

    /** Progress 0..1 of the current dwell (for drawing a ring), updated by [update]. */
    var progress = 0f
        private set

    /** Returns the click position when a dwell completes. */
    fun update(p: Pair<Float, Float>?, nowMs: Long): Pair<Float, Float>? {
        val a = anchor
        if (p == null) { reset(); return null }
        if (a == null || hypot(p.first - a.first, p.second - a.second) > radius) {
            anchor = p; since = nowMs; fired = false; progress = 0f
            return null
        }
        if (fired) return null
        progress = ((nowMs - since).toFloat() / dwellMs).coerceIn(0f, 1f)
        if (nowMs - since >= dwellMs) { fired = true; progress = 1f; return a }
        return null
    }

    fun reset() { anchor = null; fired = false; progress = 0f }
}

enum class ControllerAction { CLICK, BACK, SCROLL_UP, SCROLL_DOWN, SCROLL_LEFT, SCROLL_RIGHT, RECENTER, TOGGLE_DWELL, PLAY_PAUSE }

/**
 * Bluetooth gamepad / remote / keyboard mapping. Values are android.view.KeyEvent key codes
 * (duplicated here so the mapping is testable on the JVM).
 */
object ControllerMap {
    const val KEYCODE_BACK = 4
    const val KEYCODE_DPAD_UP = 19
    const val KEYCODE_DPAD_DOWN = 20
    const val KEYCODE_DPAD_LEFT = 21
    const val KEYCODE_DPAD_RIGHT = 22
    const val KEYCODE_DPAD_CENTER = 23
    const val KEYCODE_SPACE = 62
    const val KEYCODE_ENTER = 66
    const val KEYCODE_MEDIA_PLAY_PAUSE = 85
    const val KEYCODE_PAGE_UP = 92
    const val KEYCODE_PAGE_DOWN = 93
    const val KEYCODE_BUTTON_A = 96
    const val KEYCODE_BUTTON_B = 97
    const val KEYCODE_BUTTON_X = 99
    const val KEYCODE_BUTTON_Y = 100
    const val KEYCODE_BUTTON_START = 108
    const val KEYCODE_ESCAPE = 111

    fun action(keyCode: Int): ControllerAction? = when (keyCode) {
        KEYCODE_DPAD_CENTER, KEYCODE_ENTER, KEYCODE_BUTTON_A -> ControllerAction.CLICK
        KEYCODE_BACK, KEYCODE_BUTTON_B, KEYCODE_ESCAPE -> ControllerAction.BACK
        KEYCODE_DPAD_UP, KEYCODE_PAGE_UP -> ControllerAction.SCROLL_UP
        KEYCODE_DPAD_DOWN, KEYCODE_PAGE_DOWN -> ControllerAction.SCROLL_DOWN
        KEYCODE_DPAD_LEFT -> ControllerAction.SCROLL_LEFT
        KEYCODE_DPAD_RIGHT -> ControllerAction.SCROLL_RIGHT
        KEYCODE_BUTTON_Y -> ControllerAction.RECENTER
        KEYCODE_BUTTON_X -> ControllerAction.TOGGLE_DWELL
        KEYCODE_MEDIA_PLAY_PAUSE, KEYCODE_SPACE, KEYCODE_BUTTON_START -> ControllerAction.PLAY_PAUSE
        else -> null
    }
}
