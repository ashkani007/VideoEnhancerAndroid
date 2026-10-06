package com.lensprompt.app.prompter

import android.app.Application
import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.data.AppSettings
import com.lensprompt.app.data.Script
import com.lensprompt.app.speech.RecognizerStatus
import com.lensprompt.app.speech.SpeechEvent
import com.lensprompt.app.speech.SpeechRecognitionManager
import com.lensprompt.core.FollowOutput
import com.lensprompt.core.FollowState
import com.lensprompt.core.ProgressMapper
import com.lensprompt.core.RecognitionEvent
import com.lensprompt.core.SmartFollowController
import com.lensprompt.core.SpeechScenario
import com.lensprompt.core.TeleprompterScrollController
import com.lensprompt.core.TextNormalizer
import com.lensprompt.core.Token
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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
)

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
    private var micConflictWarned = false
    private var frameMsAvg = 16.0

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

    /** Called when recording starts so we can explain microphone sharing once. */
    fun onRecordingStarted(withAudio: Boolean) {
        if (withAudio && settings.value.smartFollow && !micConflictWarned) {
            micConflictWarned = true
            _ui.update {
                it.copy(banner = Banner(
                    "Recording sound while Smart Follow listens: some phones give the microphone to only one of them. " +
                        "If the text stops following, turn off \"Record audio\" in Settings or use manual mode.",
                ))
            }
        }
    }

    // --------------------------------------------------------------- dragging

    fun onDrag(deltaPx: Float) {
        val m = mapper ?: return
        val next = (scroll.position - deltaPx).coerceIn(m.yAt(0.0), m.yAt(m.size.toDouble()))
        scroll.snapTo(next)
        _ui.update { it.copy(atEnd = false) }
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
        return scroll.position.toFloat()
    }

    fun scrollVelocityPx(): Double = scroll.velocity

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
        if (!s.smartFollow) {
            smartActive = false
            return
        }
        smartActive = true
        val simulate = s.debugMode && _ui.value.simulating
        if (!simulate && !speech.isAvailable()) {
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
        if (!simulate) speech.start(lang, s.preferOffline, cfg)
    }

    private fun haltFollowing() {
        smartActive = false
        speech.stop()
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
        )
    }

    /** Worker: route recognizer output into the controller. */
    private suspend fun handleSpeechEvent(e: SpeechEvent) {
        val c = controller ?: return
        when (e) {
            is SpeechEvent.SessionStarted -> c.onSessionStart()
            is SpeechEvent.Partial -> c.onPartialResult(e.text, e.timeMs)
            is SpeechEvent.Final -> c.onFinalResult(e.text, e.timeMs)
            is SpeechEvent.Level -> c.onAudioLevel(e.rmsDb, e.timeMs)
            is SpeechEvent.EndOfSpeech -> c.onEndOfSpeech(e.timeMs)
            is SpeechEvent.Failure -> {
                Log.w(TAG, "speech failure ${e.code}: ${e.message} fatal=${e.fatal}")
                if (e.fatal) {
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
                }
            }
        }
    }

    override fun onCleared() {
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
