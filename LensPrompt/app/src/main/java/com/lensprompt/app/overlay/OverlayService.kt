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
    private lateinit var textView: TextView
    private lateinit var clip: FrameLayout
    private lateinit var anchorLine: View
    private lateinit var playButton: TextView
    private lateinit var modeButton: TextView
    private lateinit var statusView: TextView
    private lateinit var panel: LinearLayout
    private lateinit var background: GradientDrawable
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
        running = true
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Always satisfy the foreground-service contract first, even when about to stop.
        startInForeground()
        if (intent?.action == ACTION_STOP || !Settings.canDrawOverlays(this)) {
            stopSelf()
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
            .setContentTitle("Floating teleprompter is on")
            .setContentText("Shown over your camera app. Tap to open LensPrompt.")
            .setContentIntent(open)
            .addAction(0, "Close", stop)
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

    @SuppressLint("ClickableViewAccessibility", "SetTextI18n")
    private fun showWindow() {
        val dm = resources.displayMetrics
        val s = app.settings.settings.value
        speedDp = s.manualSpeedDp
        smart = s.overlaySmartFollow && s.smartFollow
        scroll.updateConfig(s.smartFollowConfig())

        background = GradientDrawable().apply {
            cornerRadius = dp(14f).toFloat()
            setColor(Color.argb((s.overlayOpacity * 255).toInt(), 0, 0, 0))
        }
        fun button(label: String, desc: String, onClick: () -> Unit) = TextView(this).apply {
            text = label
            contentDescription = desc
            setTextColor(Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
            minWidth = dp(42f)
            minHeight = dp(42f)
            setPadding(dp(4f), 0, dp(4f), 0)
            setOnClickListener { onClick() }
        }

        // Header: drag handle + status, mode, play, settings, close.
        val handle = TextView(this).apply {
            text = "⠿"
            setTextColor(Color.argb(200, 255, 255, 255))
            textSize = 18f
            gravity = Gravity.CENTER
            minWidth = dp(36f)
            minHeight = dp(42f)
            contentDescription = "Drag to move"
        }
        statusView = TextView(this).apply {
            setTextColor(Color.argb(210, 255, 255, 255))
            textSize = 11f
            maxLines = 2
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        modeButton = button("", "Smart Follow or manual") { setSmart(!smart) }
        playButton = button("▶", "Play") { setPlaying(!playing) }
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(4f), dp(2f), dp(2f), 0)
            addView(handle)
            addView(statusView)
            addView(modeButton)
            addView(playButton)
            addView(button("⚙", "Adjust") { panel.visibility = if (panel.visibility == View.VISIBLE) View.GONE else View.VISIBLE })
            addView(button("✕", "Close floating teleprompter") { stopSelf() })
        }

        // Adjustments (hidden by default so the window stays small).
        fun row(vararg views: View) = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            views.forEach { addView(it) }
        }
        fun label(t: String) = TextView(this).apply { text = t; setTextColor(Color.argb(190, 255, 255, 255)); textSize = 12f; setPadding(dp(6f), 0, 0, 0) }
        panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            setPadding(dp(4f), 0, dp(4f), dp(2f))
            addView(row(
                label("Text"), button("A−", "Smaller text") { changeFont(-2f) }, button("A+", "Larger text") { changeFont(2f) },
                label("Speed"), button("−", "Slower") { changeSpeed(-1f) }, button("+", "Faster") { changeSpeed(1f) },
            ))
            addView(row(
                label("Opacity"), button("◐−", "More transparent") { changeOpacity(-0.1f) }, button("◐+", "Less transparent") { changeOpacity(0.1f) },
                button("⟲", "Back to start") { restart() },
                button("📷", "Open camera") { openCamera() },
            ))
        }

        textView = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = s.overlayFontSp
            setLineSpacing(0f, s.lineSpacing)
            setPadding(dp(12f), 0, dp(12f), 0)
            textDirection = View.TEXT_DIRECTION_FIRST_STRONG
            setShadowLayer(4f, 0f, 1f, Color.BLACK)
            text = "Loading…"
        }
        anchorLine = View(this).apply { setBackgroundColor(Color.argb(110, 76, 217, 100)) }
        clip = FrameLayout(this).apply {
            clipChildren = true
            addView(textView, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT))
            addView(anchorLine, FrameLayout.LayoutParams(dp(4f), dp(28f)))
        }
        textView.addOnLayoutChangeListener { _, l, t, rr, b, ol, ot, orr, ob ->
            if (mapper == null || rr - l != orr - ol || b - t != ob - ot) onTextLayout()
        }
        clip.addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ -> positionAnchor(); requestFrame() }

        // Bottom: height bar + corner (width and height).
        val heightBar = TextView(this).apply {
            text = "═"
            gravity = Gravity.CENTER
            setTextColor(Color.argb(150, 255, 255, 255))
            contentDescription = "Drag to change height"
            layoutParams = LinearLayout.LayoutParams(0, dp(22f), 1f)
        }
        val corner = TextView(this).apply {
            text = "◢"
            gravity = Gravity.END or Gravity.BOTTOM
            setTextColor(Color.argb(190, 255, 255, 255))
            contentDescription = "Drag to change width and height"
            setPadding(0, 0, dp(6f), dp(2f))
            layoutParams = LinearLayout.LayoutParams(dp(40f), dp(22f))
        }
        val footer = row(heightBar, corner)

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = this@OverlayService.background
            addView(header)
            addView(panel)
            addView(clip, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
            addView(footer)
        }

        // Default: a band across the upper part of the screen, so most of the
        // camera preview and the shutter stay uncovered.
        val w = if (s.overlayW > 0) s.overlayW else (dm.widthPixels * 0.9f).toInt()
        val h = if (s.overlayH > 0) s.overlayH else (dm.heightPixels * 0.26f).toInt()
        val params = WindowManager.LayoutParams(
            w.coerceIn(dp(180f), dm.widthPixels),
            h.coerceIn(dp(120f), dm.heightPixels),
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, // minSdk 26
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = if (s.overlayX >= 0) s.overlayX else (dm.widthPixels * 0.05f).toInt()
            y = if (s.overlayY >= 0) s.overlayY else dp(72f)
        }

        val mover = dragListener { dx, dy, start ->
            params.x = (start[0] + dx).coerceIn(-params.width / 2, dm.widthPixels - params.width / 2)
            params.y = (start[1] + dy).coerceIn(0, dm.heightPixels - dp(48f))
        }
        handle.setOnTouchListener(mover)
        statusView.setOnTouchListener(mover)
        heightBar.setOnTouchListener(dragListener { _, dy, start ->
            params.height = (start[3] + dy).coerceIn(dp(120f), dm.heightPixels)
        })
        corner.setOnTouchListener(dragListener { dx, dy, start ->
            params.width = (start[2] + dx).coerceIn(dp(180f), dm.widthPixels)
            params.height = (start[3] + dy).coerceIn(dp(120f), dm.heightPixels)
        })
        // Dragging the text moves the script position (Smart Follow restarts from there).
        clip.setOnTouchListener(object : View.OnTouchListener {
            var lastY = 0f
            override fun onTouch(v: View, e: MotionEvent): Boolean {
                val m = mapper ?: return true
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> lastY = e.rawY
                    MotionEvent.ACTION_MOVE -> {
                        scroll.snapTo((scroll.position - (e.rawY - lastY)).coerceIn(m.yAt(0.0), m.yAt(m.size.toDouble())))
                        lastY = e.rawY
                        requestFrame()
                    }
                    MotionEvent.ACTION_UP -> if (smartRunning) {
                        val start = currentToken()
                        scope.launch(worker) { controller?.start(SystemClock.elapsedRealtime(), start) }
                    }
                }
                return true
            }
        })

        try {
            wm.addView(container, params)
        } catch (e: Exception) {
            Log.e(TAG, "cannot add overlay window", e)
            stopSelf()
            return
        }
        root = container
        lp = params
        updateModeButton()
        startStatusUpdates()
    }

    /** Touch listener that moves/resizes the window; [apply] gets (dx, dy, [x, y, w, h] at down). */
    private fun dragListener(apply: (Int, Int, IntArray) -> Unit) = object : View.OnTouchListener {
        val start = IntArray(4)
        var downX = 0f
        var downY = 0f
        override fun onTouch(v: View, e: MotionEvent): Boolean {
            val p = lp ?: return true
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    start[0] = p.x; start[1] = p.y; start[2] = p.width; start[3] = p.height
                    downX = e.rawX; downY = e.rawY
                }
                MotionEvent.ACTION_MOVE -> {
                    apply((e.rawX - downX).toInt(), (e.rawY - downY).toInt(), start)
                    root?.let { wm.updateViewLayout(it, p) }
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> saveWindow()
            }
            return true
        }
    }

    private fun saveWindow() {
        val p = lp ?: return
        app.settings.update { it.copy(overlayX = p.x, overlayY = p.y, overlayW = p.width, overlayH = p.height) }
    }

    private fun changeFont(delta: Float) {
        val sp = (app.settings.settings.value.overlayFontSp + delta).coerceIn(14f, 64f)
        app.settings.update { it.copy(overlayFontSp = sp) }
        textView.textSize = sp
    }

    private fun changeSpeed(delta: Float) {
        app.settings.update { it.copy(manualSpeed = (it.manualSpeed + delta).coerceIn(1f, 10f)) }
        speedDp = app.settings.settings.value.manualSpeedDp
        flashStatus("Manual speed ${"%.0f".format(app.settings.settings.value.manualSpeed)}")
    }

    private fun changeOpacity(delta: Float) {
        val o = (app.settings.settings.value.overlayOpacity + delta).coerceIn(0.1f, 1f)
        app.settings.update { it.copy(overlayOpacity = o) }
        background.setColor(Color.argb((o * 255).toInt(), 0, 0, 0))
    }

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
        Toast.makeText(this, "No camera app found", Toast.LENGTH_SHORT).show()
    }

    private var flashUntilMs = 0L

    private fun flashStatus(text: String) {
        statusView.text = text
        flashUntilMs = SystemClock.elapsedRealtime() + 1_500
    }

    // ------------------------------------------------------------------ script

    private var scriptJob: Job? = null

    private fun loadScript(requested: String?) {
        scriptJob?.cancel()
        scriptJob = scope.launch {
            app.scripts.scripts.collectLatest { list ->
                val s = list.firstOrNull { it.id == (requested ?: scriptId) } ?: list.firstOrNull()
                val body = s?.body?.ifBlank { null } ?: "No script yet. Create one in LensPrompt."
                if (s?.id != scriptId || body != scriptText) {
                    val wasPlaying = playing
                    if (wasPlaying) setPlaying(false)
                    scriptId = s?.id
                    scriptText = body
                    languageTag = app.settings.settings.value.languageTag.ifBlank { Locale.getDefault().toLanguageTag() }
                    mapper = null
                    textView.text = body
                    scroll.snapTo(0.0)
                    textView.post { onTextLayout() }
                    requestFrame()
                }
            }
        }
    }

    /** y (px) of every token in the TextView layout, as in the full-screen prompter. */
    private fun onTextLayout() {
        val layout = textView.layout ?: return
        val tokens = TextNormalizer(languageTag).tokenize(scriptText)
        val len = textView.text.length
        val ys = FloatArray(tokens.size)
        if (len > 0) {
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
        val old = mapper
        val progress = old?.progressAt(scroll.position) ?: 0.0
        val m = ProgressMapper(ys, layout.height.toFloat())
        mapper = m
        scroll.snapTo(m.yAt(progress))
        requestFrame()
    }

    private fun anchorY(): Float = clip.height * ANCHOR_FRACTION

    private fun positionAnchor() {
        val lh = textView.lineHeight
        val top = (anchorY() - lh / 2f).toInt().coerceAtLeast(0)
        val p = anchorLine.layoutParams as FrameLayout.LayoutParams
        if (p.height == lh && p.topMargin == top) return // avoid a layout loop
        p.height = lh
        p.topMargin = top
        anchorLine.layoutParams = p
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
        val end = m.yAt(m.size.toDouble())
        if (scroll.position >= end) {
            scroll.snapTo(end)
            if (playing && !smartRunning) setPlaying(false)
        }
        textView.translationY = (anchorY() - textView.lineHeight / 2f - scroll.position).toFloat()
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
        playButton.contentDescription = if (p) "Pause" else "Play"
        if (p && smart) startSmartFollow() else stopSmartFollow()
        lastFrameNanos = 0L
        requestFrame()
    }

    private fun setSmart(on: Boolean) {
        smart = on
        app.settings.update { it.copy(overlaySmartFollow = on) }
        updateModeButton()
        if (playing) { if (on) startSmartFollow() else stopSmartFollow() }
    }

    private fun updateModeButton() {
        modeButton.text = if (smart) "AUTO" else "MAN"
        modeButton.contentDescription = if (smart) "Smart Follow on. Tap for manual scrolling" else "Manual scrolling. Tap for Smart Follow"
        modeButton.setTextColor(if (smart) Color.rgb(76, 217, 100) else Color.WHITE)
    }

    // ------------------------------------------------------------ smart follow

    private fun startSmartFollow() {
        if (smartRunning) return
        val s = app.settings.settings.value
        if (!micGranted() || micUnavailableInService) {
            flashStatus("Microphone not available to the overlay — manual speed. Open LensPrompt and allow the microphone.")
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
                    flashStatus("Loading offline speech pack…")
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
                if (SystemClock.elapsedRealtime() >= flashUntilMs) statusView.text = statusText()
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

    override fun onDestroy() {
        running = false
        if (::playButton.isInitialized) setPlaying(false)
        stopSmartFollow()
        speech?.release()
        Choreographer.getInstance().removeFrameCallback(frameCallback)
        scope.cancel()
        workerExecutor.shutdown()
        root?.let { try { wm.removeView(it) } catch (_: Exception) {} }
        root = null
        super.onDestroy()
    }

    companion object {
        private const val TAG = "OverlayService"
        private const val CHANNEL = "overlay"
        private const val NOTIFICATION_ID = 42
        private const val ACTION_STOP = "com.lensprompt.app.overlay.STOP"
        private const val EXTRA_SCRIPT_ID = "scriptId"
        private const val ANCHOR_FRACTION = 0.3f
        private const val ZERO_RUN_SILENCED_MS = 1_500L

        @Volatile var running = false
            private set

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

        fun stop(context: Context) {
            context.stopService(Intent(context, OverlayService::class.java))
        }
    }
}
