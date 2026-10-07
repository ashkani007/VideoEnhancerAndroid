package com.lensprompt.app.overlay

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.text.Layout
import android.text.StaticLayout
import android.text.TextDirectionHeuristics
import android.text.TextPaint
import android.util.TypedValue
import android.view.View
import kotlin.math.roundToInt

/**
 * The floating teleprompter's script area: a real viewport.
 *
 * The whole script is laid out once per width / font / spacing / alignment
 * (a [StaticLayout] wrapped to the current width), and only the part inside
 * this view's bounds is drawn — the text can never render outside the window.
 * Scrolling is a draw offset ([scrollPx]), so Smart Follow and manual scrolling
 * move the text inside the viewport without re-measuring anything.
 *
 * [onReflow] fires after every re-layout so the owner can rebuild its
 * token → y mapping and keep the same reading position.
 */
class ScriptViewport(context: Context) : View(context) {

    private val paint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        setShadowLayer(4f, 0f, 1f, Color.BLACK)
    }
    private val markerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(150, 76, 217, 100) }
    private val padH = dp(12f)

    var text: CharSequence = ""
        set(v) { if (field != v) { field = v; reflow() } }

    var textSizeSp: Float = 28f
        set(v) {
            if (field == v) return
            field = v
            paint.textSize = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, v, resources.displayMetrics)
            reflow()
        }

    var lineSpacing: Float = 1.25f
        set(v) { if (field != v) { field = v; reflow() } }

    var alignCenter: Boolean = false
        set(v) { if (field != v) { field = v; reflow() } }

    var mirror: Boolean = false
        set(v) { if (field != v) { field = v; invalidate() } }

    /** 0..1 */
    var textOpacity: Float = 1f
        set(v) {
            field = v.coerceIn(0f, 1f)
            paint.alpha = (field * 255).roundToInt()
            invalidate()
        }

    /** Reading line position from the top of the viewport (0..1). */
    var anchorFraction: Float = 0.3f
        set(v) { field = v; invalidate() }

    /** Layout y (px) that sits on the reading line. */
    var scrollPx: Float = 0f
        set(v) { if (field != v) { field = v; invalidate() } }

    var onReflow: (() -> Unit)? = null

    var textLayout: StaticLayout? = null
        private set

    init {
        paint.textSize = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, textSizeSp, resources.displayMetrics)
    }

    /** Height of one text line in px (for presets and the reading marker). */
    val lineHeightPx: Int
        get() = textLayout?.takeIf { it.lineCount > 0 }?.let { it.getLineBottom(0) - it.getLineTop(0) }
            ?: (paint.fontMetricsInt.let { it.descent - it.ascent } * lineSpacing).roundToInt()

    fun anchorY(): Float = height * anchorFraction

    private fun reflow() {
        val w = width - 2 * padH
        if (w <= 0) { textLayout = null; invalidate(); return }
        textLayout = StaticLayout.Builder.obtain(text, 0, text.length, paint, w)
            .setAlignment(if (alignCenter) Layout.Alignment.ALIGN_CENTER else Layout.Alignment.ALIGN_NORMAL)
            .setTextDirection(TextDirectionHeuristics.FIRSTSTRONG_LTR) // Persian/RTL lines align right
            .setLineSpacing(0f, lineSpacing)
            .setIncludePad(false)
            .build()
        onReflow?.invoke()
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        if (w != oldw || textLayout == null) reflow() else invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        val l = textLayout ?: return
        val lh = lineHeightPx
        val top = anchorY() - lh / 2f - scrollPx
        canvas.save()
        canvas.clipRect(0, 0, width, height) // never outside the viewport
        if (mirror) canvas.scale(-1f, 1f, width / 2f, 0f)
        canvas.translate(padH.toFloat(), top)
        // Draw only the visible lines.
        val first = l.getLineForVertical((-top).toInt().coerceAtLeast(0))
        val last = l.getLineForVertical((height - top).toInt().coerceAtLeast(0))
        canvas.clipRect(-padH.toFloat(), l.getLineTop(first).toFloat(), (width - padH).toFloat(), l.getLineBottom(last).toFloat())
        l.draw(canvas)
        canvas.restore()
        // Reading marker on the leading edge.
        val ay = anchorY()
        canvas.drawRoundRect(0f, ay - lh / 2f, dp(3f).toFloat(), ay + lh / 2f, 2f, 2f, markerPaint)
    }

    private fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics).toInt()
}

/** Bottom-right resize handle: a clearly visible corner grip (diagonal lines on a dark disc). */
class ResizeGrip(context: Context) : View(context) {
    private val bg = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(140, 0, 0, 0) }
    private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        strokeWidth = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 2f, resources.displayMetrics)
        strokeCap = Paint.Cap.ROUND
    }

    override fun onDraw(canvas: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()
        canvas.drawCircle(w, h, minOf(w, h), bg) // quarter disc in the corner
        val step = minOf(w, h) / 4f
        for (i in 1..3) {
            val d = step * i
            canvas.drawLine(w - d, h - step * 0.6f, w - step * 0.6f, h - d, line)
        }
    }
}
