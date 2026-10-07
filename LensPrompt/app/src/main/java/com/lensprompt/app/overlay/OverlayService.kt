package com.lensprompt.app.overlay

import android.Manifest
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.content.res.Configuration
import android.graphics.Typeface
import android.os.Handler
import android.os.Looper
import android.view.ContextThemeWrapper
import android.view.ViewConfiguration
import android.view.WindowInsets
import com.lensprompt.core.OverlayGeometry
import com.lensprompt.core.WindowRect
import kotlin.math.abs
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import android.provider.MediaStore
import android.provider.Settings
import android.util.Log
import android.util.TypedValue
import android.view.Choreographer
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.MainActivity
import com.lensprompt.app.R
import com.lensprompt.app.audio.AudioCaptureEngine
import com.lensprompt.app.data.AppSettings
import com.lensprompt.app.data.SpeechEngineChoice
import com.lensprompt.app.diag.Diagnostics
import com.lensprompt.app.speech.OfflineModelCache
import com.lensprompt.app.speech.SpeechEvent
import com.lensprompt.app.speech.SpeechRecognitionManager
import com.lensprompt.app.speech.VoskSpeechEngine
import com.lensprompt.core.FollowOutput
import com.lensprompt.core.FollowState
import com.lensprompt.core.ProgressMapper
import com.lensprompt.core.SmartFollowController
import com.lensprompt.core.TeleprompterScrollController
import com.lensprompt.core.TextNormalizer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale
import java.util.concurrent.Executors

/**
 * Floating teleprompter drawn above other apps (Samsung Camera, Google Camera,
 * Open Camera, Instagram, …) with a TYPE_APPLICATION_OVERLAY window, which
 * needs the "Display over other apps" permission (SYSTEM_ALERT_WINDOW).
 *
 * It runs as a foreground service (types specialUse + microphone) so Android
 * keeps it alive and lets it use the microphone while the camera app is in
 * front. The service must be started while LensPrompt is in the foreground;
 * Android does not grant microphone access to a service started later.
 *
 * Smart Follow in the overlay: LensPrompt's own AudioRecord → offline
 * recognizer (if a pack is installed for the language), else the system
 * recognizer. A camera app that records video WITH sound captures the
 * microphone with a privacy-sensitive source, and Android then gives other apps
 * silence. LensPrompt detects that (AudioRecordingConfiguration.isClientSilenced,
 * plus an all-zero-samples check) and falls back to scrolling at the manual
 * speed until the microphone is free again. This is a platform rule; no app can
 * hear the microphone while another app records with CAMCORDER.
 */
class OverlayService : Service() {

    private lateinit var wm: WindowManager
    private lateinit var app: LensPromptApplication
    private var root: View? = null
    private var lp: WindowManager.LayoutParams? = null
    private lateinit var scriptView: ScriptViewport
    private lateinit var toolbar: LinearLayout
    private lateinit var settingsButton: TextView
    private lateinit var lockButton: TextView
    private lateinit var closeButton: TextView
    private lateinit var lockStrip: LinearLayout
    private lateinit var playButton: TextView
    private lateinit var modeChip: TextView
    private lateinit var hintView: TextView
    private lateinit var resizeHandle: View
    private lateinit var miniHandle: View
    private lateinit var lockBadge: View
    private lateinit var background: GradientDrawable
    private var panelView: View? = null
    private var panelController: OverlaySettingsPanel? = null
    private val handler = Handler(Looper.getMainLooper())
    private var screenW = 0
    private var screenH = 0
    private var locked = false
    private var controlsShown = true
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    // ---- prompting state (main thread)
    private var scriptId: String? = null
    private var scriptText = ""
    private var languageTag = "en"
    private var playing = false
    private var smart = true
    private var micSilenced = false
    private var lastFrameNanos = 0L
    private val scroll = TeleprompterScrollController()
    private var mapper: ProgressMapper? = null
    private var speedDp = 40f

    // ---- smart follow
    private val workerExecutor = Executors.newSingleThreadExecutor { r -> Thread(r, "overlay-follow") }
    private val worker = workerExecutor.asCoroutineDispatcher()
    private var controller: SmartFollowController? = null // worker-confined
    @Volatile private var latest: FollowOutput? = null
    @Volatile private var latestAtMs = 0L
    private var tickJob: Job? = null
    private var engineJob: Job? = null
    private var statusJob: Job? = null
    private var mic: AudioCaptureEngine? = null
    private var offline: VoskSpeechEngine? = null
    private var speech: SpeechRecognitionManager? = null
    private var routeLabel = ""
    private var smartRunning = false

    private val frameCallback = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) = onFrame(frameTimeNanos)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        app = application as LensPromptApplication
        setRunning(true)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // "Stop teleprompter" from the notification arrives as a plain startService
        // (no foreground contract): close at once, even if the window UI is stuck.
        if (intent?.action == ACTION_STOP) {
            closeOverlay("notification")
            return START_NOT_STICKY
        }
        // A start via startForegroundService must call startForeground, even when about to stop.
        startInForeground()
        if (!Settings.canDrawOverlays(this)) {
            closeOverlay("no overlay permission")
            return START_NOT_STICKY
        }
        val requested = intent?.getStringExtra(EXTRA_SCRIPT_ID)
        if (root == null) {
            showWindow()
            loadScript(requested)
        } else if (requested != null && requested != scriptId) {
            setPlaying(false)
            loadScript(requested)
        }
        return START_NOT_STICKY
    }

    private fun micGranted() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun startInForeground() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, getString(R.string.overlay_channel), NotificationManager.IMPORTANCE_LOW))
        }
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, OverlayService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        val n: Notification = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(getString(R.string.overlay_notification_title))
            .setContentText(getString(R.string.overlay_notification_text))
            .setContentIntent(open)
            .addAction(0, getString(R.string.overlay_notification_stop), stop)
            .setOngoing(true)
            .build()
        try {
            when {
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE -> {
                    var type = ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
                    if (micGranted()) type = type or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                    startForeground(NOTIFICATION_ID, n, type)
                }
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && micGranted() ->
                    startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
                else -> startForeground(NOTIFICATION_ID, n)
            }
        } catch (e: Exception) {
            // E.g. started from the background on Android 14 with the microphone type.
            Log.w(TAG, "startForeground with microphone failed; continuing without mic", e)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            } else {
                startForeground(NOTIFICATION_ID, n)
            }
            micUnavailableInService = true
        }
    }

    private var micUnavailableInService = false

    // ------------------------------------------------------------------ window

    private fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics).toInt()

    private val geometry by lazy { OverlayGeometry(minWidth = dp(MIN_WIDTH_DP), minHeight = dp(MIN_HEIGHT_DP)) }

    /** Area overlay windows can use (the screen minus status/navigation bars), px. */
    private fun usableScreen(): Pair<Int, Int> {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val m = wm.currentWindowMetrics
            val ins = m.windowInsets.getInsetsIgnoringVisibility(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
            return (m.bounds.width() - ins.left - ins.right) to (m.bounds.height() - ins.top - ins.bottom)
        }
        val dm = resources.displayMetrics
        val statusId = resources.getIdentifier("status_bar_height", "dimen", "android")
        val status = if (statusId > 0) resources.getDimensionPixelSize(statusId) else 0
        return dm.widthPixels to (dm.heightPixels - status)
    }

    private fun currentRect(): WindowRect {
        val p = lp ?: return WindowRect(0, 0, 0, 0)
        return WindowRect(p.x, p.y, p.width, p.height)
    }

    private fun applyRect(r: WindowRect) {
        val p = lp ?: return
        p.x = r.x; p.y = r.y; p.width = r.width; p.height = r.height
        root?.let { try { wm.updateViewLayout(it, p) } catch (_: Exception) {} }
        panelController?.showSize(r.width, r.height)
    }

    /** The overlay's own context: dark framework widgets. */
    private val ui: Context by lazy { ContextThemeWrapper(this, android.R.style.Theme_DeviceDefault) }

    @SuppressLint("ClickableViewAccessibility")
    private fun showWindow() {
        val s = app.settings.settings.value
        speedDp = s.manualSpeedDp
        smart = s.overlaySmartFollow && s.smartFollow
        locked = s.overlayLocked
        scroll.updateConfig(s.smartFollowConfig())

        background = GradientDrawable().apply {
            cornerRadius = dp(14f).toFloat()
            setColor(bgColor(s.overlayOpacity))
        }

        // ---- script viewport (fills everything below the toolbar)
        scriptView = ScriptViewport(ui).apply {
            textSizeSp = s.overlayFontSp.coerceIn(OverlaySettingsPanel.FONT_MIN, OverlaySettingsPanel.FONT_MAX)
            lineSpacing = s.overlayLineSpacing
            alignCenter = s.overlayAlignCenter
            mirror = s.overlayMirror
            textOpacity = s.overlayTextOpacity
            anchorFraction = ANCHOR_FRACTION
            onReflow = { onTextLayout() }
            text = getString(R.string.overlay_loading)
        }

        // ---- compact toolbar: [⠿] [MODE] [hint…] [▶] [⚙] [🔒]
        fun iconButton(label: String, desc: String, onClick: () -> Unit) = TextView(ui).apply {
            text = label
            contentDescription = desc
            setTextColor(Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
            minWidth = dp(40f)
            minHeight = dp(TOOLBAR_DP)
            setOnClickListener { touched(); onClick() }
        }
        val handle = TextView(ui).apply {
            text = "⠿"
            setTextColor(Color.argb(220, 255, 255, 255))
            textSize = 20f
            gravity = Gravity.CENTER
            minWidth = dp(40f)
            minHeight = dp(TOOLBAR_DP)
            contentDescription = getString(R.string.overlay_drag_to_move)
        }
        modeChip = TextView(ui).apply {
            textSize = 11f
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
            setPadding(dp(8f), dp(3f), dp(8f), dp(3f))
            background = GradientDrawable().apply { cornerRadius = dp(10f).toFloat(); setColor(Color.argb(90, 255, 255, 255)) }
            contentDescription = getString(R.string.overlay_mode_chip)
            setOnClickListener { touched(); setSmart(!smart) }
        }
        hintView = TextView(ui).apply {
            setTextColor(Color.argb(200, 255, 255, 255))
            textSize = 10f
            maxLines = 2
            setPadding(dp(6f), 0, dp(4f), 0)
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        playButton = iconButton("▶", getString(R.string.common_play)) { setPlaying(!playing) }
        settingsButton = iconButton("⚙", getString(R.string.overlay_settings)) { togglePanel() }
        lockButton = iconButton("🔒", getString(R.string.overlay_lock)) { setLocked(true) }
        closeButton = makeCloseButton(getString(R.string.overlay_close))
        toolbar = LinearLayout(ui).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(2f), 0, dp(2f), 0)
            addView(handle)
            addView(modeChip)
            addView(hintView)
            addView(playButton)
            addView(settingsButton)
            addView(lockButton)
            // A clear gap and divider keep × apart from play / settings.
            addView(View(ui).apply { setBackgroundColor(Color.argb(90, 255, 255, 255)) },
                LinearLayout.LayoutParams(dp(1f), dp(22f)).apply { setMargins(dp(6f), 0, dp(4f), 0) })
            addView(closeButton)
            // × must never be pushed out of a narrow window: drop less important items first.
            addOnLayoutChangeListener { _, l, _, rr, _, ol, _, orr, _ -> if (rr - l != orr - ol) fitToolbar(rr - l) }
        }

        // ---- floating bits over the script: resize corner, mini handle, lock badge
        resizeHandle = ResizeGrip(ui).apply { contentDescription = getString(R.string.overlay_resize) }
        miniHandle = TextView(ui).apply {
            text = "⋯"
            setTextColor(Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.argb(110, 0, 0, 0)) }
            contentDescription = getString(R.string.overlay_show_controls)
            alpha = 0.75f
        }
        lockBadge = TextView(ui).apply {
            text = "🔒"
            textSize = 13f
            gravity = Gravity.CENTER
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.argb(110, 0, 0, 0)) }
            contentDescription = getString(R.string.overlay_locked_badge)
            alpha = 0.6f
            setOnClickListener { showLockStrip() }
        }
        lockStrip = LinearLayout(ui).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = GradientDrawable().apply { cornerRadius = dp(18f).toFloat(); setColor(Color.argb(215, 20, 20, 24)) }
            setPadding(dp(4f), 0, dp(2f), 0)
            visibility = View.GONE
            addView(TextView(ui).apply {
                text = getString(R.string.overlay_unlock)
                setTextColor(Color.WHITE)
                textSize = 12f
                setTypeface(typeface, Typeface.BOLD)
                gravity = Gravity.CENTER
                setPadding(dp(10f), 0, dp(10f), 0)
                minHeight = dp(36f)
                contentDescription = getString(R.string.overlay_unlock_desc)
                setOnClickListener { setLocked(false) }
            })
            addView(View(ui).apply { setBackgroundColor(Color.argb(90, 255, 255, 255)) },
                LinearLayout.LayoutParams(dp(1f), dp(20f)).apply { setMargins(dp(2f), 0, dp(2f), 0) })
            addView(makeCloseButton(getString(R.string.overlay_close)))
        }
        val scriptArea = FrameLayout(ui).apply {
            addView(scriptView, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
            addView(resizeHandle, FrameLayout.LayoutParams(dp(GRIP_DP), dp(GRIP_DP), Gravity.BOTTOM or Gravity.END))
            addView(miniHandle, FrameLayout.LayoutParams(dp(28f), dp(28f), Gravity.TOP or Gravity.START).apply { setMargins(dp(4f), dp(4f), 0, 0) })
            addView(lockBadge, FrameLayout.LayoutParams(dp(28f), dp(28f), Gravity.TOP or Gravity.END).apply { setMargins(0, dp(4f), dp(4f), 0) })
            addView(lockStrip, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, dp(36f), Gravity.TOP or Gravity.END).apply { setMargins(0, dp(2f), dp(2f), 0) })
        }
        val container = LinearLayout(ui).apply {
            orientation = LinearLayout.VERTICAL
            background = this@OverlayService.background
            clipChildren = true
            addView(toolbar, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(TOOLBAR_DP)))
            addView(scriptArea, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        }

        // ---- window: restore the last layout, adapted to this screen
        val (sw, sh) = usableScreen()
        screenW = sw; screenH = sh
        val rect = when {
            s.overlayW <= 0 || s.overlayH <= 0 -> geometry.defaultRect(sw, sh, dp(8f))
            s.overlayScreenW == sw && s.overlayScreenH == sh -> geometry.clamp(WindowRect(s.overlayX, s.overlayY, s.overlayW, s.overlayH), sw, sh)
            else -> geometry.reorient(WindowRect(s.overlayX, s.overlayY, s.overlayW, s.overlayH), s.overlayScreenW, s.overlayScreenH, sw, sh)
        }
        val params = WindowManager.LayoutParams(
            rect.width, rect.height,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, // minSdk 26
            // Not focusable: the camera app keeps its input. No FLAG_LAYOUT_NO_LIMITS:
            // the window must always stay on screen.
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = rect.x
            y = rect.y
        }

        // ---- gestures: the handles move/resize the WINDOW; the script area scrolls the TEXT
        val mover = windowDrag { start, dx, dy -> geometry.move(start, dx, dy, screenW, screenH) }
        handle.setOnTouchListener(mover)
        miniHandle.setOnTouchListener(mover)
        resizeHandle.setOnTouchListener(windowDrag { start, dx, dy -> geometry.resize(start, dx, dy, screenW, screenH) })
        scriptView.setOnTouchListener(scriptGestures())

        try {
            wm.addView(container, params)
        } catch (e: Exception) {
            Log.e(TAG, "cannot add overlay window", e)
            closeOverlay("window could not be added")
            return
        }
        root = container
        lp = params
        updateChip()
        applyControlsVisibility()
        touched()
        startStatusUpdates()
    }

    /**
     * Window move/resize from a handle. Only the window changes; the script is
     * untouched, so dragging the window never scrolls the text.
     */
    private fun windowDrag(apply: (WindowRect, Int, Int) -> WindowRect) = object : View.OnTouchListener {
        var start = WindowRect(0, 0, 0, 0)
        var downX = 0f
        var downY = 0f
        var moved = false
        override fun onTouch(v: View, e: MotionEvent): Boolean {
            touched()
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    start = currentRect(); downX = e.rawX; downY = e.rawY; moved = false
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (e.rawX - downX).toInt()
                    val dy = (e.rawY - downY).toInt()
                    if (!moved && abs(dx) + abs(dy) < touchSlop) return true
                    moved = true
                    applyRect(apply(start, dx, dy))
                }
                MotionEvent.ACTION_UP -> {
                    if (moved) saveWindow() else if (v === miniHandle) showControls()
                }
                MotionEvent.ACTION_CANCEL -> if (moved) saveWindow()
            }
            return true
        }
    }

    private val touchSlop by lazy { ViewConfiguration.get(this).scaledTouchSlop }

    /** Script area: vertical drag scrolls the text (unlocked); a tap shows the controls. */
    private fun scriptGestures() = object : View.OnTouchListener {
        var downY = 0f
        var lastY = 0f
        var scrolling = false
        override fun onTouch(v: View, e: MotionEvent): Boolean {
            if (locked) {
                // Locked: nothing moves by accident; a tap only reveals the unlock badge.
                if (e.actionMasked == MotionEvent.ACTION_UP) flashLockBadge()
                return true
            }
            touched()
            val m = mapper
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { downY = e.rawY; lastY = e.rawY; scrolling = false }
                MotionEvent.ACTION_MOVE -> {
                    if (!scrolling && abs(e.rawY - downY) > touchSlop) scrolling = true
                    if (scrolling && m != null) {
                        scroll.snapTo((scroll.position - (e.rawY - lastY)).coerceIn(m.yAt(0.0), m.yAt(m.size.toDouble())))
                        requestFrame()
                    }
                    lastY = e.rawY
                }
                MotionEvent.ACTION_UP -> {
                    if (scrolling) {
                        if (smartRunning) {
                            val start = currentToken()
                            scope.launch(worker) { controller?.start(SystemClock.elapsedRealtime(), start) }
                        }
                    } else {
                        showControls()
                    }
                }
            }
            return true
        }
    }

    private fun saveWindow() {
        val p = lp ?: return
        app.settings.update {
            it.copy(overlayX = p.x, overlayY = p.y, overlayW = p.width, overlayH = p.height, overlayScreenW = screenW, overlayScreenH = screenH)
        }
    }

    /** Rotation / screen size change: keep the window on screen and in a similar place. */
    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (root == null) return
        val (sw, sh) = usableScreen()
        if (sw == screenW && sh == screenH) return
        val r = geometry.reorient(currentRect(), screenW, screenH, sw, sh)
        screenW = sw; screenH = sh
        closePanel()
        applyRect(r)
        saveWindow()
    }

    // ---- controls: auto-hide and lock

    private val autoHide = Runnable { hideControls() }

    /** Any interaction: keep controls up and restart the auto-hide timer. */
    private fun touched() {
        handler.removeCallbacks(autoHide)
        if (app.settings.settings.value.overlayAutoHide && panelView == null && !locked) {
            handler.postDelayed(autoHide, AUTO_HIDE_MS)
        }
    }

    private fun showControls() {
        if (locked) return
        controlsShown = true
        applyControlsVisibility()
        touched()
    }

    private fun hideControls() {
        if (panelView != null) return
        controlsShown = false
        applyControlsVisibility()
    }

    private fun applyControlsVisibility() {
        val full = controlsShown && !locked
        fade(toolbar, full)
        fade(resizeHandle, full)
        fade(miniHandle, !full && !locked)
        fade(lockBadge, locked && lockStrip.visibility != View.VISIBLE)
        if (!locked) lockStrip.visibility = View.GONE
    }

    private val hideLockStrip = Runnable {
        if (::lockStrip.isInitialized) { lockStrip.visibility = View.GONE; applyControlsVisibility() }
    }

    /** Locked: the 🔒 badge opens a tiny strip [UNLOCK | ×] for a few seconds. */
    private fun showLockStrip() {
        handler.removeCallbacks(hideLockStrip)
        lockBadge.animate().cancel()
        lockBadge.visibility = View.GONE
        lockStrip.alpha = 1f
        lockStrip.visibility = View.VISIBLE
        handler.postDelayed(hideLockStrip, LOCK_STRIP_MS)
    }

    /** Small, clearly recognizable × with its own touch target. */
    private fun makeCloseButton(desc: String) = TextView(ui).apply {
        text = "✕"
        contentDescription = desc
        setTextColor(Color.WHITE)
        textSize = 15f
        setTypeface(typeface, Typeface.BOLD)
        gravity = Gravity.CENTER
        minWidth = dp(36f)
        minHeight = dp(36f)
        background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.argb(150, 200, 40, 40)) }
        setOnClickListener { closeOverlay("× button") }
    }

    /**
     * Keeps × visible in narrow windows: hides the mode chip, then the lock
     * button (also in settings), then the hint; drag, play, settings and ×
     * always fit the minimum width.
     */
    private fun fitToolbar(widthPx: Int) {
        val wDp = widthPx / resources.displayMetrics.density
        modeChip.visibility = if (wDp >= 270f) View.VISIBLE else View.GONE
        lockButton.visibility = if (wDp >= 225f) View.VISIBLE else View.GONE
        hintView.visibility = if (wDp >= 300f) View.VISIBLE else View.GONE
    }

    private fun fade(v: View, show: Boolean) {
        v.animate().cancel()
        if (show) {
            if (v.visibility != View.VISIBLE) { v.alpha = 0f; v.visibility = View.VISIBLE }
            v.animate().alpha(if (v === lockBadge) 0.6f else if (v === miniHandle) 0.75f else 1f).setStartDelay(0).setDuration(150).start()
        } else if (v.visibility == View.VISIBLE) {
            v.animate().alpha(0f).setStartDelay(0).setDuration(250).withEndAction { v.visibility = View.GONE }.start()
        }
    }

    private fun flashLockBadge() {
        lockBadge.animate().cancel()
        lockBadge.alpha = 1f
        lockBadge.animate().alpha(0.6f).setStartDelay(1_200).setDuration(400).start()
    }

    private fun setLocked(on: Boolean) {
        locked = on
        app.settings.update { it.copy(overlayLocked = on) }
        if (on) closePanel()
        controlsShown = !on
        applyControlsVisibility()
        touched()
        if (on) flashHint(getString(R.string.overlay_hint_locked))
    }

    // ---- settings panel (its own small overlay window)

    private fun togglePanel() = if (panelView != null) closePanel() else openPanel()

    private fun openPanel() {
        if (panelView != null || locked) return
        val s = app.settings.settings.value
        val r = currentRect()
        val panel = OverlaySettingsPanel(ui, panelCallbacks)
        val view = panel.build(
            OverlaySettingsPanel.Values(
                fontSp = scriptView.textSizeSp,
                lineSpacing = scriptView.lineSpacing,
                backgroundOpacity = s.overlayOpacity,
                textOpacity = scriptView.textOpacity,
                width = r.width,
                height = r.height,
                minWidth = dp(MIN_WIDTH_DP),
                minHeight = dp(MIN_HEIGHT_DP),
                maxWidth = screenW,
                maxHeight = screenH,
                manualSpeed = s.manualSpeed,
                smartFollow = smart,
                alignCenter = scriptView.alignCenter,
                mirror = scriptView.mirror,
                locked = locked,
                autoHide = s.overlayAutoHide,
            ),
        )
        val pw = minOf(screenW - dp(16f), dp(420f))
        view.measure(View.MeasureSpec.makeMeasureSpec(pw, View.MeasureSpec.EXACTLY), View.MeasureSpec.UNSPECIFIED)
        val ph = minOf(view.measuredHeight, (screenH * 0.62f).toInt())
        // Below the teleprompter if it fits, else above it, else at the bottom.
        val below = r.y + r.height + dp(8f)
        val above = r.y - ph - dp(8f)
        val py = when {
            below + ph <= screenH -> below
            above >= 0 -> above
            else -> screenH - ph
        }
        val params = WindowManager.LayoutParams(
            pw, ph,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (screenW - pw) / 2
            y = py.coerceIn(0, maxOf(0, screenH - ph))
        }
        try {
            wm.addView(view, params)
        } catch (e: Exception) {
            Log.e(TAG, "cannot show settings panel", e)
            return
        }
        panelView = view
        panelController = panel
        handler.removeCallbacks(autoHide)
    }

    private fun closePanel() {
        panelView?.let { try { wm.removeView(it) } catch (_: Exception) {} }
        panelView = null
        panelController = null
        touched()
    }

    private val panelCallbacks = object : OverlaySettingsPanel.Callbacks {
        override fun onFontSize(sp: Float) {
            scriptView.textSizeSp = sp // reflows immediately, reading position kept
            app.settings.update { it.copy(overlayFontSp = sp) }
        }
        override fun onLineSpacing(mult: Float) {
            scriptView.lineSpacing = mult
            app.settings.update { it.copy(overlayLineSpacing = mult) }
        }
        override fun onBackgroundOpacity(v: Float) {
            background.setColor(bgColor(v))
            app.settings.update { it.copy(overlayOpacity = v) }
        }
        override fun onTextOpacity(v: Float) {
            scriptView.textOpacity = v
            app.settings.update { it.copy(overlayTextOpacity = v) }
        }
        override fun onWidth(px: Int) {
            val r = currentRect()
            applyRect(geometry.clamp(r.copy(width = px, x = minOf(r.x, screenW - px)), screenW, screenH))
        }
        override fun onHeight(px: Int) {
            val r = currentRect()
            applyRect(geometry.clamp(r.copy(height = px, y = minOf(r.y, screenH - px)), screenW, screenH))
        }
        override fun onSizeChangeFinished() = saveWindow()
        override fun onManualSpeed(v: Float) {
            app.settings.update { it.copy(manualSpeed = v.coerceIn(1f, 10f)) }
            speedDp = app.settings.settings.value.manualSpeedDp
        }
        override fun onSmartFollow(on: Boolean) = setSmart(on)
        override fun onAlignCenter(on: Boolean) {
            scriptView.alignCenter = on
            app.settings.update { it.copy(overlayAlignCenter = on) }
        }
        override fun onMirror(on: Boolean) {
            scriptView.mirror = on
            app.settings.update { it.copy(overlayMirror = on) }
        }
        override fun onLock(on: Boolean) = setLocked(on)
        override fun onAutoHide(on: Boolean) {
            app.settings.update { it.copy(overlayAutoHide = on) }
        }
        override fun onPreset(preset: OverlaySettingsPanel.Preset) {
            val top = dp(8f)
            val r = when (preset) {
                OverlaySettingsPanel.Preset.NEAR_CAMERA ->
                    geometry.nearCamera(screenW, screenH, top, scriptView.lineHeightPx, dp(TOOLBAR_DP))
                OverlaySettingsPanel.Preset.TOP_BAND -> geometry.defaultRect(screenW, screenH, top)
                OverlaySettingsPanel.Preset.LARGE -> geometry.large(screenW, screenH, top)
            }
            closePanel()
            applyRect(r)
            saveWindow()
            if (preset == OverlaySettingsPanel.Preset.NEAR_CAMERA) flashHint(getString(R.string.overlay_hint_near_camera))
        }
        override fun onBackToStart() = restart()
        override fun onOpenCamera() { closePanel(); openCamera() }
        override fun onCloseTeleprompter() = closeOverlay("settings panel")
        override fun onDone() = closePanel()
    }

    private fun bgColor(opacity: Float) = Color.argb((opacity.coerceIn(0f, 1f) * 255).toInt(), 0, 0, 0)

    private fun restart() {
        val m = mapper ?: return
        scroll.snapTo(m.yAt(0.0))
        if (smartRunning) scope.launch(worker) { controller?.start(SystemClock.elapsedRealtime(), 0) }
        requestFrame()
    }

    /** Opens the default camera app in video mode (the overlay stays on top). */
    private fun openCamera() {
        val intents = listOf(
            Intent(MediaStore.INTENT_ACTION_VIDEO_CAMERA),
            Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA),
        )
        for (i in intents) {
            try {
                startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return
            } catch (_: ActivityNotFoundException) {
            } catch (e: SecurityException) {
                Log.w(TAG, "cannot open camera", e)
            }
        }
        Toast.makeText(this, getString(R.string.overlay_no_camera_app), Toast.LENGTH_SHORT).show()
    }

    private var hintUntilMs = 0L

    /** A short message in the toolbar (shown with the controls). */
    private fun flashHint(text: String) {
        hintView.text = text
        hintUntilMs = SystemClock.elapsedRealtime() + 2_500
        if (!locked) showControls()
    }

    // ------------------------------------------------------------------ script

    private var scriptJob: Job? = null

    private fun loadScript(requested: String?) {
        scriptJob?.cancel()
        scriptJob = scope.launch {
            app.scripts.scripts.collectLatest { list ->
                val s = list.firstOrNull { it.id == (requested ?: scriptId) } ?: list.firstOrNull()
                val body = s?.body?.ifBlank { null } ?: getString(R.string.overlay_no_script)
                if (s?.id != scriptId || body != scriptText) {
                    if (playing) setPlaying(false)
                    scriptId = s?.id
                    scriptText = body
                    languageTag = app.settings.settings.value.languageTag.ifBlank { Locale.getDefault().toLanguageTag() }
                    mapper = null
                    scroll.snapTo(0.0)
                    scriptView.text = body // reflows → onTextLayout
                    requestFrame()
                }
            }
        }
    }

    /**
     * After every reflow (new text, width, font, spacing, alignment): y (px) of
     * every token in the wrapped layout, keeping the same script position on the
     * reading line.
     */
    private fun onTextLayout() {
        val layout = scriptView.textLayout ?: return
        val tokens = TextNormalizer(languageTag).tokenize(scriptText)
        val text = scriptView.text
        val len = text.length
        val ys = FloatArray(tokens.size)
        if (len > 0 && text.toString() == scriptText) {
            for (i in tokens.indices) {
                val off = tokens[i].start.coerceIn(0, len - 1)
                val line = layout.getLineForOffset(off)
                val ls = layout.getLineStart(line)
                val le = layout.getLineEnd(line)
                val frac = if (le > ls) (off - ls).toFloat() / (le - ls) else 0f
                val top = layout.getLineTop(line).toFloat()
                ys[i] = top + frac * (layout.getLineBottom(line) - top)
                if (i > 0 && ys[i] < ys[i - 1]) ys[i] = ys[i - 1]
            }
        }
        val progress = mapper?.progressAt(scroll.position) ?: 0.0
        val m = ProgressMapper(ys, layout.height.toFloat())
        mapper = m
        scroll.snapTo(m.yAt(progress))
        scriptView.scrollPx = scroll.position.toFloat()
        requestFrame()
    }

    private fun currentToken(): Int = mapper?.progressAt(scroll.position)?.toInt() ?: 0

    // ------------------------------------------------------------------- frame

    private fun requestFrame() {
        Choreographer.getInstance().removeFrameCallback(frameCallback)
        Choreographer.getInstance().postFrameCallback(frameCallback)
    }

    private fun onFrame(frameNanos: Long) {
        val m = mapper
        if (m == null) { lastFrameNanos = 0L; return }
        val dt = if (lastFrameNanos == 0L) 0.0 else ((frameNanos - lastFrameNanos) / 1e9).coerceIn(0.0, 0.1)
        lastFrameNanos = frameNanos
        val density = resources.displayMetrics.density
        val out = latest
        when {
            playing && smartRunning && !micSilenced && out != null && out.state != FollowState.ERROR -> {
                val age = ((SystemClock.elapsedRealtime() - latestAtMs) / 1000.0).coerceIn(0.0, 0.1)
                val p = out.targetProgress + out.targetVelocity * age
                scroll.follow(dt, m.yAt(p), out.targetVelocity * m.pxPerToken(p))
            }
            // Manual mode, or the camera app has the microphone: scroll at the manual speed.
            playing && (!smartRunning || micSilenced) -> scroll.cruise(dt, speedDp.toDouble() * density)
            else -> scroll.cruise(dt, 0.0)
        }
        // The whole script is reachable: from the first line to the last one on the reading line.
        val start = m.yAt(0.0)
        val end = m.yAt(m.size.toDouble())
        if (scroll.position < start) scroll.snapTo(start)
        if (scroll.position >= end) {
            scroll.snapTo(end)
            if (playing && !smartRunning) setPlaying(false)
        }
        scriptView.scrollPx = scroll.position.toFloat()
        if (playing || scroll.velocity != 0.0) {
            Choreographer.getInstance().postFrameCallback(frameCallback)
        } else {
            lastFrameNanos = 0L
        }
    }

    // ------------------------------------------------------------ play / modes

    private fun setPlaying(p: Boolean) {
        if (p == playing) return
        playing = p
        playButton.text = if (p) "❚❚" else "▶"
        playButton.contentDescription = if (p) getString(R.string.common_pause) else getString(R.string.common_play)
        if (p && smart) startSmartFollow() else stopSmartFollow()
        lastFrameNanos = 0L
        updateChip()
        requestFrame()
    }

    private fun setSmart(on: Boolean) {
        smart = on
        app.settings.update { it.copy(overlaySmartFollow = on) }
        if (playing) { if (on) startSmartFollow() else stopSmartFollow() }
        updateChip()
    }

    /**
     * Compact mode chip:
     *  MAN   manual scrolling (chosen, or forced: camera app has the mic / no mic)
     *  OFF   Smart Follow chosen but not running (press ▶)
     *  WAIT  listening / finding the place / speaker paused
     *  SMART following recognized words
     *  VOICE following voice activity only (no words available)
     */
    private fun updateChip() {
        if (!::modeChip.isInitialized) return
        val out = latest
        val (label, color) = when {
            !smart -> "MAN" to Color.WHITE
            !playing -> "OFF" to Color.argb(200, 200, 200, 200)
            !smartRunning || micSilenced -> "MAN" to AMBER
            out == null -> "WAIT" to AMBER
            out.state == FollowState.TRACKING || out.state == FollowState.SHORT_GAP -> "SMART" to GREEN
            out.state == FollowState.PACING -> "VOICE" to CYAN
            out.state == FollowState.ERROR -> "OFF" to Color.rgb(255, 99, 99)
            else -> "WAIT" to AMBER
        }
        if (modeChip.text != label) modeChip.text = label
        modeChip.setTextColor(color)
    }

    // ------------------------------------------------------------ smart follow

    private fun startSmartFollow() {
        if (smartRunning) return
        val s = app.settings.settings.value
        if (!micGranted() || micUnavailableInService) {
            flashHint(getString(R.string.overlay_hint_mic_unavailable))
            return
        }
        smartRunning = true
        micSilenced = false
        val cfg = s.smartFollowConfig()
        val text = scriptText
        val lang = languageTag
        val startToken = currentToken()
        latest = null
        scope.launch(worker) {
            val c = SmartFollowController(text, lang, cfg)
            controller = c
            c.start(SystemClock.elapsedRealtime(), startToken)
        }
        startTicker()
        startRecognition(s, lang)
    }

    /**
     * One microphone owner: with an offline pack, LensPrompt's AudioRecord feeds
     * the offline recognizer and the voice detector; without one, the system
     * recognizer opens the microphone itself.
     */
    private fun startRecognition(s: AppSettings, lang: String) {
        val dir = if (s.speechEngine != SpeechEngineChoice.SYSTEM) app.models.modelDirFor(lang) else null
        if (dir != null) {
            val capture = AudioCaptureEngine(this).also { mic = it }
            capture.onSilencedChanged = { silenced -> onMicSilenced(silenced) }
            val ok = capture.start(null) { db, t -> scope.launch(worker) { controller?.onAudioLevel(db, t) } }
            if (!ok) {
                mic = null
                routeLabel = "mic busy"
                onMicSilenced(true)
                return
            }
            routeLabel = "offline"
            engineJob = scope.launch {
                val model = OfflineModelCache.loadedFor(dir) ?: try {
                    flashHint(getString(R.string.overlay_loading_offline_pack))
                    withContext(Dispatchers.IO) { OfflineModelCache.load(dir) }
                } catch (e: Throwable) {
                    Log.e(TAG, "offline model failed", e)
                    null
                }
                if (model == null || !smartRunning) {
                    if (model == null) { routeLabel = "offline pack failed"; startSystemRecognizer(s, lang) }
                    return@launch
                }
                Diagnostics.resetRecognizer("offline (Vosk) in overlay", dir.parentFile?.name ?: lang)
                val engine = VoskSpeechEngine(model, lang)
                launch(worker, start = CoroutineStart.UNDISPATCHED) { engine.events.collect { onSpeechEvent(it) } }
                if (engine.start()) {
                    offline = engine
                    capture.pcm16kSink = engine::accept
                    Diagnostics.smartFollowSource = "words (offline, overlay)"
                }
            }
        } else {
            startSystemRecognizer(s, lang)
        }
    }

    private fun startSystemRecognizer(s: AppSettings, lang: String) {
        mic?.stop()
        mic = null
        routeLabel = "system recognizer"
        val sr = speech ?: SpeechRecognitionManager(this).also { speech = it }
        engineJob?.cancel()
        engineJob = scope.launch(worker, start = CoroutineStart.UNDISPATCHED) { sr.events.collect { onSpeechEvent(it) } }
        sr.start(lang, s.preferOffline, s.smartFollowConfig())
        Diagnostics.smartFollowSource = "words (system recognizer, overlay)"
    }

    private fun stopSmartFollow() {
        if (!smartRunning) return
        smartRunning = false
        tickJob?.cancel()
        engineJob?.cancel()
        engineJob = null
        mic?.pcm16kSink = null
        offline?.stop()
        offline = null
        mic?.stop()
        mic = null
        speech?.stop()
        micSilenced = false
        scope.launch(worker) { controller?.stop() }
        Diagnostics.smartFollowSource = "manual (overlay)"
    }

    /** Worker thread: recognizer output into the controller. */
    private fun onSpeechEvent(e: SpeechEvent) {
        val c = controller ?: return
        when (e) {
            is SpeechEvent.SessionStarted -> c.onSessionStart()
            is SpeechEvent.Partial -> c.onPartialResult(e.text, e.timeMs)
            is SpeechEvent.Final -> c.onFinalResult(e.text, e.timeMs)
            is SpeechEvent.Level -> if (mic == null) c.onAudioLevel(e.rmsDb, e.timeMs)
            is SpeechEvent.EndOfSpeech -> c.onEndOfSpeech(e.timeMs)
            is SpeechEvent.Failure -> if (e.fatal) {
                Log.w(TAG, "recognition failed in overlay: ${e.message}")
                c.setRecognitionAvailable(false)
            }
        }
    }

    /**
     * The camera app took the microphone (it records video with sound): Android
     * gives LensPrompt silence. Scroll at the manual speed until it is released,
     * then continue Smart Follow from the current position.
     */
    private fun onMicSilenced(silenced: Boolean) {
        if (silenced == micSilenced) return
        micSilenced = silenced
        if (!silenced && smartRunning) {
            val start = currentToken()
            scope.launch(worker) { controller?.continueFrom(SystemClock.elapsedRealtime(), start) }
        }
        requestFrame()
    }

    private fun startTicker() {
        tickJob?.cancel()
        tickJob = scope.launch(worker) {
            while (isActive) {
                controller?.let { c ->
                    val now = SystemClock.elapsedRealtime()
                    latest = c.tick(now)
                    latestAtMs = now
                }
                delay(16)
            }
        }
    }

    /** Status line + the all-zero-samples fallback for silencing detection. */
    private fun startStatusUpdates() {
        statusJob = scope.launch {
            while (isActive) {
                // Devices that do not report silencing still deliver exact zeros.
                if (smartRunning && mic != null) {
                    val zeros = Diagnostics.zeroRunMs >= ZERO_RUN_SILENCED_MS
                    if (Diagnostics.micSilenced != true) onMicSilenced(zeros)
                }
                updateChip()
                if (SystemClock.elapsedRealtime() >= hintUntilMs) {
                    hintView.text = if (app.settings.settings.value.debugMode) statusText() else ""
                }
                delay(400)
            }
        }
    }

    private fun statusText(): String {
        if (!smart) return "Manual scrolling"
        if (!playing) return "Smart Follow — press ▶"
        if (!smartRunning) return "Manual speed (microphone unavailable)"
        if (micSilenced) return "Camera app is using the mic — manual speed"
        val out = latest ?: return "Starting…"
        val what = when (out.state) {
            FollowState.TRACKING, FollowState.SHORT_GAP -> "Following"
            FollowState.PAUSED -> "Paused — keep reading"
            FollowState.PACING -> "Following your voice"
            FollowState.LOW_CONFIDENCE, FollowState.RECOVERING -> "Finding your place…"
            FollowState.ERROR -> "Recognition error"
            else -> "Listening…"
        }
        return "$what · $routeLabel"
    }

    private var closed = false

    /**
     * Close floating mode, from any entry point (× on the overlay, × in the lock
     * strip, the settings panel, the notification, or LensPrompt's own Stop
     * button via [stop]). Idempotent. Stops scrolling and Smart Follow, releases
     * the microphone and recognizer, saves the layout, removes both overlay
     * windows at once, removes the notification and stops the service. The camera
     * app and the LensPrompt process are left alone.
     */
    private fun closeOverlay(reason: String) {
        if (closed) return
        closed = true
        Log.i(TAG, "closing floating teleprompter ($reason)")
        if (::playButton.isInitialized) setPlaying(false) // stops scrolling + Smart Follow
        stopSmartFollow()
        speech?.release()
        speech = null
        if (root != null) saveWindow()
        handler.removeCallbacksAndMessages(null)
        Choreographer.getInstance().removeFrameCallback(frameCallback)
        panelView?.let { try { wm.removeViewImmediate(it) } catch (_: Exception) {} }
        panelView = null
        panelController = null
        root?.let { try { wm.removeViewImmediate(it) } catch (_: Exception) {} }
        root = null
        setRunning(false)
        stopForeground(STOP_FOREGROUND_REMOVE) // also removes the notification
        stopSelf()
    }

    override fun onDestroy() {
        closeOverlay("service destroyed")
        scope.cancel()
        workerExecutor.shutdown()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "OverlayService"
        private const val CHANNEL = "overlay"
        private const val NOTIFICATION_ID = 42
        internal const val ACTION_STOP = "com.lensprompt.app.overlay.STOP"
        private const val EXTRA_SCRIPT_ID = "scriptId"
        private const val ANCHOR_FRACTION = 0.3f
        private const val TOOLBAR_DP = 40f
        private const val GRIP_DP = 36f
        private const val MIN_WIDTH_DP = 180f
        private const val MIN_HEIGHT_DP = 110f
        private const val AUTO_HIDE_MS = 3_000L
        private const val LOCK_STRIP_MS = 4_000L
        private val GREEN = Color.rgb(76, 217, 100)
        private val AMBER = Color.rgb(255, 196, 0)
        private val CYAN = Color.rgb(90, 200, 250)
        private const val ZERO_RUN_SILENCED_MS = 1_500L

        @Volatile var running = false
            private set

        private val _runningState = MutableStateFlow(false)
        /** True while floating mode is on; LensPrompt shows "Stop floating mode" then. */
        val runningState: StateFlow<Boolean> = _runningState.asStateFlow()

        private fun setRunning(on: Boolean) {
            running = on
            _runningState.value = on
        }

        fun canDrawOverlays(context: Context) = Settings.canDrawOverlays(context)

        /** The system screen where the user allows "Display over other apps" for LensPrompt. */
        fun permissionIntent(context: Context) =
            Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${context.packageName}"))

        /** Must be called while LensPrompt is in the foreground (microphone access). */
        fun start(context: Context, scriptId: String? = null) {
            val i = Intent(context, OverlayService::class.java)
            if (scriptId != null) i.putExtra(EXTRA_SCRIPT_ID, scriptId)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(i) else context.startService(i)
        }

        /** Stop floating mode from inside LensPrompt; onDestroy does the cleanup. */
        fun stop(context: Context) {
            context.stopService(Intent(context, OverlayService::class.java))
            setRunning(false)
        }
    }
}
