package com.lensprompt.core

import com.lensprompt.core.RecognizerHealthMonitor.Verdict
import kotlin.test.Test
import kotlin.test.assertEquals

class RecognizerHealthTest {

    @Test
    fun anyResultProvesTheRecognizerWorks() {
        val m = RecognizerHealthMonitor()
        assertEquals(Verdict.PENDING, m.update(0, 2_000, 0, 2_000))
        assertEquals(Verdict.WORKING, m.update(1, 0, 0, 3_000))
        // Sticky: later silence does not undo the proof.
        assertEquals(Verdict.WORKING, m.update(1, 20_000, 10_000, 3_000))
    }

    @Test
    fun recognizerThatNeverReadsThePipeIsDetected() {
        val m = RecognizerHealthMonitor()
        // ~2 s accepted by the pipe buffer, then everything is dropped.
        assertEquals(Verdict.PENDING, m.update(0, 0, 1_000, 2_000))
        assertEquals(Verdict.NOT_READING_AUDIO, m.update(0, 0, 3_500, 2_000))
    }

    @Test
    fun voicedSpeechWithoutWordsIsDetected() {
        val m = RecognizerHealthMonitor()
        assertEquals(Verdict.PENDING, m.update(0, 7_000, 0, 20_000))
        assertEquals(Verdict.NO_WORDS, m.update(0, 8_000, 0, 21_000))
    }

    @Test
    fun silenceAloneNeverCondemnsTheRecognizer() {
        val m = RecognizerHealthMonitor()
        repeat(100) { assertEquals(Verdict.PENDING, m.update(0, 0, 0, it * 1_000L)) }
    }

    @Test
    fun parsesVoskJson() {
        assertEquals("hello world", RecognizerJson.partial("{\n  \"partial\" : \"hello world\"\n}"))
        assertEquals("the end", RecognizerJson.text("{\n  \"text\" : \"the end\"\n}"))
        assertEquals("", RecognizerJson.partial("{\n  \"partial\" : \"\"\n}"))
        assertEquals("", RecognizerJson.text("{}"))
        assertEquals("سلام دنیا", RecognizerJson.text("{\"text\" : \"\\u0633\\u0644\\u0627\\u0645 دنیا\"}"))
        assertEquals("a \"q\" b", RecognizerJson.text("{\"text\":\"a \\\"q\\\" b\"}"))
        // Result JSON with word details still yields the text field.
        assertEquals("go", RecognizerJson.text("{\"result\":[{\"conf\":1.0,\"word\":\"go\"}],\"text\":\"go\"}"))
    }
}
