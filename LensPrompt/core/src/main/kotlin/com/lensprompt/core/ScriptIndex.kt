package com.lensprompt.core

import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min

/**
 * Normalized, position-mapped view of a script.
 *
 * Token `i` covers characters [Token.start, Token.end) of the displayed text, so
 * an alignment result (a token index) maps straight back to the on-screen text.
 * Each token also carries an informativeness weight: frequent words and
 * function words ("the", "and", "و", "de") carry little evidence, rare content
 * words carry a lot. This is what keeps a common word from yanking the
 * teleprompter to another occurrence elsewhere in the script.
 */
class ScriptIndex(val text: String, val normalizer: TextNormalizer) {

    val tokens: List<Token> = normalizer.tokenize(text)
    val size: Int get() = tokens.size
    val weights: DoubleArray

    init {
        val counts = HashMap<String, Int>(tokens.size)
        for (t in tokens) counts[t.text] = (counts[t.text] ?: 0) + 1
        weights = DoubleArray(tokens.size) { i -> tokenWeight(tokens[i].text, counts[tokens[i].text] ?: 1) }
    }

    fun word(i: Int): String = tokens[i].text

    /** Index of the token containing or following [charOffset]; clamps to the script. */
    fun tokenIndexAtChar(charOffset: Int): Int {
        if (tokens.isEmpty()) return 0
        var lo = 0
        var hi = tokens.size - 1
        while (lo < hi) {
            val mid = (lo + hi) ushr 1
            if (tokens[mid].end <= charOffset) lo = mid + 1 else hi = mid
        }
        return lo
    }

    companion object {
        fun tokenWeight(word: String, occurrences: Int): Double {
            val base = when {
                StopWords.contains(word) -> 0.35
                word.length <= 2 -> 0.45
                word.length == 3 -> 0.75
                else -> 1.0
            }
            val freq = (1.5 / (1.0 + ln(occurrences.toDouble()))).coerceIn(0.4, 1.0)
            return base * freq
        }
    }
}

/** Fuzzy similarity between two normalized tokens, in [0, 1]. */
object TokenSimilarity {

    fun similarity(a: String, b: String): Double {
        if (a == b) return 1.0
        val la = a.length
        val lb = b.length
        if (la == 0 || lb == 0) return 0.0
        val longest = max(la, lb)
        // Very short words must match exactly: "a"/"an"/"in" are too easy to confuse.
        if (min(la, lb) <= 2) return 0.0
        // Cheap rejection before the edit-distance computation.
        if (abs(la - lb).toDouble() / longest > 0.4) return 0.0
        val d = levenshtein(a, b, maxDistance = (longest * 0.45).toInt() + 1)
        val sim = 1.0 - d.toDouble() / longest
        // Shared prefix is a strong hint for recognizer inflection errors ("start"/"starts").
        val prefixBonus = if (a[0] == b[0] && a[1] == b[1]) 0.05 else 0.0
        return (sim + prefixBonus).coerceIn(0.0, 0.99)
    }

    /** Edit distance with an early exit once [maxDistance] is exceeded. */
    fun levenshtein(a: String, b: String, maxDistance: Int = Int.MAX_VALUE): Int {
        val n = b.length
        var prev = IntArray(n + 1) { it }
        var cur = IntArray(n + 1)
        for (i in 1..a.length) {
            cur[0] = i
            var rowMin = cur[0]
            val ca = a[i - 1]
            for (j in 1..n) {
                val cost = if (ca == b[j - 1]) 0 else 1
                val v = min(min(cur[j - 1] + 1, prev[j] + 1), prev[j - 1] + cost)
                cur[j] = v
                if (v < rowMin) rowMin = v
            }
            if (rowMin > maxDistance) return maxDistance + 1
            val t = prev; prev = cur; cur = t
        }
        return prev[n]
    }
}

/** Small function-word lists. They only lower weights; they never block a match. */
object StopWords {
    private val words = hashSetOf(
        // English
        "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at", "by", "for", "with",
        "is", "are", "was", "were", "be", "been", "it", "its", "this", "that", "these", "those",
        "as", "so", "if", "then", "than", "we", "you", "i", "he", "she", "they", "our", "your",
        "my", "me", "us", "do", "does", "did", "not", "no", "from", "up", "out", "into", "can",
        "will", "just", "have", "has", "had", "there", "here", "what", "which", "who", "how",
        // Dutch
        "de", "het", "een", "en", "of", "maar", "te", "van", "op", "aan", "bij", "voor", "met",
        "is", "zijn", "was", "waren", "dit", "dat", "die", "deze", "als", "dan", "wij", "we",
        "jij", "je", "u", "ik", "hij", "zij", "ze", "niet", "geen", "naar", "er", "om", "ook",
        // Persian (normalized: Persian yeh/keheh, no ZWNJ)
        "و", "در", "به", "از", "که", "این", "را", "با", "برای", "تا", "یا", "هم", "است",
        "بود", "شد", "می", "ما", "من", "تو", "او", "شما", "ان", "یک",
    )

    fun contains(word: String) = word in words
}
