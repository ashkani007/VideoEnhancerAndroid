package com.lensprompt.core

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * Smart Follow states. Exactly one is active; transitions happen only in
 * [SmartFollowController] and are covered by unit tests.
 *
 * IDLE            not following
 * LISTENING       microphone on, speaker not located yet
 * TRACKING        speaker located and progressing
 * SHORT_GAP       no progress for a moment (natural gap); coasting, slowing
 * PAUSED          speaker stopped; target velocity is zero
 * LOW_CONFIDENCE  speech heard but not matching the script; position held
 * RECOVERING      a new location was found and is waiting for confirmation
 * PACING          words cannot be recognized (e.g. the microphone is shared with
 *                 video recording); the text advances at the learned reading
 *                 speed while voice/lip activity says the speaker is talking
 * ERROR           recognition failed permanently (permission, unavailable, …)
 */
enum class FollowState { IDLE, LISTENING, TRACKING, SHORT_GAP, PAUSED, LOW_CONFIDENCE, RECOVERING, PACING, ERROR }

/** Snapshot consumed by the scroll controller and the debug overlay. */
data class FollowOutput(
    val state: FollowState,
    /** Fractional script position (tokens) the anchor line should show. */
    val targetProgress: Double,
    /** How fast [targetProgress] is currently moving, tokens/s (feed-forward). */
    val targetVelocity: Double,
    /** Last reliable aligned token index (-1 before the first match). */
    val matchedIndex: Int,
    val confidence: Double,
    /** Smoothed reading speed estimate, tokens/s. */
    val readingVelocity: Double,
    val msSinceProgress: Long,
    val lastRecognized: String,
    val pendingJumpIndex: Int,
    val errorMessage: String? = null,
    /** Audio voice activity at this tick. */
    val voice: VoiceState = VoiceState.UNKNOWN,
    /** Lip activity at this tick. */
    val visual: VisualState = VisualState.UNKNOWN,
    /** True while the text is paced by activity instead of recognized words. */
    val pacing: Boolean = false,
    /** Why pacing is active (debug): "unavailable", "stalled" or "". */
    val pacingReason: String = "",
)

/**
 * The Smart Follow brain. Pure Kotlin, single-threaded, clock injected by the
 * caller, so it is deterministic and unit-testable without a microphone.
 *
 * Pipeline per recognition event:
 *   text → normalize → query (recent words) → align (windowed) → accept/reject
 *   → progress sample → velocity estimate
 * and per frame ([tick]):
 *   pause detection → state → target position + target velocity.
 *
 * "Where" (alignment) and "how fast" (velocity) are estimated separately;
 * turning them into pixels is [TeleprompterScrollController]'s job.
 */
class SmartFollowController(
    scriptText: String,
    languageTag: String = "en",
    private val config: SmartFollowConfig = SmartFollowConfig(),
) {
    private val normalizer = TextNormalizer(languageTag)
    val index = ScriptIndex(scriptText, normalizer)
    private val aligner = ScriptAligner(index, config)
    private val velocity = ReadingVelocityEstimator(config)
    private val pause = PauseDetector(config)
    private val vad = VoiceActivityDetector()
    private val mouth = MouthActivityDetector()

    /** False when the app knows words cannot be recognized right now. */
    private var recognitionAvailable = true
    /** Voiced time accumulated since the last recognized hypothesis. */
    private var voicedWithoutWordsMs = 0.0
    private var pacing = false

    var state: FollowState = FollowState.IDLE
        private set

    /** Last reliable aligned token index; -1 = before the first token. */
    private var reliableIndex = -1
    private var reliableTimeMs = 0L
    private var lastConfidence = 0.0
    private var consecutiveRejects = 0
    private var firstRejectMs = Long.MIN_VALUE

    private var pendingJump = -1
    private var pendingConfirmations = 0

    private val history = ArrayDeque<String>()
    private var partial: List<String> = emptyList()
    private var lastQueryKey = ""
    private var lastRecognized = ""

    /** Monotonic target (except on confirmed backward reacquisition). */
    private var target = 0.0
    private var targetVel = 0.0
    /** Tokens the target has coasted past the last reliable fix. */
    private var coast = 0.0
    private var lastTickMs = Long.MIN_VALUE
    private var errorMessage: String? = null

    val scriptTokenCount: Int get() = index.size

    // ------------------------------------------------------------------ control

    /** Begin following from [startTokenIndex] (the token currently at the anchor). */
    fun start(nowMs: Long, startTokenIndex: Int = 0) {
        val start = startTokenIndex.coerceIn(0, max(0, index.size - 1))
        reliableIndex = start - 1
        reliableTimeMs = nowMs
        target = start.toDouble()
        targetVel = 0.0
        coast = 0.0
        lastConfidence = 0.0
        consecutiveRejects = 0
        firstRejectMs = Long.MIN_VALUE
        pendingJump = -1
        pendingConfirmations = 0
        history.clear()
        partial = emptyList()
        lastQueryKey = ""
        lastRecognized = ""
        errorMessage = null
        velocity.resetAll()
        pause.reset(nowMs)
        vad.reset()
        mouth.reset()
        voicedWithoutWordsMs = 0.0
        pacing = false
        lastTickMs = nowMs
        state = FollowState.LISTENING
    }

    /**
     * Restart following from a new position while keeping what was learned about
     * the speaker (reading speed). Used when the audio route changes, e.g. when
     * video recording starts and the microphone is re-routed.
     */
    fun continueFrom(nowMs: Long, startTokenIndex: Int) {
        val v = velocity.velocity
        start(nowMs, startTokenIndex)
        velocity.seed(v)
    }

    /**
     * Tell the controller whether word recognition is possible at all. When it is
     * not, the text is paced by voice/lip activity at the learned reading speed.
     */
    fun setRecognitionAvailable(available: Boolean) {
        recognitionAvailable = available
        voicedWithoutWordsMs = 0.0
    }

    /** The audio level source changed (different scale); re-learn the noise floor. */
    fun onAudioSourceChanged() = vad.reset()

    /**
     * Lip activity from the front camera: inner-lip gap divided by face height,
     * or null when no face is visible in this frame.
     */
    fun onMouthOpenness(openness: Double?, nowMs: Long) = mouth.onFrame(openness, nowMs)

    fun stop() {
        state = FollowState.IDLE
        targetVel = 0.0
    }

    /** Recognition failed permanently. Position is kept so the user can continue manually. */
    fun fail(message: String) {
        state = FollowState.ERROR
        errorMessage = message
        targetVel = 0.0
    }

    /** Recognition recovered after an error (e.g. permission granted, service back). */
    fun clearError(nowMs: Long) {
        if (state == FollowState.ERROR) {
            errorMessage = null
            state = if (reliableIndex >= 0) FollowState.PAUSED else FollowState.LISTENING
            pause.reset(nowMs)
        }
    }

    // ------------------------------------------------------------ recognition

    /** A new recognizer session began; the partial hypothesis restarts from scratch. */
    fun onSessionStart() {
        commitPartial()
    }

    fun onPartialResult(text: String, nowMs: Long) = onHypothesis(text, nowMs, isFinal = false)

    fun onFinalResult(text: String, nowMs: Long) {
        onHypothesis(text, nowMs, isFinal = true)
        commitPartial()
    }

    /**
     * Audio level from the recognizer (dB). Used only as a voice-activity signal
     * to stop coasting quickly when the speaker falls silent; it never moves the
     * text by itself.
     */
    fun onAudioLevel(rmsDb: Float, nowMs: Long) = vad.onLevel(rmsDb.toDouble(), nowMs)

    fun onEndOfSpeech(nowMs: Long) = pause.onEndOfSpeech(nowMs)

    private fun onHypothesis(text: String, nowMs: Long, isFinal: Boolean) {
        if (state == FollowState.IDLE || state == FollowState.ERROR) return
        val tokens = normalizer.tokenize(text).map { it.text }
        if (tokens.isEmpty()) return
        lastRecognized = text
        partial = tokens
        voicedWithoutWordsMs = 0.0

        val query = buildQuery()
        val key = query.joinToString(" ")
        if (key == lastQueryKey && !isFinal) return // nothing new was heard
        lastQueryKey = key

        val (from, to) = searchWindow(nowMs)
        val result = aligner.align(query, expectedIndex(nowMs), from, to)
        if (result == null) { reject(nowMs); return }
        evaluate(result, nowMs)
    }

    private fun buildQuery(): List<String> {
        val q = ArrayList<String>(config.queryTokens)
        val fromPartial = partial.takeLast(config.queryTokens)
        val needed = config.queryTokens - fromPartial.size
        if (needed > 0) {
            val h = history.size
            for (k in max(0, h - needed) until h) q.add(history[k])
        }
        q.addAll(fromPartial)
        return q
    }

    private fun commitPartial() {
        for (t in partial) {
            history.addLast(t)
            if (history.size > HISTORY_TOKENS) history.removeFirst()
        }
        partial = emptyList()
        lastQueryKey = ""
    }

    /**
     * The position decisions are made relative to: the last reliable fix, or while
     * pacing (no fresh fixes) the paced target, which is our best estimate.
     */
    private fun referenceIndex(): Int =
        if (pacing) max(reliableIndex, target.toInt() - 1) else reliableIndex

    /** Where we expect the newest recognized word to be: last fix plus predicted advance. */
    private fun expectedIndex(nowMs: Long): Int {
        if (pacing) return max(0, referenceIndex())
        val elapsed = (nowMs - reliableTimeMs).coerceAtLeast(0) / 1000.0
        val advance = min(velocity.velocity * elapsed, 8.0)
        return max(0, reliableIndex + advance.toInt())
    }

    private fun searchWindow(nowMs: Long): Pair<Int, Int> {
        val base = max(0, referenceIndex())
        val lost = state == FollowState.LOW_CONFIDENCE || state == FollowState.RECOVERING ||
            state == FollowState.LISTENING
        return if (!lost) {
            (base - config.searchBackTokens) to (base + config.searchForwardTokens)
        } else {
            val longLost = firstRejectMs != Long.MIN_VALUE && nowMs - firstRejectMs > config.lostAfterMs
            if (longLost) 0 to (index.size - 1)
            else (base - config.searchBackTokens * 2) to (base + config.recoverySearchForwardTokens)
        }
    }

    // ------------------------------------------------------------- decisions

    private fun evaluate(r: AlignmentResult, nowMs: Long) {
        if (r.confidence < config.minConfidence) { reject(nowMs); return }
        if (pacing) {
            // Words are back after a stretch of pacing. The paced target is only an
            // estimate, so accept any confident fix reasonably close to it.
            val d = r.endIndex - referenceIndex()
            if (d in -config.pacingToleranceTokens..config.pacingToleranceTokens) {
                accept(r, nowMs, jumped = true)
                return
            }
        }
        val delta = r.endIndex - reliableIndex
        val firstFix = reliableIndex < 0 || state == FollowState.LISTENING

        when {
            // Normal forward tracking (or start of tracking near the start position).
            delta in 0..config.smallJumpTokens -> accept(r, nowMs, jumped = false)

            // Small step back: the speaker is repeating or correcting. Hold, do not scroll back.
            delta < 0 && -delta <= config.backtrackAllowanceTokens -> hold(r, nowMs)

            // Larger move: a skip, a restart, or noise. Needs strong or repeated evidence.
            else -> {
                val forward = delta > 0
                val strong = r.matchedTokens >= (if (forward) config.reacquireMinMatches else config.backtrackMinMatches) &&
                    r.confidence >= config.highConfidence
                val immediate = strong && forward && (delta <= config.searchForwardTokens || firstFix)
                if (immediate) {
                    accept(r, nowMs, jumped = true)
                } else if (r.matchedTokens >= config.reacquireMinMatches) {
                    confirmJump(r, nowMs)
                } else {
                    reject(nowMs)
                }
            }
        }
    }

    private fun confirmJump(r: AlignmentResult, nowMs: Long) {
        if (pendingJump >= 0 && abs(r.endIndex - pendingJump) <= config.reacquireAgreementTokens &&
            r.endIndex >= pendingJump
        ) {
            pendingConfirmations++
        } else {
            pendingConfirmations = 1
        }
        pendingJump = r.endIndex
        if (pendingConfirmations >= config.reacquireConfirmations) {
            accept(r, nowMs, jumped = true)
        } else {
            state = FollowState.RECOVERING
            targetVel = 0.0
        }
    }

    private fun accept(r: AlignmentResult, nowMs: Long, jumped: Boolean) {
        val advanced = r.endIndex > reliableIndex
        val movedBack = r.endIndex < reliableIndex
        lastConfidence = r.confidence
        consecutiveRejects = 0
        firstRejectMs = Long.MIN_VALUE
        pendingJump = -1
        pendingConfirmations = 0

        if (jumped) velocity.resetHistory()
        val wasPacing = pacing
        if (recognitionAvailable) pacing = false
        if (advanced || movedBack) {
            reliableIndex = r.endIndex
            reliableTimeMs = nowMs
            pause.onProgress(nowMs)
            // Recognition lags speech: the speaker is already a little further on.
            coast = min(velocity.velocity * config.recognitionLatencyMs / 1000.0, config.maxCoastTokens)
            velocity.addSample(nowMs, (reliableIndex + 1).toDouble())
        }
        if (movedBack) target = (reliableIndex + 1).toDouble() // confirmed backward reacquisition
        if (advanced || wasPacing || state == FollowState.LOW_CONFIDENCE || state == FollowState.RECOVERING) {
            state = if (pacing) FollowState.PACING else FollowState.TRACKING
        }
    }

    /** Evidence consistent with the current position but not ahead of it. */
    private fun hold(r: AlignmentResult, nowMs: Long) {
        lastConfidence = r.confidence
        consecutiveRejects = 0
        firstRejectMs = Long.MIN_VALUE
        if (state == FollowState.LOW_CONFIDENCE || state == FollowState.RECOVERING) {
            state = FollowState.PAUSED
        }
    }

    private fun reject(nowMs: Long) {
        consecutiveRejects++
        if (firstRejectMs == Long.MIN_VALUE) firstRejectMs = nowMs
        lastConfidence *= 0.7
        if (consecutiveRejects >= config.lowConfidenceAfterRejects &&
            state != FollowState.LISTENING && state != FollowState.RECOVERING
        ) {
            state = FollowState.LOW_CONFIDENCE
        }
    }

    // ------------------------------------------------------------------ frame

    /** Advance time-based logic (pause detection, coasting). Call every frame or so. */
    fun tick(nowMs: Long): FollowOutput {
        val dt = if (lastTickMs == Long.MIN_VALUE) 0.0 else (nowMs - lastTickMs).coerceIn(0, 250) / 1000.0
        lastTickMs = nowMs

        val voice = vad.state(nowMs)
        val visual = mouth.state(nowMs)
        updatePacing(nowMs, dt, voice)
        if (state == FollowState.TRACKING || state == FollowState.SHORT_GAP || state == FollowState.PAUSED) {
            when (pause.phase(nowMs, voice)) {
                SpeechPhase.ACTIVE -> if (state != FollowState.PAUSED) state = FollowState.TRACKING
                SpeechPhase.SHORT_GAP -> if (state == FollowState.TRACKING) state = FollowState.SHORT_GAP
                SpeechPhase.PAUSED -> if (state != FollowState.PAUSED) {
                    state = FollowState.PAUSED
                    velocity.resetHistory() // the silent gap must not count as slow reading
                }
            }
        }

        val reliableProgress = (reliableIndex + 1).toDouble()
        val v = velocity.velocity
        if (state == FollowState.PACING) {
            // No words: advance at the learned reading speed, scaled by how sure we
            // are that the speaker is talking. Silence stops the text immediately.
            val rate = v * SpeakingFusion.rate(voice, visual)
            target = min(target + rate * dt, index.size.toDouble())
            targetVel = rate
            return output(nowMs, v, voice, visual)
        }
        val coastCap = max(config.maxCoastTokens, v * COAST_SECONDS)
        val desiredVel: Double
        when (state) {
            FollowState.TRACKING, FollowState.SHORT_GAP -> {
                // Between measurements, coast at the reading speed (half speed in a short
                // gap) but never more than coastCap past the last real fix. Measured
                // silence stops coasting at once: the speaker is not advancing.
                val rate = when {
                    voice == VoiceState.SILENCE -> 0.0
                    state == FollowState.SHORT_GAP -> v * 0.5
                    else -> v
                }
                coast = min(coast + rate * dt, coastCap)
                desiredVel = if (coast >= coastCap) 0.0 else rate
            }
            else -> desiredVel = 0.0
        }
        val desired = reliableProgress + coast

        // The target never moves backwards on its own (only a confirmed backward
        // reacquisition resets it). If it is already ahead of the evidence, the
        // feed-forward velocity tapers so the scroll waits for the speaker.
        val ahead = target - desired
        if (desired > target) target = desired
        targetVel = if (ahead <= 0.0) desiredVel else desiredVel * (1.0 - ahead / AHEAD_TAPER_TOKENS).coerceIn(0.0, 1.0)
        return output(nowMs, v, voice, visual)
    }

    /**
     * Enter pacing when recognition is known to be unavailable, or when it has
     * stalled: the speaker has been audibly talking for a while but no words
     * arrived. Leave it as soon as recognized words line up again (see evaluate)
     * or the app reports recognition available and words flow.
     */
    private fun updatePacing(nowMs: Long, dt: Double, voice: VoiceState) {
        if (state == FollowState.IDLE || state == FollowState.ERROR) return
        if (voice == VoiceState.VOICE) voicedWithoutWordsMs += dt * 1000.0
        val stalled = voicedWithoutWordsMs >= config.recognitionStallVoicedMs
        val shouldPace = !recognitionAvailable || stalled
        if (shouldPace && !pacing) {
            pacing = true
            pendingJump = -1
            pendingConfirmations = 0
            // Continue from where the text is, never jump back.
            target = max(target, (reliableIndex + 1).toDouble())
        }
        // Pacing ends only when recognized words line up again (see accept).
        if (pacing) state = FollowState.PACING
    }

    private fun output(nowMs: Long, v: Double, voice: VoiceState, visual: VisualState): FollowOutput =
        FollowOutput(
            state = state,
            targetProgress = target,
            targetVelocity = targetVel,
            matchedIndex = reliableIndex,
            confidence = lastConfidence,
            readingVelocity = v,
            msSinceProgress = pause.msSinceProgress(nowMs).coerceAtMost(99_999),
            lastRecognized = lastRecognized,
            pendingJumpIndex = pendingJump,
            errorMessage = errorMessage,
            voice = voice,
            visual = visual,
            pacing = pacing,
            pacingReason = when {
                !pacing -> ""
                !recognitionAvailable -> "unavailable"
                else -> "stalled"
            },
        )

    private companion object {
        const val HISTORY_TOKENS = 32
        /** Target lead (tokens) over the evidence at which feed-forward reaches zero. */
        const val AHEAD_TAPER_TOKENS = 1.5
        /** Coasting may cover at most this much reading time past the last fix. */
        const val COAST_SECONDS = 1.2
    }
}
