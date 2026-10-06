package com.lensprompt.app.overlay

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.util.TypedValue
import android.view.Choreographer
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.app.NotificationCompat
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.MainActivity
import com.lensprompt.app.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Floating teleprompter window drawn above other apps (e.g. a third-party camera).
 *
 * Runs as a foreground service so Android does not kill it while the user is in
 * another app. Scrolling is manual-speed only: Smart Follow needs continuous
 * microphone access, which Android restricts for apps in the background, and it
 * would compete with the camera app's own audio recording.
 */
class OverlayService : Service() {

    private lateinit var wm: WindowManager
    private var root: LinearLayout? = null
    private var params: WindowManager.LayoutParams? = null
    private lateinit var textView: TextView
    private lateinit var playButton: TextView
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private var playing = false
    private var offsetPx = 0f
    private var speedDp = 40f
    private var lastFrameNanos = 0L

    private val frameCallback = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            if (!playing) { lastFrameNanos = 0L; return }
            if (lastFrameNanos != 0L) {
                val dt = ((frameTimeNanos - lastFrameNanos) / 1e9f).coerceIn(0f, 0.1f)
                offsetPx += speedDp * resources.displayMetrics.density * dt
                val maxOffset = (textView.height - 40f).coerceAtLeast(0f)
                if (offsetPx >= maxOffset) { offsetPx = maxOffset; setPlaying(false) }
                textView.translationY = -offsetPx
            }
            lastFrameNanos = frameTimeNanos
            if (playing) Choreographer.getInstance().postFrameCallback(this)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Always satisfy the foreground-service contract first, even when about to stop.
        startInForeground()
        if (intent?.action == ACTION_STOP || !Settings.canDrawOverlays(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (root == null) showWindow()
        return START_NOT_STICKY
    }

    private fun startInForeground() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, getString(R.string.overlay_channel), NotificationManager.IMPORTANCE_LOW))
        }
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, OverlayService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        val n: Notification = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("LensPrompt overlay is on")
            .setContentText("Tap to open LensPrompt")
            .setContentIntent(open)
            .addAction(0, "Close overlay", stop)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFICATION_ID, n)
        }
    }

    @SuppressLint("ClickableViewAccessibility", "SetTextI18n")
    private fun showWindow() {
        val app = application as LensPromptApplication
        val dm = resources.displayMetrics
        fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, dm).toInt()

        val settings = app.settings.settings.value
        speedDp = settings.manualSpeedDp
        val bg = GradientDrawable().apply {
            cornerRadius = dp(14f).toFloat()
            setColor(Color.argb((settings.overlayOpacity * 255).toInt(), 0, 0, 0))
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(8f), dp(4f), dp(4f), dp(4f))
        }
        fun button(label: String, desc: String, onClick: () -> Unit) = TextView(this).apply {
            text = label
            contentDescription = desc
            setTextColor(Color.WHITE)
            textSize = 18f
            gravity = Gravity.CENTER
            minWidth = dp(44f)
            minHeight = dp(44f)
            setOnClickListener { onClick() }
        }
        val handle = TextView(this).apply {
            text = "⠿ LensPrompt"
            setTextColor(Color.argb(200, 255, 255, 255))
            textSize = 13f
            layoutParams = LinearLayout.LayoutParams(0, dp(44f), 1f)
            gravity = Gravity.CENTER_VERTICAL
            contentDescription = "Drag to move"
        }
        playButton = button("▶", "Play") { setPlaying(!playing) }
        header.addView(handle)
        header.addView(button("−", "Slower") { speedDp = (speedDp - 9f).coerceAtLeast(9f) })
        header.addView(playButton)
        header.addView(button("+", "Faster") { speedDp = (speedDp + 9f).coerceAtMost(120f) })
        header.addView(button("⟲", "Back to start") { offsetPx = 0f; textView.translationY = 0f })
        header.addView(button("✕", "Close overlay") { stopSelf() })

        textView = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = (settings.fontSizeSp * 0.75f).coerceIn(16f, 48f)
            setLineSpacing(0f, settings.lineSpacing)
            setPadding(dp(12f), dp(8f), dp(12f), dp(8f))
            textDirection = View.TEXT_DIRECTION_FIRST_STRONG
            text = "Loading…"
        }
        val clip = FrameLayout(this).apply {
            clipChildren = true
            addView(textView, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT))
        }
        val resize = TextView(this).apply {
            text = "◢"
            setTextColor(Color.argb(180, 255, 255, 255))
            gravity = Gravity.END
            contentDescription = "Drag to resize"
            setPadding(0, 0, dp(6f), dp(2f))
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = bg
            addView(header)
            addView(clip, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
            addView(resize, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(24f)))
        }

        val type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY // minSdk 26
        val lp = WindowManager.LayoutParams(
            (dm.widthPixels * 0.86f).toInt(),
            (dm.heightPixels * 0.32f).toInt(),
            type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (dm.widthPixels * 0.07f).toInt()
            y = dp(80f)
        }

        // Move by dragging the header handle.
        handle.setOnTouchListener(object : View.OnTouchListener {
            var startX = 0; var startY = 0; var downX = 0f; var downY = 0f
            override fun onTouch(v: View, e: MotionEvent): Boolean {
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { startX = lp.x; startY = lp.y; downX = e.rawX; downY = e.rawY }
                    MotionEvent.ACTION_MOVE -> {
                        lp.x = startX + (e.rawX - downX).toInt()
                        lp.y = startY + (e.rawY - downY).toInt()
                        root?.let { wm.updateViewLayout(it, lp) }
                    }
                }
                return true
            }
        })
        // Resize from the bottom-right corner.
        resize.setOnTouchListener(object : View.OnTouchListener {
            var startW = 0; var startH = 0; var downX = 0f; var downY = 0f
            override fun onTouch(v: View, e: MotionEvent): Boolean {
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { startW = lp.width; startH = lp.height; downX = e.rawX; downY = e.rawY }
                    MotionEvent.ACTION_MOVE -> {
                        lp.width = (startW + (e.rawX - downX).toInt()).coerceIn(dp(180f), dm.widthPixels)
                        lp.height = (startH + (e.rawY - downY).toInt()).coerceIn(dp(140f), dm.heightPixels)
                        root?.let { wm.updateViewLayout(it, lp) }
                    }
                }
                return true
            }
        })
        // Drag the text itself to reposition while paused.
        clip.setOnTouchListener(object : View.OnTouchListener {
            var lastY = 0f
            override fun onTouch(v: View, e: MotionEvent): Boolean {
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> lastY = e.rawY
                    MotionEvent.ACTION_MOVE -> {
                        offsetPx = (offsetPx - (e.rawY - lastY)).coerceIn(0f, textView.height.toFloat())
                        textView.translationY = -offsetPx
                        lastY = e.rawY
                    }
                }
                return true
            }
        })

        try {
            wm.addView(container, lp)
        } catch (e: Exception) {
            stopSelf()
            return
        }
        root = container
        params = lp

        scope.launch {
            app.scripts.scripts.collectLatest { list ->
                val s = list.firstOrNull()
                textView.text = s?.body?.ifBlank { null } ?: "No script yet. Create one in LensPrompt."
            }
        }
    }

    private fun setPlaying(p: Boolean) {
        playing = p
        playButton.text = if (p) "❚❚" else "▶"
        playButton.contentDescription = if (p) "Pause" else "Play"
        if (p) {
            lastFrameNanos = 0L
            Choreographer.getInstance().postFrameCallback(frameCallback)
        } else {
            Choreographer.getInstance().removeFrameCallback(frameCallback)
        }
    }

    override fun onDestroy() {
        if (::playButton.isInitialized) setPlaying(false)
        scope.cancel()
        root?.let { try { wm.removeView(it) } catch (_: Exception) {} }
        root = null
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "overlay"
        private const val NOTIFICATION_ID = 42
        private const val ACTION_STOP = "com.lensprompt.app.overlay.STOP"

        fun start(context: Context) {
            val i = Intent(context, OverlayService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(i) else context.startService(i)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, OverlayService::class.java))
        }
    }
}
