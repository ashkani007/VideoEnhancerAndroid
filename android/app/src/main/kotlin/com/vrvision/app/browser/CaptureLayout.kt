package com.vrvision.app.browser

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.view.Choreographer
import android.view.Surface
import android.view.View
import android.widget.FrameLayout

/**
 * Hosts the WebView at a fixed resolution and draws it into [surface] (the VR renderer's
 * SurfaceTexture) instead of onto the screen. The VR renderer then shows the page as a
 * virtual screen with per-eye rendering and lens pre-distortion. The layout stays attached
 * to the window so the WebView keeps rendering and receives dispatched touch events.
 */
class CaptureLayout(context: Context, val captureWidth: Int, val captureHeight: Int) : FrameLayout(context) {

    @Volatile var surface: Surface? = null

    private val frame = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            // Pages animate and play video; refresh every vsync while attached.
            invalidate()
            if (isAttachedToWindow) Choreographer.getInstance().postFrameCallback(this)
        }
    }

    init {
        setWillNotDraw(false)
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        super.onMeasure(
            MeasureSpec.makeMeasureSpec(captureWidth, MeasureSpec.EXACTLY),
            MeasureSpec.makeMeasureSpec(captureHeight, MeasureSpec.EXACTLY),
        )
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        Choreographer.getInstance().postFrameCallback(frame)
    }

    override fun onDetachedFromWindow() {
        Choreographer.getInstance().removeFrameCallback(frame)
        super.onDetachedFromWindow()
    }

    override fun draw(canvas: Canvas) {
        // Nothing is drawn on screen; the content goes only to the VR surface.
        val s = surface ?: return
        if (!s.isValid) return
        val c = try { s.lockHardwareCanvas() } catch (_: Exception) { return }
        try {
            c.drawColor(Color.WHITE)
            super.draw(c)
        } finally {
            s.unlockCanvasAndPost(c)
        }
    }

    override fun onDescendantInvalidated(child: View, target: View) {
        super.onDescendantInvalidated(child, target)
        invalidate()
    }
}
