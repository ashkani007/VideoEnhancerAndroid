package com.vrvision.app

import android.app.Application
import android.webkit.WebSettings
import android.webkit.WebView
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.vrvision.app.browser.BrowserController
import com.vrvision.app.browser.BrowserDatabase
import com.vrvision.app.browser.WebViewSecurity
import com.vrvision.core.browser.MediaKind
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** Real WebView on the device: security settings, navigation rules, tabs, media detection, session, clearing. */
@RunWith(AndroidJUnit4::class)
class BrowserDeviceTest {

    private val instr get() = InstrumentationRegistry.getInstrumentation()
    private val app get() = instr.targetContext.applicationContext as Application
    private lateinit var db: BrowserDatabase
    private lateinit var browser: BrowserController

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(app, BrowserDatabase::class.java).allowMainThreadQueries().build()
        browser = BrowserController(app, db.dao(), CoroutineScope(SupervisorJob() + Dispatchers.IO)) { "https://search.example/?q=%s" }
        runBlocking { browser.restore(restoreSession = false) }
    }

    @After
    fun tearDown() {
        instr.runOnMainSync { browser.tabs.value.tabs.forEach { browser.close(it.id) } }
        db.close()
    }

    private fun <T> main(block: () -> T): T { var r: T? = null; instr.runOnMainSync { r = block() }; @Suppress("UNCHECKED_CAST") return r as T }

    private fun waitFor(timeoutMs: Long = 15_000, cond: () -> Boolean) {
        val end = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < end) { if (cond()) return; Thread.sleep(100) }
        throw AssertionError("Condition not met within $timeoutMs ms")
    }

    @Test
    fun webViewIsHardened() {
        main {
            val wv = WebView(app)
            WebViewSecurity.configure(wv)
            val s = wv.settings
            assertFalse(s.allowFileAccess)
            assertFalse(s.allowContentAccess)
            @Suppress("DEPRECATION") assertFalse(s.allowUniversalAccessFromFileURLs)
            @Suppress("DEPRECATION") assertFalse(s.allowFileAccessFromFileURLs)
            assertEquals(WebSettings.MIXED_CONTENT_NEVER_ALLOW, s.mixedContentMode)
            assertTrue(s.safeBrowsingEnabled)
            assertFalse(s.javaScriptCanOpenWindowsAutomatically)
            assertTrue(s.mediaPlaybackRequiresUserGesture)
            wv.destroy()
        }
        // Tabs created by the controller use the same configuration.
        main {
            val wv = browser.webView(browser.activeId!!)
            assertFalse(wv.settings.allowFileAccess)
            assertEquals(WebSettings.MIXED_CONTENT_NEVER_ALLOW, wv.settings.mixedContentMode)
        }
    }

    @Test
    fun dangerousAddressesAreRejectedAndSearchWorks() {
        main {
            assertNotNull(browser.submit("javascript:alert(document.cookie)"))
            assertNotNull(browser.submit("file:///sdcard/Download/x.html"))
            assertNotNull(browser.submit("content://com.android.contacts/contacts"))
            assertNotNull(browser.submit("intent://scan#Intent;scheme=zxing;end"))
            assertNull(browser.submit("vr180 hiking"))
        }
    }

    @Test
    fun tabLifecycle() {
        main {
            assertEquals(1, browser.tabs.value.tabs.size)
            assertTrue(browser.newTab("https://example.org/"))
            assertEquals(2, browser.tabs.value.tabs.size)
            val second = browser.activeId!!
            browser.close(second)
            assertEquals(1, browser.tabs.value.tabs.size)
            browser.close(browser.activeId!!)
            assertEquals("a tab always remains", 1, browser.tabs.value.tabs.size)
        }
    }

    @Test
    fun detectsVideosOnARealPage() {
        val html = """
            <html><head><title>Alps VR180 SBS demo</title></head><body>
            <video id="v" src="media/alps_vr180_sbs.mp4" preload="none"></video>
            <video preload="none"><source src="media/clip.webm" type="video/webm"></video>
            <a href="https://cdn.example.test/live/master.m3u8">Live (HLS)</a>
            <a href="/about">About</a>
            </body></html>
        """.trimIndent()
        val id = main { browser.activeId!! }
        main { browser.webView(id).loadDataWithBaseURL("https://vrvision.test/page/", html, "text/html", "utf-8", null) }
        waitFor { browser.ui.value[id]?.media?.size == 3 }
        val media = browser.ui.value[id]!!.media
        val mp4 = media.first { it.kind == MediaKind.MP4 }
        assertEquals("https://vrvision.test/page/media/alps_vr180_sbs.mp4", mp4.url)
        assertEquals("Alps VR180 SBS demo", mp4.pageTitle)
        assertTrue(media.any { it.kind == MediaKind.WEBM })
        assertTrue(media.any { it.kind == MediaKind.HLS && it.url.endsWith("master.m3u8") })
        assertFalse(media.any { it.drmProtected })
    }

    @Test
    fun sessionIsSavedAndBrowsingDataCleared(): Unit = runBlocking {
        val id = main { browser.activeId!! }
        main { browser.webView(id).loadDataWithBaseURL("https://vrvision.test/", "<title>T</title>", "text/html", "utf-8", null) }
        waitFor { runBlocking { db.dao().sessionTabs() }.any { it.url.startsWith("https://vrvision.test") } }
        browser.clearBrowsingData()
        assertTrue(db.dao().sessionTabs().isEmpty())
    }
}
