package com.lensprompt.core

import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * One alignment measurement: where the end of the recently spoken words most
 * likely sits in the script.
 */
data class AlignmentResult(
    /** Script token index aligned with the last spoken token. */
    val endIndex: Int,
    /** Raw alignment score (before the distance prior). */
    val rawScore: Double,
    /** Score after the distance prior; used to rank candidates. */
    val adjustedScore: Double,
    /** 0 = no idea, 1 = certain. */
    val confidence: Double,
    /** Number of recognized tokens matched to script tokens on the best path. */
    val matchedTokens: Int,
    /** Sum of informativeness weights of the matched script tokens. */
    val matchedWeight: Double,
    /** End index of the best competing candidate elsewhere in the window, or -1. */
    val runnerUpIndex: Int,
)

/**
 * Weighted local sequence alignment of recognized speech against the script.
 *
 * The query is the last few recognized words. Each script position in the
 * search window is scored by a Smith-Waterman style dynamic program:
 *  - match: +matchScore * weight(script word) * similarity
 *  - mismatch / inserted word / skipped script word: penalties
 *  - split / merge: "every day" ↔ "everyday", "می خواهم" ↔ "میخواهم"
 * The alignment must end at (or within two tokens of) the newest recognized word,
 * because we want the speaker's *current* position. A distance prior then prefers
 * positions near where the speaker is expected to be, so repeated phrases and
 * common words do not cause jumps. Confidence combines how much of the query is
 * explained, how much informative evidence was matched and how clearly the best
 * candidate beats its competitors.
 *
 * Not thread-safe: buffers are reused between calls to avoid per-event allocation.
 */
class ScriptAligner(private val index: ScriptIndex, private val config: SmartFollowConfig) {

    private var h = DoubleArray(0)
    private var matches = IntArray(0)
    private var weightSum = DoubleArray(0)
    private var simCache = DoubleArray(0)

    /**
     * @param query normalized recognized tokens, oldest first.
     * @param expected script index where the last query token is expected to be.
     * @param windowStart first script index searched (inclusive).
     * @param windowEnd last script index searched (inclusive).
     */
    fun align(query: List<String>, expected: Int, windowStart: Int, windowEnd: Int): AlignmentResult? {
        if (query.isEmpty() || index.size == 0) return null
        val a = windowStart.coerceIn(0, index.size - 1)
        val b = windowEnd.coerceIn(a, index.size - 1)
        val m = query.size
        val n = b - a + 1
        val cols = n + 1
        ensureCapacity((m + 1) * cols, m * n)

        // Similarity of each query token to each window token, computed once.
        for (i in 0 until m) {
            val q = query[i]
            for (j in 0 until n) simCache[i * n + j] = TokenSimilarity.similarity(q, index.word(a + j))
        }

        java.util.Arrays.fill(h, 0, (m + 1) * cols, 0.0)
        java.util.Arrays.fill(matches, 0, (m + 1) * cols, 0)
        java.util.Arrays.fill(weightSum, 0, (m + 1) * cols, 0.0)

        val minSim = config.minTokenSimilarity
        for (i in 1..m) {
            for (j in 1..n) {
                val sIdx = a + j - 1
                val w = index.weights[sIdx]
                var best = 0.0
                var bestMatches = 0
                var bestWeight = 0.0

                // diagonal: match or mismatch
                val sim = simCache[(i - 1) * n + (j - 1)]
                val d = (i - 1) * cols + (j - 1)
                if (sim >= minSim) {
                    val v = h[d] + config.matchScore * w * sim
                    if (v > best) { best = v; bestMatches = matches[d] + 1; bestWeight = weightSum[d] + w }
                } else {
                    val v = h[d] - config.mismatchPenalty
                    if (v > best) { best = v; bestMatches = matches[d]; bestWeight = weightSum[d] }
                }
                // insertion: recognized word not in script
                val up = (i - 1) * cols + j
                val ins = h[up] - config.insertionPenalty
                if (ins > best) { best = ins; bestMatches = matches[up]; bestWeight = weightSum[up] }
                // deletion: script word skipped by the speaker (cheap for function words)
                val left = i * cols + (j - 1)
                val del = h[left] - config.deletionPenalty * (0.5 + 0.5 * w)
                if (del > best) { best = del; bestMatches = matches[left]; bestWeight = weightSum[left] }
                // merge: two recognized tokens form one script word
                if (i >= 2) {
                    val ms = TokenSimilarity.similarity(query[i - 2] + query[i - 1], index.word(sIdx))
                    if (ms >= minSim) {
                        val p = (i - 2) * cols + (j - 1)
                        val v = h[p] + config.matchScore * w * ms
                        if (v > best) { best = v; bestMatches = matches[p] + 1; bestWeight = weightSum[p] + w }
                    }
                }
                // split: one recognized token covers two script words
                if (j >= 2) {
                    val ss = TokenSimilarity.similarity(query[i - 1], index.word(sIdx - 1) + index.word(sIdx))
                    if (ss >= minSim) {
                        val p = (i - 1) * cols + (j - 2)
                        val w2 = (w + index.weights[sIdx - 1])
                        val v = h[p] + config.matchScore * w2 * ss * 0.75
                        if (v > best) { best = v; bestMatches = matches[p] + 2; bestWeight = weightSum[p] + w2 }
                    }
                }
                val c = i * cols + j
                h[c] = best
                matches[c] = bestMatches
                weightSum[c] = bestWeight
            }
        }

        // Candidates: alignments ending at the newest token, or with <=2 trailing unmatched tokens.
        var bestEnd = -1
        var bestAdj = Double.NEGATIVE_INFINITY
        var bestRaw = 0.0
        var bestMatches = 0
        var bestWeight = 0.0
        val endScores = DoubleArray(n) { Double.NEGATIVE_INFINITY }
        for (trailing in 0..min(2, m - 1)) {
            val i = m - trailing
            for (j in 1..n) {
                val c = i * cols + j
                if (matches[c] == 0) continue
                // the alignment must actually end on a matched script token
                if (simCache[(i - 1) * n + (j - 1)] < minSim && !endsOnMerge(query, i, a + j - 1, minSim)) continue
                val raw = h[c] - trailing * config.trailingUnmatchedPenalty
                if (raw <= 0.0) continue
                val adj = raw - distancePenalty(a + j - 1, expected)
                if (adj > endScores[j - 1]) endScores[j - 1] = adj
                if (adj > bestAdj) {
                    bestAdj = adj; bestEnd = a + j - 1; bestRaw = raw
                    bestMatches = matches[c]; bestWeight = weightSum[c]
                }
            }
        }
        if (bestEnd < 0) return null

        // Strongest competitor that is not just a neighbour of the winner.
        var runnerUp = -1
        var runnerAdj = Double.NEGATIVE_INFINITY
        for (j in 0 until n) {
            if (kotlin.math.abs(a + j - bestEnd) <= config.reacquireAgreementTokens) continue
            if (endScores[j] > runnerAdj) { runnerAdj = endScores[j]; runnerUp = a + j }
        }

        val quality = (bestRaw / (config.matchScore * m)).coerceIn(0.0, 1.0)
        val evidence = 1.0 - exp(-bestWeight / 2.0)
        val margin = if (runnerUp < 0) 1.0 else ((bestAdj - runnerAdj) / config.matchScore).coerceIn(0.0, 1.0)
        val confidence = (sqrt(quality) * evidence * (0.75 + 0.25 * margin)).coerceIn(0.0, 1.0)

        return AlignmentResult(
            endIndex = bestEnd,
            rawScore = bestRaw,
            adjustedScore = bestAdj,
            confidence = confidence,
            matchedTokens = bestMatches,
            matchedWeight = bestWeight,
            runnerUpIndex = runnerUp,
        )
    }

    private fun endsOnMerge(query: List<String>, i: Int, sIdx: Int, minSim: Double): Boolean {
        if (i >= 2 && TokenSimilarity.similarity(query[i - 2] + query[i - 1], index.word(sIdx)) >= minSim) return true
        if (sIdx >= 1 && TokenSimilarity.similarity(query[i - 1], index.word(sIdx - 1) + index.word(sIdx)) >= minSim) return true
        return false
    }

    /** Prior: positions far from where the speaker should be are less likely. */
    private fun distancePenalty(pos: Int, expected: Int): Double {
        val d = pos - expected
        return if (d >= 0) {
            // A few tokens ahead are free: recognition arrives in bursts.
            max(0, d - 3) * config.forwardDistancePenalty
        } else {
            -d * config.backwardDistancePenalty
        }
    }

    private fun ensureCapacity(cells: Int, simCells: Int) {
        if (h.size < cells) {
            h = DoubleArray(cells)
            matches = IntArray(cells)
            weightSum = DoubleArray(cells)
        }
        if (simCache.size < simCells) simCache = DoubleArray(simCells)
    }
}
