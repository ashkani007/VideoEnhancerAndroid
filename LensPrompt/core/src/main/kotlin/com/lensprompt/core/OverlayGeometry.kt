package com.lensprompt.core

import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/** A floating window rectangle in screen pixels (x, y = top-left). */
data class WindowRect(val x: Int, val y: Int, val width: Int, val height: Int)

/**
 * Size and position rules for the floating teleprompter window. Pure, so the
 * clamping that keeps the window usable and on screen (resize, orientation
 * change, restored layouts) is unit-tested.
 *
 * @param minWidth  smallest usable width (px), enough for the toolbar.
 * @param minHeight smallest usable height (px), toolbar plus about two lines.
 */
class OverlayGeometry(private val minWidth: Int, private val minHeight: Int) {

    /** The window fully on screen and at least the minimum size. */
    fun clamp(r: WindowRect, screenW: Int, screenH: Int): WindowRect {
        val w = r.width.coerceIn(min(minWidth, screenW), screenW)
        val h = r.height.coerceIn(min(minHeight, screenH), screenH)
        val x = r.x.coerceIn(0, screenW - w)
        val y = r.y.coerceIn(0, screenH - h)
        return WindowRect(x, y, w, h)
    }

    /** Resize from the bottom-right corner by (dx, dy), keeping the top-left fixed. */
    fun resize(start: WindowRect, dx: Int, dy: Int, screenW: Int, screenH: Int): WindowRect {
        val maxW = screenW - start.x
        val maxH = screenH - start.y
        val w = (start.width + dx).coerceIn(min(minWidth, maxW), max(maxW, min(minWidth, screenW)))
        val h = (start.height + dy).coerceIn(min(minHeight, maxH), max(maxH, min(minHeight, screenH)))
        return clamp(WindowRect(start.x, start.y, w, h), screenW, screenH)
    }

    /** Move by (dx, dy); the window always stays fully on screen. */
    fun move(start: WindowRect, dx: Int, dy: Int, screenW: Int, screenH: Int): WindowRect =
        clamp(start.copy(x = start.x + dx, y = start.y + dy), screenW, screenH)

    /**
     * After a rotation: keep the window's relative position (its centre as a
     * fraction of the screen) and size, then clamp to the new screen.
     */
    fun reorient(r: WindowRect, oldW: Int, oldH: Int, newW: Int, newH: Int): WindowRect {
        if (oldW <= 0 || oldH <= 0) return clamp(r, newW, newH)
        val cx = (r.x + r.width / 2.0) / oldW
        val cy = (r.y + r.height / 2.0) / oldH
        val w = min(r.width, newW)
        val h = min(r.height, newH)
        val x = (cx * newW - w / 2.0).roundToInt()
        val y = (cy * newH - h / 2.0).roundToInt()
        return clamp(WindowRect(x, y, w, h), newW, newH)
    }

    /** Default band across the upper part of the screen (preview and shutter stay free). */
    fun defaultRect(screenW: Int, screenH: Int, topInset: Int): WindowRect {
        val landscape = screenW > screenH
        val w = (screenW * if (landscape) 0.6 else 0.92).roundToInt()
        val h = (screenH * if (landscape) 0.4 else 0.28).roundToInt()
        return clamp(WindowRect((screenW - w) / 2, topInset, w, h), screenW, screenH)
    }

    /**
     * NEAR CAMERA: a narrow strip of about [lines] text lines just below the
     * top edge, so the eyes stay close to the lens. It is centred by default but
     * the selfie camera is not always centred, so the user drags it into place.
     */
    fun nearCamera(screenW: Int, screenH: Int, topInset: Int, lineHeight: Int, toolbar: Int, lines: Int = 3): WindowRect {
        val landscape = screenW > screenH
        val w = (screenW * if (landscape) 0.42 else 0.7).roundToInt()
        val h = toolbar + (lineHeight * (lines + 0.4)).roundToInt()
        return clamp(WindowRect((screenW - w) / 2, topInset, w, h), screenW, screenH)
    }

    /** Large: most of the screen, for reading without the camera app's preview. */
    fun large(screenW: Int, screenH: Int, topInset: Int): WindowRect {
        val w = (screenW * 0.96).roundToInt()
        val h = ((screenH - topInset) * 0.7).roundToInt()
        return clamp(WindowRect((screenW - w) / 2, topInset, w, h), screenW, screenH)
    }
}
