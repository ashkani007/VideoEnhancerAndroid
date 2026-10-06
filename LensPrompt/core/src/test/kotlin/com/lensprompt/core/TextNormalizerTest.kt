package com.lensprompt.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class TextNormalizerTest {

    private val en = TextNormalizer("en-US")

    @Test
    fun `case punctuation and whitespace are ignored`() {
        val tokens = en.tokenize("  Steel ENTERS,   the cutting-zone!  ").map { it.text }
        assertEquals(listOf("steel", "enters", "the", "cutting", "zone"), tokens)
    }

    @Test
    fun `apostrophes are removed inside words`() {
        assertEquals(listOf("dont", "its"), en.tokenize("Don't it’s").map { it.text })
        assertEquals(listOf("dont"), en.tokenize("don't").map { it.text })
    }

    @Test
    fun `tokens keep original character spans`() {
        val text = "Hello, brave world."
        val tokens = en.tokenize(text)
        assertEquals("brave", text.substring(tokens[1].start, tokens[1].end))
        assertEquals("world", text.substring(tokens[2].start, tokens[2].end))
    }

    @Test
    fun `numbers are spelled so digits match words`() {
        assertEquals(listOf("twenty", "five"), en.tokenize("25").map { it.text })
        assertEquals(listOf("three", "hundred", "twelve"), en.tokenize("312").map { it.text })
        assertEquals(listOf("vijfentwintig"), TextNormalizer("nl").tokenize("25").map { it.text })
    }

    @Test
    fun `accents are folded`() {
        assertEquals(listOf("een", "cafe"), TextNormalizer("nl").tokenize("één café").map { it.text })
    }

    @Test
    fun `persian zwnj arabic letters and digits are unified`() {
        val fa = TextNormalizer("fa-IR")
        // ZWNJ-joined vs plain
        assertEquals(fa.tokenize("می‌خواهم").map { it.text }, fa.tokenize("میخواهم").map { it.text })
        // Arabic yeh/kaf vs Persian yeh/keheh
        assertEquals(fa.tokenize("كتابي").map { it.text }, fa.tokenize("کتابی").map { it.text })
        // Persian digits are spelled in Persian
        assertEquals(listOf("بیست", "و", "پنج"), fa.tokenize("۲۵").map { it.text })
        // harakat removed
        assertEquals(fa.tokenize("کتاب").map { it.text }, fa.tokenize("کِتاب").map { it.text })
    }

    @Test
    fun `persian sentence tokenizes into words`() {
        val fa = TextNormalizer("fa")
        val tokens = fa.tokenize("سلام، امروز درباره‌ی ماشین‌کاری صحبت می‌کنیم.")
        assertEquals(6, tokens.size)
        assertTrue(tokens.all { it.text.isNotEmpty() })
    }

    @Test
    fun `token index lookup by character offset`() {
        val idx = ScriptIndex("one two three", en)
        assertEquals(0, idx.tokenIndexAtChar(0))
        assertEquals(1, idx.tokenIndexAtChar(4))
        assertEquals(2, idx.tokenIndexAtChar(9))
        assertEquals(2, idx.tokenIndexAtChar(100))
    }

    @Test
    fun `similarity tolerates recognizer inflection errors`() {
        assertTrue(TokenSimilarity.similarity("starts", "start") > 0.8)
        assertTrue(TokenSimilarity.similarity("material", "materials") > 0.85)
        assertEquals(0.0, TokenSimilarity.similarity("the", "and"))
        assertEquals(0.0, TokenSimilarity.similarity("in", "on"))
        assertTrue(TokenSimilarity.similarity("pressure", "machine") < 0.5)
    }
}
