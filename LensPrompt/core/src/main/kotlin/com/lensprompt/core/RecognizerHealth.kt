package com.lensprompt.core

/**
 * Decides whether a speech recognizer that was handed LensPrompt's own audio
 * stream (Android's EXTRA_AUDIO_SOURCE) is really using it.
 *
 * EXTRA_AUDIO_SOURCE is optional for recognition services: a service may ignore
 * it and open the microphone itself, which during video recording yields only
 * silence. Restarting such a recognizer forever achieves nothing, so this
 * monitor gives a verdict from two independent observations:
 *  - the service never drains the pipe: written audio piles up and is dropped
 *    because the pipe is full ([Verdict.NOT_READING_AUDIO]);
 *  - the speaker is audibly talking (our own VAD) but no words ever arrive
 *    ([Verdict.NO_WORDS]).
 * Once any result has arrived the recognizer is proven to work ([Verdict.WORKING]);
 * later gaps are normal recognizer behaviour and are left to Smart Follow's own
 * stall handling.
 */
class RecognizerHealthMonitor(
    /** Voiced audio without any recognized word before giving up, ms. */
    private val maxVoicedWithoutWordsMs: Long = 8_000,
    /** Audio dropped because nobody read the pipe before giving up, ms. */
    private val maxUnreadAudioMs: Long = 3_000,
) {
    enum class Verdict { PENDING, WORKING, NOT_READING_AUDIO, NO_WORDS }

    var verdict: Verdict = Verdict.PENDING
        private set

    fun reset() { verdict = Verdict.PENDING }

    /**
     * @param resultsSoFar partial + final results since the route started.
     * @param voicedWithoutWordsMs voiced audio since the last recognized words.
     * @param audioDroppedMs audio dropped because the recognizer's pipe was full.
     * @param audioWrittenMs audio the recognizer actually accepted through the pipe.
     */
    fun update(resultsSoFar: Int, voicedWithoutWordsMs: Long, audioDroppedMs: Long, audioWrittenMs: Long): Verdict {
        if (verdict != Verdict.PENDING) return verdict
        verdict = when {
            resultsSoFar > 0 -> Verdict.WORKING
            // The pipe holds ~2 s of 16 kHz audio; a reader that never drains it
            // means the service is not consuming our stream at all.
            audioDroppedMs >= maxUnreadAudioMs && audioDroppedMs > audioWrittenMs -> Verdict.NOT_READING_AUDIO
            voicedWithoutWordsMs >= maxVoicedWithoutWordsMs -> Verdict.NO_WORDS
            else -> Verdict.PENDING
        }
        return verdict
    }

    companion object {
        fun describe(v: Verdict): String = when (v) {
            Verdict.PENDING -> "checking"
            Verdict.WORKING -> "working"
            Verdict.NOT_READING_AUDIO -> "recognizer does not read LensPrompt's audio (EXTRA_AUDIO_SOURCE ignored)"
            Verdict.NO_WORDS -> "no words from recognizer while you speak"
        }
    }
}

/**
 * Minimal reader for the recognizer JSON Vosk produces:
 * `{"partial" : "…"}` and `{"text" : "…"}`. Handles JSON string escapes,
 * including \uXXXX (Persian text may arrive escaped or as raw UTF-8).
 */
object RecognizerJson {
    fun field(json: String, name: String): String? {
        val key = Regex("\"" + Regex.escape(name) + "\"\\s*:\\s*\"")
        val m = key.find(json) ?: return null
        val sb = StringBuilder()
        var i = m.range.last + 1
        while (i < json.length) {
            val c = json[i]
            when {
                c == '"' -> return sb.toString()
                c == '\\' && i + 1 < json.length -> {
                    when (val e = json[i + 1]) {
                        'n' -> sb.append('\n')
                        't' -> sb.append('\t')
                        'r' -> sb.append('\r')
                        'b' -> sb.append('\b')
                        'f' -> sb.append('\u000C')
                        'u' -> {
                            if (i + 5 < json.length) {
                                json.substring(i + 2, i + 6).toIntOrNull(16)?.let { sb.append(it.toChar()) }
                                i += 4
                            }
                        }
                        else -> sb.append(e)
                    }
                    i += 2
                    continue
                }
                else -> sb.append(c)
            }
            i++
        }
        return null
    }

    fun partial(json: String): String = field(json, "partial").orEmpty().trim()

    fun text(json: String): String = field(json, "text").orEmpty().trim()
}
