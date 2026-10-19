package com.lensprompt.app

import com.lensprompt.app.diag.Diagnostics
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DiagnosticPrivacyTest {
    @Test
    fun routineLogsDoNotContainSpeechButUserExportRemainsUseful() {
        val previous = Diagnostics.lastResultText
        try {
            Diagnostics.lastResultText = "private sentence about a client"
            assertFalse(Diagnostics.logLine().contains("private sentence"))
            assertTrue(Diagnostics.logLine().contains("LAST RESULT=[redacted]"))
            assertTrue(Diagnostics.text().contains("private sentence about a client"))
            assertTrue(Diagnostics.logLine().contains("RECOGNIZER ENGINE="))
        } finally {
            Diagnostics.lastResultText = previous
        }
    }
}
