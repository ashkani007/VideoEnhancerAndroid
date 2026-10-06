package com.lensprompt.core

/** Timestamped recognizer events, as the Android layer would deliver them. */
sealed class RecognitionEvent {
    abstract val timeMs: Long
    data class SessionStart(override val timeMs: Long) : RecognitionEvent()
    data class Partial(override val timeMs: Long, val text: String) : RecognitionEvent()
    data class Final(override val timeMs: Long, val text: String) : RecognitionEvent()
    data class EndOfSpeech(override val timeMs: Long) : RecognitionEvent()
    data class AudioLevel(override val timeMs: Long, val rmsDb: Float) : RecognitionEvent()
}

/**
 * Builds realistic recognizer event streams from a reading plan, so Smart
 * Follow can be tuned and regression-tested without a microphone.
 *
 * The model: the speaker utters words at given times; the recognizer emits a
 * cumulative partial hypothesis of the current utterance every
 * [partialIntervalMs], lagging speech by [latencyMs]; after a silence longer
 * than [utteranceGapMs] (or [maxUtteranceWords] words) it emits a final result
 * and starts a new session.
 */
class SpeechScenario(
    script: String,
    languageTag: String = "en",
    private val partialIntervalMs: Long = 250,
    private val latencyMs: Long = 300,
    private val utteranceGapMs: Long = 700,
    private val maxUtteranceWords: Int = 30,
    /** Some recognizers report no audio level; set false to test that fallback. */
    private val emitAudioLevels: Boolean = true,
) {
    /** Displayed words of the script (one per distinct source span). */
    val words: List<String>

    init {
        val idx = ScriptIndex(script, TextNormalizer(languageTag))
        val spans = LinkedHashSet<Pair<Int, Int>>()
        for (t in idx.tokens) spans.add(t.start to t.end)
        words = spans.map { script.substring(it.first, it.second) }
    }

    private data class Spoken(val timeMs: Long, val word: String)

    private val spoken = ArrayList<Spoken>()
    private var clock = 0L

    val durationMs: Long get() = clock

    /** Read script words [from, to) at [wordsPerSec]. */
    fun read(from: Int, to: Int, wordsPerSec: Double, substitutions: Map<Int, String> = emptyMap()): SpeechScenario {
        val step = (1000.0 / wordsPerSec).toLong()
        for (i in from until to.coerceAtMost(words.size)) {
            clock += step
            spoken += Spoken(clock, substitutions[i] ?: words[i])
        }
        return this
    }

    /** Read with a speed ramp from [startWps] to [endWps]. */
    fun readRamp(from: Int, to: Int, startWps: Double, endWps: Double): SpeechScenario {
        val n = (to - from).coerceAtLeast(1)
        for (k in 0 until n) {
            val wps = startWps + (endWps - startWps) * k / n
            clock += (1000.0 / wps).toLong()
            spoken += Spoken(clock, words[from + k])
        }
        return this
    }

    /** Say words that are not in the script. */
    fun say(text: String, wordsPerSec: Double): SpeechScenario {
        val step = (1000.0 / wordsPerSec).toLong()
        for (w in text.split(' ').filter { it.isNotBlank() }) {
            clock += step
            spoken += Spoken(clock, w)
        }
        return this
    }

    fun silence(ms: Long): SpeechScenario { clock += ms; return this }

    fun events(): List<RecognitionEvent> {
        val out = ArrayList<RecognitionEvent>()
        if (spoken.isEmpty()) return out
        out += RecognitionEvent.SessionStart(0)
        var utterance = ArrayList<String>()
        var lastEmitted = ""
        var next = 0
        var t = partialIntervalMs
        val end = clock + latencyMs + 2 * partialIntervalMs
        var lastWordTime = 0L
        while (t <= end) {
            // words the recognizer has "heard" by now
            var added = false
            while (next < spoken.size && spoken[next].timeMs + latencyMs <= t) {
                // silence since the previous word → close the utterance first
                if (utterance.isNotEmpty() && spoken[next].timeMs - lastWordTime > utteranceGapMs) {
                    out += RecognitionEvent.EndOfSpeech(lastWordTime + utteranceGapMs / 2 + latencyMs)
                    out += RecognitionEvent.Final(lastWordTime + utteranceGapMs + latencyMs, utterance.joinToString(" "))
                    out += RecognitionEvent.SessionStart(lastWordTime + utteranceGapMs + latencyMs)
                    utterance = ArrayList(); lastEmitted = ""
                }
                utterance += spoken[next].word
                lastWordTime = spoken[next].timeMs
                next++
                added = true
                if (utterance.size >= maxUtteranceWords) {
                    out += RecognitionEvent.Final(t, utterance.joinToString(" "))
                    out += RecognitionEvent.SessionStart(t)
                    utterance = ArrayList(); lastEmitted = ""
                }
            }
            val text = utterance.joinToString(" ")
            if (text.isNotEmpty() && text != lastEmitted) {
                out += RecognitionEvent.Partial(t, text)
                lastEmitted = text
            }
            t += partialIntervalMs
        }
        if (utterance.isNotEmpty()) {
            out += RecognitionEvent.EndOfSpeech(lastWordTime + utteranceGapMs / 2 + latencyMs)
            out += RecognitionEvent.Final(lastWordTime + utteranceGapMs + latencyMs, utterance.joinToString(" "))
        }
        // Real-time audio level (no recognition latency), ~10 Hz like Android's onRmsChanged.
        if (emitAudioLevels) {
            var w = 0
            var lt = 0L
            while (lt <= end) {
                while (w < spoken.size && spoken[w].timeMs < lt - 50) w++
                // a word is being voiced if one ends within the next ~350 ms
                val voiced = w < spoken.size && spoken[w].timeMs <= lt + 350
                out += RecognitionEvent.AudioLevel(lt, if (voiced) 7f else 0f)
                lt += 100
            }
        }
        out.sortBy { it.timeMs }
        return out
    }
}

/** One rendered frame of a simulation. */
data class SimFrame(
    val timeMs: Long,
    val state: FollowState,
    val targetProgress: Double,
    val matchedIndex: Int,
    val confidence: Double,
    val readingVelocity: Double,
    val scrollPx: Double,
    val scrollVelocityPx: Double,
    /** Script progress currently under the reading anchor. */
    val displayedProgress: Double,
)

/**
 * Runs recognizer events through [SmartFollowController] and
 * [TeleprompterScrollController] at a fixed frame rate, exactly as the app's
 * frame loop does, and records every frame.
 */
class SmartFollowSimulator(
    script: String,
    languageTag: String = "en",
    val config: SmartFollowConfig = SmartFollowConfig(),
    private val pxPerToken: Float = 30f,
    private val frameMs: Long = 16,
) {
    val controller = SmartFollowController(script, languageTag, config)
    private val scroll = TeleprompterScrollController(config)
    private val mapper = ProgressMapper.uniform(controller.scriptTokenCount, pxPerToken)

    fun run(events: List<RecognitionEvent>, durationMs: Long, startToken: Int = 0): List<SimFrame> {
        val frames = ArrayList<SimFrame>((durationMs / frameMs).toInt() + 1)
        controller.start(0, startToken)
        scroll.snapTo(mapper.yAt(startToken.toDouble()))
        var e = 0
        var t = 0L
        while (t <= durationMs) {
            while (e < events.size && events[e].timeMs <= t) {
                when (val ev = events[e]) {
                    is RecognitionEvent.SessionStart -> controller.onSessionStart()
                    is RecognitionEvent.Partial -> controller.onPartialResult(ev.text, ev.timeMs)
                    is RecognitionEvent.Final -> controller.onFinalResult(ev.text, ev.timeMs)
                    is RecognitionEvent.EndOfSpeech -> controller.onEndOfSpeech(ev.timeMs)
                    is RecognitionEvent.AudioLevel -> controller.onAudioLevel(ev.rmsDb, ev.timeMs)
                }
                e++
            }
            val out = controller.tick(t)
            val targetPx = mapper.yAt(out.targetProgress)
            val ffPx = out.targetVelocity * mapper.pxPerToken(out.targetProgress)
            val pos = scroll.follow(frameMs / 1000.0, targetPx, ffPx)
            frames += SimFrame(
                timeMs = t,
                state = out.state,
                targetProgress = out.targetProgress,
                matchedIndex = out.matchedIndex,
                confidence = out.confidence,
                readingVelocity = out.readingVelocity,
                scrollPx = pos,
                scrollVelocityPx = scroll.velocity,
                displayedProgress = mapper.progressAt(pos),
            )
            t += frameMs
        }
        return frames
    }
}
