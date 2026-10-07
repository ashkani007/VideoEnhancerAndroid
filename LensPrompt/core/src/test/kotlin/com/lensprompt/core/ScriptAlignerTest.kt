package com.lensprompt.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class ScriptAlignerTest {

    private val config = SmartFollowConfig()
    private val normalizer = TextNormalizer("en")
    private val index = ScriptIndex(TestScripts.MACHINING, normalizer)
    private val aligner = ScriptAligner(index, config)

    private fun q(text: String) = normalizer.tokenize(text).map { it.text }
    private fun pos(word: String, occurrence: Int = 0): Int =
        index.tokens.withIndex().filter { it.value.text == word }[occurrence].index

    @Test
    fun `exact phrase aligns to its last word`() {
        val r = assertNotNull(aligner.align(q("steel enters the cutting zone"), 0, 0, 60))
        assertEquals(pos("zone"), r.endIndex)
        assertTrue(r.confidence > 0.6, "confidence ${r.confidence}")
    }

    @Test
    fun `misrecognized word still aligns`() {
        val r = assertNotNull(aligner.align(q("steel enters the cutting soon and the tool"), 0, 0, 60))
        assertEquals(pos("tool"), r.endIndex)
    }

    @Test
    fun `a single common word does not pull alignment far away`() {
        // Speaker is around "coolant flows"; recognizer hears just "the".
        val here = pos("flows")
        val r = aligner.align(q("the"), here, here - 20, here + 60)
        if (r != null) {
            assertTrue(r.confidence < config.minConfidence, "confidence ${r.confidence} for a lone stop word")
        }
    }

    @Test
    fun `repeated phrase resolves by context and position`() {
        val second = pos("producing")
        val r = assertNotNull(aligner.align(q("slowly the machine starts producing"), pos("slowly"), 0, 80))
        assertEquals(second, r.endIndex)

        // "the machine starts" right after "slowly." — must pick the 2nd occurrence, not the 3rd.
        val r2 = assertNotNull(aligner.align(q("starts slowly the machine starts"), pos("slowly") + 2, 0, 80))
        assertEquals(pos("starts", 1), r2.endIndex)
    }

    @Test
    fun `compound split by recognizer is merged`() {
        val idx = ScriptIndex("We test the everyday workflow of the shop floor", normalizer)
        val al = ScriptAligner(idx, config)
        val r = assertNotNull(al.align(q("we test the every day workflow"), 3, 0, idx.size - 1))
        assertEquals(idx.tokens.indexOfFirst { it.text == "workflow" }, r.endIndex)
    }

    @Test
    fun `persian aligns with or without zwnj`() {
        val fa = TextNormalizer("fa")
        val idx = ScriptIndex(TestScripts.PERSIAN, fa)
        val al = ScriptAligner(idx, config)
        val query = fa.tokenize("فولاد وارد منطقه برش میشود").map { it.text }
        val r = assertNotNull(al.align(query, 0, 0, idx.size - 1))
        assertEquals(4, r.endIndex)
    }
}
