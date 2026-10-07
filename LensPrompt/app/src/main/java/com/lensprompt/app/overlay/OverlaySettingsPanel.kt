package com.lensprompt.app.overlay

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.Switch
import android.widget.TextView
import kotlin.math.roundToInt

/**
 * The floating teleprompter's settings, shown in their own small overlay
 * window so they can be changed while the camera app stays open. Every
 * control applies live through [Callbacks]; nothing needs a "save".
 */
class OverlaySettingsPanel(private val context: Context, private val cb: Callbacks) {

    /** Current values the panel starts from. */
    data class Values(
        val fontSp: Float,
        val lineSpacing: Float,
        val backgroundOpacity: Float,
        val textOpacity: Float,
        val width: Int,
        val height: Int,
        val minWidth: Int,
        val minHeight: Int,
        val maxWidth: Int,
        val maxHeight: Int,
        val manualSpeed: Float,
        val smartFollow: Boolean,
        val alignCenter: Boolean,
        val mirror: Boolean,
        val locked: Boolean,
        val autoHide: Boolean,
    )

    interface Callbacks {
        fun onFontSize(sp: Float)
        fun onLineSpacing(mult: Float)
        fun onBackgroundOpacity(v: Float)
        fun onTextOpacity(v: Float)
        fun onWidth(px: Int)
        fun onHeight(px: Int)
        fun onSizeChangeFinished()
        fun onManualSpeed(v: Float)
        fun onSmartFollow(on: Boolean)
        fun onAlignCenter(on: Boolean)
        fun onMirror(on: Boolean)
        fun onLock(on: Boolean)
        fun onAutoHide(on: Boolean)
        fun onPreset(preset: Preset)
        fun onBackToStart()
        fun onOpenCamera()
        fun onCloseTeleprompter()
        fun onDone()
    }

    enum class Preset { NEAR_CAMERA, TOP_BAND, LARGE }

    private var widthBar: SeekBar? = null
    private var heightBar: SeekBar? = null
    private var widthRange = 0..1
    private var heightRange = 0..1

    private fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, context.resources.displayMetrics).roundToInt()

    fun build(v: Values): View {
        val col = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14f), dp(8f), dp(14f), dp(12f))
        }

        // Header
        col.addView(LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(TextView(context).apply {
                text = "Teleprompter settings"
                setTextColor(Color.WHITE)
                textSize = 15f
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
            addView(Button(context).apply { text = "Done"; setOnClickListener { cb.onDone() } })
        })

        // Text size: A− ───●─── A+
        col.addView(label("Text size"))
        val fontValue = valueText("${v.fontSp.roundToInt()} sp")
        col.addView(LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(TextView(context).apply { text = "A−"; setTextColor(Color.WHITE); textSize = 13f })
            addView(seek(FONT_MIN.roundToInt(), FONT_MAX.roundToInt(), v.fontSp.roundToInt()) { p, _ ->
                fontValue.text = "$p sp"
                cb.onFontSize(p.toFloat())
            }.apply { contentDescription = "Text size" })
            addView(TextView(context).apply { text = "A+"; setTextColor(Color.WHITE); textSize = 20f })
            addView(fontValue)
        })

        sliderRow(col, "Line spacing", 100, 220, (v.lineSpacing * 100).roundToInt(), { "%.2f×".format(it / 100f) }) { p, _ -> cb.onLineSpacing(p / 100f) }
        sliderRow(col, "Background opacity", 0, 100, (v.backgroundOpacity * 100).roundToInt(), { "$it %" }) { p, _ -> cb.onBackgroundOpacity(p / 100f) }
        sliderRow(col, "Text opacity", 30, 100, (v.textOpacity * 100).roundToInt(), { "$it %" }) { p, _ -> cb.onTextOpacity(p / 100f) }

        widthRange = v.minWidth..maxOf(v.minWidth + 1, v.maxWidth)
        heightRange = v.minHeight..maxOf(v.minHeight + 1, v.maxHeight)
        widthBar = sliderRow(col, "Window width", widthRange.first, widthRange.last, v.width, { "${it * 100 / widthRange.last} %" }, onStop = cb::onSizeChangeFinished) { p, user ->
            if (user) cb.onWidth(p)
        }
        heightBar = sliderRow(col, "Window height", heightRange.first, heightRange.last, v.height, { "${it * 100 / heightRange.last} %" }, onStop = cb::onSizeChangeFinished) { p, user ->
            if (user) cb.onHeight(p)
        }
        sliderRow(col, "Scroll speed (manual)", 10, 100, (v.manualSpeed * 10).roundToInt(), { "%.1f".format(it / 10f) }) { p, _ -> cb.onManualSpeed(p / 10f) }

        col.addView(switchRow("Smart Follow (follow my voice)", v.smartFollow, cb::onSmartFollow))
        col.addView(switchRow("Center text", v.alignCenter, cb::onAlignCenter))
        col.addView(switchRow("Mirror text", v.mirror, cb::onMirror))
        col.addView(switchRow("Lock overlay", v.locked, cb::onLock))
        col.addView(switchRow("Auto-hide controls", v.autoHide, cb::onAutoHide))

        col.addView(label("Layout"))
        col.addView(buttonRow(
            "Near camera" to { cb.onPreset(Preset.NEAR_CAMERA) },
            "Top band" to { cb.onPreset(Preset.TOP_BAND) },
            "Large" to { cb.onPreset(Preset.LARGE) },
        ))
        col.addView(buttonRow(
            "⟲ Start" to cb::onBackToStart,
            "📷 Camera" to cb::onOpenCamera,
            "✕ Close" to cb::onCloseTeleprompter,
        ))

        return ScrollView(context).apply {
            isVerticalScrollBarEnabled = true
            background = GradientDrawable().apply {
                cornerRadius = dp(16f).toFloat()
                setColor(Color.argb(240, 28, 28, 32))
            }
            addView(col)
        }
    }

    /** Keep the size sliders in step with resizing by the corner handle or presets. */
    fun showSize(width: Int, height: Int) {
        widthBar?.progress = width.coerceIn(widthRange) - widthRange.first
        heightBar?.progress = height.coerceIn(heightRange) - heightRange.first
    }

    // ------------------------------------------------------------------ widgets

    private fun label(t: String) = TextView(context).apply {
        text = t
        setTextColor(Color.argb(200, 255, 255, 255))
        textSize = 12f
        setPadding(0, dp(10f), 0, 0)
    }

    private fun valueText(t: String) = TextView(context).apply {
        text = t
        setTextColor(Color.WHITE)
        textSize = 12f
        minWidth = dp(52f)
        gravity = Gravity.END
    }

    private fun seek(min: Int, max: Int, value: Int, onStop: (() -> Unit)? = null, onChange: (Int, Boolean) -> Unit) =
        SeekBar(context).apply {
            this.max = max - min
            progress = value.coerceIn(min, max) - min
            layoutParams = LinearLayout.LayoutParams(0, dp(40f), 1f)
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(s: SeekBar, p: Int, fromUser: Boolean) = onChange(p + min, fromUser)
                override fun onStartTrackingTouch(s: SeekBar) = Unit
                override fun onStopTrackingTouch(s: SeekBar) { onStop?.invoke() }
            })
        }

    private fun sliderRow(
        col: LinearLayout,
        title: String,
        min: Int,
        max: Int,
        value: Int,
        format: (Int) -> String,
        onStop: (() -> Unit)? = null,
        onChange: (Int, Boolean) -> Unit,
    ): SeekBar {
        col.addView(label(title))
        val valueView = valueText(format(value.coerceIn(min, max)))
        val bar = seek(min, max, value, onStop) { p, user -> valueView.text = format(p); onChange(p, user) }
        bar.contentDescription = title
        col.addView(LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(bar)
            addView(valueView)
        })
        return bar
    }

    @Suppress("UseSwitchCompatOrMaterialCode") // plain framework widgets: no AppCompat theme in a service window
    private fun switchRow(title: String, checked: Boolean, onChange: (Boolean) -> Unit) = Switch(context).apply {
        text = title
        setTextColor(Color.WHITE)
        textSize = 14f
        isChecked = checked
        minHeight = dp(44f)
        setOnCheckedChangeListener { _, b -> onChange(b) }
    }

    private fun buttonRow(vararg buttons: Pair<String, () -> Unit>) = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        buttons.forEach { (t, action) ->
            addView(Button(context).apply {
                text = t
                isAllCaps = false
                textSize = 13f
                setOnClickListener { action() }
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
        }
    }

    companion object {
        const val FONT_MIN = 18f
        const val FONT_MAX = 72f
    }
}
