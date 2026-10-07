package com.lensprompt.app.prompter

import android.app.Application
import android.content.ContentValues
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.lensprompt.app.BuildConfig
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.audio.AudioCaptureEngine
import com.lensprompt.app.audio.AvMuxer
import com.lensprompt.app.audio.CapturedAudio
import com.lensprompt.app.camera.PrompterCamera
import com.lensprompt.app.camera.VideoForMux
import com.lensprompt.app.data.AppSettings
import com.lensprompt.app.data.Script
import com.lensprompt.app.data.SpeechEngineChoice
import com.lensprompt.app.diag.Diagnostics
import com.lensprompt.app.speech.OfflineModelCache
import com.lensprompt.app.speech.PcmSpeechEngine
import com.lensprompt.app.speech.VoskSpeechEngine
import com.lensprompt.app.speech.RecognizerStatus
import com.lensprompt.app.speech.SpeechEvent
import com.lensprompt.app.speech.SpeechRecognitionManager
import com.lensprompt.core.FollowOutput
import com.lensprompt.core.FollowState
import com.lensprompt.core.ProgressMapper
import com.lensprompt.core.RecognizerHealthMonitor
import com.lensprompt.core.RecognitionEvent
import com.lensprompt.core.SmartFollowController
import com.lensprompt.core.SpeechScenario
import com.lensprompt.core.TeleprompterScrollController
import com.lensprompt.core.TextNormalizer
import com.lensprompt.core.Token
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.io.RandomAccessFile
import java.util.Locale
import java.util.concurrent.Executors

enum class RunState { STOPPED, COUNTDOWN, RUNNING, PAUSED }

enum class BannerAction { SWITCH_TO_MANUAL, OPEN_SETTINGS, DISMISS }

data class Banner(val message: String, val action: BannerAction = BannerAction.DISMISS)

data class PrompterUiState(
    val runState: RunState = RunState.STOPPED,
    val countdown: Int = 0,
    val banner: Banner? = null,
    val simulating: Boolean = false,
    val atEnd: Boolean = false,
)

/** What the debug overlay shows; published a few times per second. */
data class DebugSnapshot(
    val follow: FollowOutput? = null,
    val scrollVelocityPx: Double = 0.0,
    val recognizer: RecognizerStatus = RecognizerStatus.OFF,
    val restarts: Int = 0,
    val frameMs: Double = 0.0,
    /** Where recognition gets its audio (route) and the key diagnostics lines. */
    val route: String = "",
    val diag: List<String> = emptyList(),
)

/**
 * Where Smart Follow gets recognized words from.
 *  SYSTEM_MIC: the system recognizer opens the microphone itself (normal prompting).
 *  OFFLINE: LensPrompt's one AudioRecord → in-process offline recognizer.
 *  SYSTEM_EXTERNAL: LensPrompt's AudioRecord → pipe → system recognizer (Android 13+),
 *    only while a health check confirms the service actually reads the pipe.
 *  PACING: no recognizer can hear the speaker; voice/lip activity paces the text.
 */
enum class Route(val label: String) {
    NONE("Smart Follow off"),
    SYSTEM_MIC("system recognizer ← its own mic"),
    OFFLINE("LensPrompt mic → offline recognizer"),
    OFFLINE_LOADING("LensPrompt mic; loading offline pack (pacing meanwhile)"),
    SYSTEM_EXTERNAL("LensPrompt mic → pipe → system recognizer"),
    PACING("LensPrompt mic → pacing by voice/lips (no recognizer)"),
}

/**
 * Owns a prompting session: run state, the Smart Follow controller (on its own
 * worker thread), the speech recognizer and the pixel scroll controller.
 *
 * Threads:
 *  - main: UI, frame loop ([onFrame]), speech recognizer callbacks;
 *  - worker ("smart-follow"): every [SmartFollowController] call, including
 *    alignment and the 60 Hz [SmartFollowController.tick].
 * The worker publishes immutable [FollowOutput] snapshots through volatile
 * fields; the frame loop extrapolates them to the exact frame time.
 */
class PrompterViewModel(app: Application, val scriptId: String) : AndroidViewModel(app) {

    private val container = app as LensPromptApplication
    val settings: StateFlow<AppSettings> = container.settings.settings

    val script: StateFlow<Script?> = container.scripts.scripts
        .map { list -> list.firstOrNull { it.id == scriptId } }
        .stateIn(viewModelScope, SharingStarted.Eagerly, container.scripts.get(scriptId))

    private val speech = SpeechRecognitionManager(app)

    /** Camera lives here so recording survives recomposition; views are passed in per bind. */
    val camera = PrompterCamera(app)

    /**
     * LensPrompt's own microphone capture, active while recording video with sound.
     * Android silences other microphone users while a video recorder captures sound
     * (CAMCORDER is privacy-sensitive), so during recording this is the single mic
     * owner and feeds both the soundtrack and the recognizer.
     */
    private val mic = AudioCaptureEngine(app)
    /** True while recording video with sound (LensPrompt's mic writes the soundtrack). */
    @Volatile private var recordingWithSound = false
    @Volatile private var route = Route.NONE
    private var offlineEngine: PcmSpeechEngine? = null
    private var offlineEventsJob: Job? = null
    private var offlineFailed = false
    private var modelLoadJob: Job? = null
    private var healthJob: Job? = null
    private var diagLogJob: Job? = null
    private val health = RecognizerHealthMonitor()
    private val levelSink: (Float, Long) -> Unit = { db, t -> viewModelScope.launch(worker) { controller?.onAudioLevel(db, t) } }
    private val workerExecutor = Executors.newSingleThreadExecutor { r -> Thread(r, "smart-follow") }
    private val worker = workerExecutor.asCoroutineDispatcher()

    private val _ui = MutableStateFlow(PrompterUiState())
    val ui: StateFlow<PrompterUiState> = _ui.asStateFlow()

    private val _debug = MutableStateFlow(DebugSnapshot())
    val debug: StateFlow<DebugSnapshot> = _debug.asStateFlow()

    /** Coarse follow state for the on-screen indicator (changes rarely). */
    private val _followState = MutableStateFlow(FollowState.IDLE)
    val followState: StateFlow<FollowState> = _followState.asStateFlow()

    // ---- worker-confined
    private var controller: SmartFollowController? = null
    private var controllerKey: String? = null
    private var tickJob: Job? = null
    private var simulationJob: Job? = null
    private var lastDebugPublishMs = 0L

    // ---- shared snapshot (written by worker, read by main)
    @Volatile private var latest: FollowOutput? = null
    @Volatile private var latestAtMs = 0L

    // ---- main-confined
    private val scroll = TeleprompterScrollController()
    private var mapper: ProgressMapper? = null
    private var lastFrameNanos = 0L
    private var countdownJob: Job? = null
    private var smartActive = false
    private var frameMsAvg = 16.0

    /**
     * Frame demand: the frame loop runs only while the text is (or should be)
     * moving, or a redraw is pending. When paused and settled it suspends, so an
     * idle prompter costs no CPU/battery.
     */
    private val frameDemand = MutableStateFlow(0L)
    private var redrawPending = true

    /** Normalized tokens of the current script, shared with the layout code. */
    fun tokens(text: String): List<Token> = TextNormalizer(languageTag()).tokenize(text)

    init {
        container.scripts.markOpened(scriptId)
        viewModelScope.launch(worker) {
            speech.events.collect { handleSpeechEvent(it) }
        }
    }

    // ------------------------------------------------------------- controls

    /** Start or resume; runs the countdown first when starting from STOPPED. */
    fun play() {
        when (_ui.value.runState) {
            RunState.RUNNING, RunState.COUNTDOWN -> return
            RunState.PAUSED -> begin()
            RunState.STOPPED -> {
                val seconds = settings.value.countdownSeconds
                if (seconds <= 0) { begin(); return }
                countdownJob = viewModelScope.launch {
                    for (n in seconds downTo 1) {
                        _ui.update { it.copy(runState = RunState.COUNTDOWN, countdown = n) }
                        delay(1_000)
                    }
                    _ui.update { it.copy(countdown = 0) }
                    begin()
                }
            }
        }
    }

    fun pause() {
        countdownJob?.cancel()
        if (_ui.value.runState == RunState.COUNTDOWN) {
            _ui.update { it.copy(runState = RunState.STOPPED, countdown = 0) }
            return
        }
        if (_ui.value.runState != RunState.RUNNING) return
        haltFollowing()
        _ui.update { it.copy(runState = RunState.PAUSED) }
    }

    fun stop() {
        countdownJob?.cancel()
        haltFollowing()
        _ui.update { it.copy(runState = RunState.STOPPED, countdown = 0) }
    }

    fun resetToStart() {
        stop()
        scroll.snapTo(mapper?.yAt(0.0) ?: 0.0)
        _ui.update { it.copy(atEnd = false) }
        requestFrames()
    }

    fun togglePlay() {
        if (_ui.value.runState == RunState.RUNNING || _ui.value.runState == RunState.COUNTDOWN) pause() else play()
    }

    fun setSmartFollow(enabled: Boolean) {
        val wasRunning = _ui.value.runState == RunState.RUNNING
        if (wasRunning) haltFollowing()
        container.settings.update { it.copy(smartFollow = enabled) }
        if (wasRunning) begin()
    }

    fun adjustManualSpeed(delta: Float) {
        container.settings.update { it.copy(manualSpeed = (it.manualSpeed + delta).coerceIn(1f, 10f)) }
    }

    fun dismissBanner() = _ui.update { it.copy(banner = null) }

    fun onBannerAction(action: BannerAction) {
        when (action) {
            BannerAction.SWITCH_TO_MANUAL -> { dismissBanner(); setSmartFollow(false); play() }
            else -> dismissBanner()
        }
    }

    /** The screen left the foreground: stop the microphone, keep the position. */
    fun onBackground() {
        if (_ui.value.runState == RunState.RUNNING || _ui.value.runState == RunState.COUNTDOWN) pause()
    }

    fun onMicPermissionDenied() {
        _ui.update {
            it.copy(banner = Banner("Smart Follow needs microphone access. You can use manual scrolling instead.", BannerAction.SWITCH_TO_MANUAL))
        }
    }

    // -------------------------------------------------------------- recording

    /**
     * Start/stop video recording. With sound enabled, LensPrompt takes the
     * microphone itself (instead of CameraX) so Smart Follow keeps hearing the
     * speaker; the audio is muxed into the video when recording stops.
     * Requires RECORD_AUDIO when sound is enabled (the screen asks first).
     */
    fun toggleRecording() {
        if (camera.state.value.isRecording) {
            camera.stopRecording()
            return
        }
        if (camera.state.value.processing) return
        if (!settings.value.recordAudio) {
            camera.startSilentRecording()
            return
        }
        val stamp = System.currentTimeMillis()
        val cache = getApplication<Application>().cacheDir
        val pcm = File(cache, "lp_rec_$stamp.pcm")
        val video = File(cache, "lp_rec_$stamp.mp4")

        // One microphone owner: stop every other capture (system recognizer, our
        // own prompting capture), then open the mic once for the soundtrack.
        teardownRoute()
        val micOk = mic.start(pcm, levelSink)
        if (!micOk) {
            applyRoute("mic unavailable for recording")
            _ui.update { it.copy(banner = Banner("The microphone is unavailable (in use by another app?). Recording without sound.")) }
            Diagnostics.recordingState = "recording without sound (mic unavailable)"
            camera.startSilentRecording()
            return
        }
        recordingWithSound = true
        Diagnostics.recordingState = "recording with sound (LensPrompt mic)"
        Diagnostics.muxState = "-"
        applyRoute("recording started")
        maybeSuggestOfflinePack()
        val started = camera.startRecordingForMux(video) { result -> onVideoFinished(result, pcm) }
        if (!started) {
            releaseMicAndRestoreRecognition()
            pcm.delete()
        }
    }

    /** Lip openness from the camera analyzer thread (null = no face). */
    fun onMouthOpenness(openness: Double?, timeMs: Long) {
        viewModelScope.launch(worker) { controller?.onMouthOpenness(openness, timeMs) }
    }

    private fun onVideoFinished(result: VideoForMux, pcm: File) {
        val audio = releaseMicAndRestoreRecognition()
        Diagnostics.muxState = if (audio == null) "no audio captured" else "muxing ${audio.frames} frames"
        if (result.error != null) {
            Diagnostics.muxState = "recording error: ${result.error}"
            camera.reportError(result.error)
            result.file.delete(); pcm.delete()
            return
        }
        val name = camera.newVideoName()
        viewModelScope.launch(Dispatchers.IO) {
            val message = try {
                saveRecording(result, audio, name)
            } catch (e: Exception) {
                Log.e(TAG, "saving recording failed", e)
                null
            } finally {
                result.file.delete()
                pcm.delete()
            }
            Diagnostics.muxState = message ?: "save failed"
            Diagnostics.log("recording saved")
            withContext(Dispatchers.Main) {
                if (message != null) camera.reportSaved(message) else camera.reportError("Could not save the recording.")
            }
        }
    }

    /** Stops LensPrompt's microphone and puts recognition back on the system microphone. */
    private fun releaseMicAndRestoreRecognition(): CapturedAudio? {
        if (!recordingWithSound) return null
        teardownRoute()
        val audio = mic.stop()
        recordingWithSound = false
        Diagnostics.recordingState = "idle"
        applyRoute("recording stopped")
        return audio
    }

    /**
     * IO thread. Muxes video + captured audio into Movies/LensPrompt. If muxing
     * fails the video is still saved (without sound) rather than lost.
     */
    private fun saveRecording(video: VideoForMux, audio: CapturedAudio?, name: String): String {
        val app = getApplication<Application>()
        val uri: android.net.Uri? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, "$name.mp4")
                put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/LensPrompt")
                put(MediaStore.MediaColumns.IS_PENDING, 1)
            }
            app.contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException("MediaStore insert failed")
        } else {
            null
        }
        val outFile: File? = if (uri == null) {
            File(app.getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: app.filesDir, "$name.mp4")
        } else {
            null
        }
        // Runs [block] with a fresh read-write descriptor of the destination; the
        // descriptor is owned (and closed) here, never by the block.
        fun withOutput(block: (java.io.FileDescriptor) -> Unit) {
            if (uri != null) {
                app.contentResolver.openFileDescriptor(uri, "rw")!!.use { block(it.fileDescriptor) }
            } else {
                RandomAccessFile(outFile!!, "rw").use { raf -> raf.setLength(0); block(raf.fd) }
            }
        }
        try {
            var message = "Saved to Movies/LensPrompt"
            try {
                if (audio == null) throw IllegalStateException("no audio captured")
                withOutput { fd -> AvMuxer.mux(video.file, audio, video.videoStartNanos, fd, app.cacheDir) }
            } catch (e: Exception) {
                Log.e(TAG, "audio mux failed; saving video without sound", e)
                withOutput { fd ->
                    val out = java.io.FileOutputStream(fd) // not closed: fd belongs to withOutput
                    out.channel.truncate(0)
                    FileInputStream(video.file).use { input -> input.copyTo(out, 256 * 1024) }
                    out.flush()
                }
                message = "Saved to Movies/LensPrompt — without sound (audio processing failed)"
            }
            if (uri != null) {
                app.contentResolver.update(uri, ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }, null, null)
            }
            return message
        } catch (e: Exception) {
            if (uri != null) try { app.contentResolver.delete(uri, null, null) } catch (_: Exception) {}
            throw e
        }
    }

    // --------------------------------------------------------------- dragging

    fun onDrag(deltaPx: Float) {
        val m = mapper ?: return
        val next = (scroll.position - deltaPx).coerceIn(m.yAt(0.0), m.yAt(m.size.toDouble()))
        scroll.snapTo(next)
        _ui.update { it.copy(atEnd = false) }
        requestFrames()
    }

    /** After the user moved the text by hand, Smart Follow restarts from there. */
    fun onDragEnd() {
        if (_ui.value.runState == RunState.RUNNING && smartActive) {
            val start = currentToken()
            viewModelScope.launch(worker) { controller?.start(SystemClock.elapsedRealtime(), start) }
        }
    }

    // ----------------------------------------------------------------- layout

    /**
     * New text layout (first layout, font size, width or rotation change).
     * Keeps the same script position under the anchor.
     */
    fun onLayout(tokenY: FloatArray, endY: Float) {
        val old = mapper
        val progress = old?.progressAt(scroll.position) ?: 0.0
        val m = ProgressMapper(tokenY, endY)
        mapper = m
        scroll.snapTo(m.yAt(progress))
        requestFrames()
    }

    // ------------------------------------------------------------------ frame

    /** Called once per display frame on the main thread; returns the scroll offset (px). */
    fun onFrame(frameNanos: Long, density: Float): Float {
        val m = mapper ?: return 0f
        val dt = if (lastFrameNanos == 0L) 0.0 else ((frameNanos - lastFrameNanos) / 1e9).coerceIn(0.0, 0.1)
        lastFrameNanos = frameNanos
        if (dt > 0) frameMsAvg += (dt * 1000 - frameMsAvg) * 0.05
        val s = settings.value
        val running = _ui.value.runState == RunState.RUNNING
        val endPx = m.yAt(m.size.toDouble())

        when {
            running && smartActive -> {
                val out = latest
                if (out == null) {
                    scroll.cruise(dt, 0.0)
                } else {
                    val age = ((SystemClock.elapsedRealtime() - latestAtMs) / 1000.0).coerceIn(0.0, 0.1)
                    val p = out.targetProgress + out.targetVelocity * age
                    scroll.follow(dt, m.yAt(p), out.targetVelocity * m.pxPerToken(p))
                }
            }
            running -> scroll.cruise(dt, s.manualSpeedDp.toDouble() * density)
            else -> scroll.cruise(dt, 0.0) // smooth stop
        }

        if (scroll.position >= endPx) {
            scroll.snapTo(endPx)
            if (running && !smartActive) {
                pause()
                _ui.update { it.copy(atEnd = true) }
            }
        }
        redrawPending = false
        return scroll.position.toFloat()
    }

    fun scrollVelocityPx(): Double = scroll.velocity

    fun scrollPositionPx(): Double = scroll.position

    /** True while another frame is needed (running, still moving, or redraw pending). */
    fun needsFrames(): Boolean =
        _ui.value.runState == RunState.RUNNING || scroll.velocity != 0.0 || redrawPending

    /** Suspends the frame loop until something needs frames again. Main thread. */
    suspend fun awaitFrameDemand() {
        lastFrameNanos = 0L
        frameDemand.first { needsFrames() }
    }

    private fun requestFrames() {
        redrawPending = true
        frameDemand.value = frameDemand.value + 1
    }

    // ------------------------------------------------------------- internals

    private fun languageTag(): String =
        settings.value.languageTag.ifBlank { Locale.getDefault().toLanguageTag() }

    private fun currentToken(): Int = mapper?.progressAt(scroll.position)?.toInt() ?: 0

    private fun begin() {
        val text = script.value?.body.orEmpty()
        if (text.isBlank()) {
            _ui.update { it.copy(runState = RunState.STOPPED, banner = Banner("This script is empty. Add some text first.")) }
            return
        }
        val s = settings.value
        val cfg = s.smartFollowConfig()
        scroll.updateConfig(cfg)
        _ui.update { it.copy(runState = RunState.RUNNING, countdown = 0, atEnd = false) }
        requestFrames()
        if (!s.smartFollow) {
            smartActive = false
            return
        }
        smartActive = true
        offlineFailed = false
        val simulate = BuildConfig.DEBUG && s.debugMode && _ui.value.simulating
        if (!simulate && !speech.isAvailable() && languageModelDir() == null) {
            smartActive = false
            _ui.update {
                it.copy(
                    runState = RunState.PAUSED,
                    banner = Banner("Speech recognition is not available on this device. Use manual scrolling instead.", BannerAction.SWITCH_TO_MANUAL),
                )
            }
            return
        }
        val lang = languageTag()
        val startToken = currentToken()
        latest = null
        viewModelScope.launch(worker) {
            val key = "${text.hashCode()}|$lang|$cfg"
            val c = if (controllerKey == key) controller!! else SmartFollowController(text, lang, cfg)
            controller = c
            controllerKey = key
            c.start(SystemClock.elapsedRealtime(), startToken)
            startTicker()
            if (simulate) startSimulation(text, lang, startToken)
        }
        if (!simulate) {
            preloadOfflineModel()
            applyRoute("start")
        }
        startDiagLog()
    }

    // ------------------------------------------------------------ audio route

    private fun languageModelDir(): File? = container.models.modelDirFor(languageTag())

    /** Load the offline pack in the background so recording can switch to it instantly. */
    private fun preloadOfflineModel() {
        val s = settings.value
        val dir = languageModelDir() ?: return
        if (s.speechEngine == SpeechEngineChoice.SYSTEM) return
        if (!(s.recordAudio || s.speechEngine == SpeechEngineChoice.OFFLINE || !speech.isAvailable())) return
        if (OfflineModelCache.loadedFor(dir) != null || modelLoadJob?.isActive == true) return
        modelLoadJob = viewModelScope.launch(Dispatchers.IO) {
            try {
                OfflineModelCache.load(dir)
            } catch (e: Throwable) {
                Log.e(TAG, "offline model failed to load", e)
                Diagnostics.lastRecognizerError = "offline model load failed: ${e.message}"
                offlineFailed = true
            }
            withContext(Dispatchers.Main) { if (route == Route.OFFLINE_LOADING) applyRoute("offline model loaded") }
        }
    }

    /**
     * Picks where recognized words come from and starts exactly one consumer of
     * the microphone. Main thread. Order of preference:
     *  1. offline pack on LensPrompt's own capture (recording with sound, or chosen);
     *  2. not recording: the system recognizer on its own microphone;
     *  3. recording, Android 13+: the system recognizer fed through a pipe, unless
     *     this service was already found to ignore it; a health check stops it if
     *     it never hears anything (no endless restarts);
     *  4. pacing by voice / lip activity.
     */
    private fun applyRoute(reason: String) {
        teardownRoute()
        val s = settings.value
        if (!smartActive || _ui.value.simulating) {
            setRoute(Route.NONE, reason)
            return
        }
        val dir = languageModelDir()
        val offlineWanted = dir != null && !offlineFailed && s.speechEngine != SpeechEngineChoice.SYSTEM &&
            (recordingWithSound || s.speechEngine == SpeechEngineChoice.OFFLINE || !speech.isAvailable())
        val target = when {
            offlineWanted -> if (OfflineModelCache.loadedFor(dir!!) != null) Route.OFFLINE else Route.OFFLINE_LOADING
            !recordingWithSound -> Route.SYSTEM_MIC
            speech.supportsExternalAudio() &&
                container.recognizerVerdicts.externalAudioBroken(speech.serviceComponent()) == null -> Route.SYSTEM_EXTERNAL
            else -> Route.PACING
        }
        val lang = languageTag()
        val cfg = s.smartFollowConfig()

        // LensPrompt's own capture is needed for every route except SYSTEM_MIC.
        if (target != Route.SYSTEM_MIC && !mic.isRunning) {
            if (!mic.start(null, levelSink)) {
                Diagnostics.lastRecognizerError = "LensPrompt could not open the microphone"
                setRoute(Route.SYSTEM_MIC, "$reason; own mic unavailable")
                speech.start(lang, s.preferOffline, cfg)
                setRecognitionAvailable(true)
                return
            }
        }
        when (target) {
            Route.SYSTEM_MIC -> {
                if (mic.isRunning && !recordingWithSound) mic.stop()
                speech.start(lang, s.preferOffline, cfg)
                setRecognitionAvailable(true)
            }
            Route.OFFLINE -> {
                val model = OfflineModelCache.loadedFor(dir!!)!!
                val spec = container.models.specFor(lang)
                Diagnostics.resetRecognizer("offline (Vosk)", "${spec?.label ?: lang}: ${dir.parentFile?.let { File(it, "name") }?.takeIf { it.exists() }?.readText()?.trim() ?: dir.name}")
                val engine = VoskSpeechEngine(model, spec?.key ?: lang)
                offlineEventsJob = viewModelScope.launch(worker, start = CoroutineStart.UNDISPATCHED) {
                    engine.events.collect { handleSpeechEvent(it) }
                }
                if (engine.start()) {
                    offlineEngine = engine
                    mic.pcm16kSink = engine::accept
                    setRecognitionAvailable(true)
                } else {
                    offlineEventsJob?.cancel()
                    offlineFailed = true
                    applyRoute("offline recognizer failed to start")
                    return
                }
            }
            Route.OFFLINE_LOADING -> {
                preloadOfflineModel()
                setRecognitionAvailable(false)
            }
            Route.SYSTEM_EXTERNAL -> {
                speech.start(lang, s.preferOffline, cfg, mic.recognizerFeed)
                setRecognitionAvailable(true)
                startHealthCheck()
            }
            Route.PACING -> {
                Diagnostics.resetRecognizer("none", speech.serviceComponent())
                Diagnostics.recognizerVerdict = container.recognizerVerdicts.externalAudioBroken(speech.serviceComponent())
                    ?: if (speech.supportsExternalAudio()) "-" else "Android < 13: system recognizer cannot take app audio"
                setRecognitionAvailable(false)
            }
            Route.NONE -> Unit
        }
        setRoute(target, reason)
    }

    /** Stops every recognizer consumer; leaves the microphone to the caller. Main thread. */
    private fun teardownRoute() {
        healthJob?.cancel()
        healthJob = null
        speech.stop()
        mic.pcm16kSink = null
        offlineEngine?.stop()
        offlineEngine = null
        offlineEventsJob?.cancel()
        offlineEventsJob = null
        if (!recordingWithSound && mic.isRunning) mic.stop()
    }

    private fun setRoute(r: Route, reason: String) {
        route = r
        Diagnostics.smartFollowSource = when (r) {
            Route.NONE -> if (smartActive) "simulation" else "manual"
            Route.SYSTEM_MIC -> "words (system recognizer)"
            Route.OFFLINE -> "words (offline recognizer)"
            Route.OFFLINE_LOADING, Route.PACING -> "pacing (voice/lips)"
            Route.SYSTEM_EXTERNAL -> "words (system recognizer via pipe)"
        }
        Diagnostics.log("route ${r.name} ($reason)")
    }

    private fun setRecognitionAvailable(available: Boolean) {
        viewModelScope.launch(worker) {
            controller?.onAudioSourceChanged()
            controller?.setRecognitionAvailable(available)
        }
    }

    /**
     * Watches the system recognizer fed with LensPrompt's audio. If the service
     * never drains the pipe, or never produces a word while the speaker talks,
     * it is stopped (not restarted forever), remembered as unusable for this
     * service, and Smart Follow continues by pacing.
     */
    private fun startHealthCheck() {
        health.reset()
        Diagnostics.recognizerVerdict = RecognizerHealthMonitor.describe(health.verdict)
        healthJob = viewModelScope.launch {
            while (isActive) {
                delay(500)
                val results = (Diagnostics.partialCount.get() + Diagnostics.finalCount.get()).toInt()
                val v = health.update(
                    resultsSoFar = results,
                    voicedWithoutWordsMs = latest?.voicedWithoutWordsMs ?: 0,
                    audioDroppedMs = Diagnostics.pipeFullDrops.get() * 20,
                    audioWrittenMs = Diagnostics.pipeBytesWritten.get() / 32,
                )
                Diagnostics.recognizerVerdict = RecognizerHealthMonitor.describe(v)
                when (v) {
                    RecognizerHealthMonitor.Verdict.WORKING -> { Diagnostics.log("system recognizer reads LensPrompt audio"); return@launch }
                    RecognizerHealthMonitor.Verdict.NOT_READING_AUDIO, RecognizerHealthMonitor.Verdict.NO_WORDS -> {
                        val why = RecognizerHealthMonitor.describe(v)
                        container.recognizerVerdicts.markExternalAudioBroken(speech.serviceComponent(), why)
                        Diagnostics.log("system recognizer unusable while recording: $why")
                        healthJob = null
                        applyRoute("health check: $why")
                        maybeSuggestOfflinePack(force = true)
                        return@launch
                    }
                    RecognizerHealthMonitor.Verdict.PENDING -> Unit
                }
            }
        }
    }

    private var offlineHintShown = false

    /** While recording without an offline pack, tell the user once how to get word-accurate following. */
    private fun maybeSuggestOfflinePack(force: Boolean = false) {
        if (!smartActive || route == Route.OFFLINE || route == Route.OFFLINE_LOADING) return
        if (offlineHintShown && !force) return
        val spec = container.models.specFor(languageTag())
        val msg = if (spec != null) {
            "While recording with sound, Smart Follow is pacing by your voice. For word-accurate following, " +
                "download the offline speech pack (${spec.label}, ~${spec.approxMb} MB) in Settings → Offline speech."
        } else {
            "While recording with sound, Smart Follow is pacing by your voice (no offline speech pack for this language)."
        }
        offlineHintShown = true
        if (route == Route.PACING) _ui.update { it.copy(banner = Banner(msg, BannerAction.OPEN_SETTINGS)) }
    }

    /** Logs one diagnostics line every 2 s while Smart Follow runs (adb logcat -s LensPromptDiag). */
    private fun startDiagLog() {
        diagLogJob?.cancel()
        // Release builds log only when the user turned on diagnostics (support cases).
        if (!BuildConfig.DEBUG && !settings.value.debugMode) return
        diagLogJob = viewModelScope.launch {
            while (isActive && _ui.value.runState == RunState.RUNNING) {
                Diagnostics.log("tick")
                delay(2_000)
            }
        }
    }

    private fun haltFollowing() {
        smartActive = false
        requestFrames()
        teardownRoute()
        setRoute(Route.NONE, "halted")
        diagLogJob?.cancel()
        viewModelScope.launch(worker) {
            simulationJob?.cancel()
            controller?.stop()
            controller?.let { latest = it.tick(SystemClock.elapsedRealtime()) }
            _followState.value = FollowState.IDLE
        }
    }

    /** Worker: tick the controller at ~60 Hz and publish snapshots. */
    private fun startTicker() {
        if (tickJob?.isActive == true) return
        tickJob = viewModelScope.launch(worker) {
            while (isActive) {
                val c = controller
                if (c != null) {
                    val now = SystemClock.elapsedRealtime()
                    val out = c.tick(now)
                    latest = out
                    latestAtMs = now
                    if (_followState.value != out.state) _followState.value = out.state
                    Diagnostics.voicedWithoutWordsMs = out.voicedWithoutWordsMs
                    Diagnostics.vadState = out.voice.name
                    if (now - lastDebugPublishMs >= 150) {
                        lastDebugPublishMs = now
                        publishDebug(out)
                    }
                }
                delay(16)
            }
        }
    }

    private fun publishDebug(out: FollowOutput) {
        if (!settings.value.debugMode) return
        _debug.value = DebugSnapshot(
            follow = out,
            scrollVelocityPx = scroll.velocity,
            recognizer = speech.status.value,
            restarts = speech.restarts.value,
            frameMs = frameMsAvg,
            route = route.label,
            diag = Diagnostics.hud(),
        )
    }

    /** Worker: route recognizer output into the controller. */
    private suspend fun handleSpeechEvent(e: SpeechEvent) {
        val c = controller ?: return
        when (e) {
            is SpeechEvent.SessionStarted -> c.onSessionStart()
            is SpeechEvent.Partial -> c.onPartialResult(e.text, e.timeMs)
            is SpeechEvent.Final -> c.onFinalResult(e.text, e.timeMs)
            // While LensPrompt owns the mic, levels come from its own capture instead.
            is SpeechEvent.Level -> if (route == Route.SYSTEM_MIC) c.onAudioLevel(e.rmsDb, e.timeMs)
            is SpeechEvent.EndOfSpeech -> c.onEndOfSpeech(e.timeMs)
            is SpeechEvent.Failure -> {
                Log.w(TAG, "speech failure ${e.code}: ${e.message} fatal=${e.fatal}")
                if (e.fatal && route != Route.SYSTEM_MIC) {
                    // The recognizer on LensPrompt's stream cannot run: pick the next
                    // route (offline → system pipe → pacing) instead of stopping.
                    withContext(Dispatchers.Main) {
                        if (route == Route.OFFLINE) offlineFailed = true
                        if (route == Route.SYSTEM_EXTERNAL) {
                            container.recognizerVerdicts.markExternalAudioBroken(speech.serviceComponent(), "fatal error: ${e.message}")
                        }
                        if (smartActive) applyRoute("recognizer failed: ${e.message}")
                    }
                } else if (e.fatal) {
                    c.fail(e.message)
                    withContext(Dispatchers.Main) {
                        smartActive = false
                        _ui.update {
                            it.copy(
                                runState = RunState.PAUSED,
                                banner = Banner("Smart Follow stopped: ${e.message}", BannerAction.SWITCH_TO_MANUAL),
                            )
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------- debugging

    fun setSimulation(enabled: Boolean) {
        val wasRunning = _ui.value.runState == RunState.RUNNING
        if (wasRunning) haltFollowing()
        _ui.update { it.copy(simulating = enabled) }
        if (wasRunning) begin()
    }

    /**
     * Worker: DEBUG ONLY. Replays synthetic recognizer events (reading at ~150 wpm
     * with recognizer-like latency) so Smart Follow can be tuned without speaking.
     * Clearly labelled in the UI; never used outside debug mode.
     */
    private fun startSimulation(text: String, lang: String, startToken: Int) {
        simulationJob?.cancel()
        simulationJob = viewModelScope.launch(worker) {
            val scenario = SpeechScenario(text, lang)
            val from = startToken.coerceIn(0, (scenario.words.size - 1).coerceAtLeast(0))
            scenario.read(from, scenario.words.size, 2.6)
            val events = scenario.events()
            val base = SystemClock.elapsedRealtime()
            for (ev in events) {
                val wait = base + ev.timeMs - SystemClock.elapsedRealtime()
                if (wait > 0) delay(wait)
                val c = controller ?: break
                val t = base + ev.timeMs
                when (ev) {
                    is RecognitionEvent.SessionStart -> c.onSessionStart()
                    is RecognitionEvent.Partial -> c.onPartialResult(ev.text, t)
                    is RecognitionEvent.Final -> c.onFinalResult(ev.text, t)
                    is RecognitionEvent.EndOfSpeech -> c.onEndOfSpeech(t)
                    is RecognitionEvent.AudioLevel -> c.onAudioLevel(ev.rmsDb, t)
                    is RecognitionEvent.MouthFrame -> c.onMouthOpenness(ev.openness, t)
                    is RecognitionEvent.RecognitionAvailability -> c.setRecognitionAvailable(ev.available)
                    is RecognitionEvent.AudioSourceChanged -> c.onAudioSourceChanged()
                }
            }
        }
    }

    override fun onCleared() {
        camera.stopRecording()
        teardownRoute()
        mic.stop()
        modelLoadJob?.cancel()
        camera.release()
        speech.release()
        workerExecutor.shutdown()
        super.onCleared()
    }

    class Factory(private val app: Application, private val scriptId: String) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = PrompterViewModel(app, scriptId) as T
    }

    private companion object {
        const val TAG = "Prompter"
    }
}
