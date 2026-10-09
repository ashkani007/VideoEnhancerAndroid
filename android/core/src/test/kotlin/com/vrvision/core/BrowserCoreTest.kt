package com.vrvision.core

import com.vrvision.core.browser.AddressInput
import com.vrvision.core.browser.ControllerAction
import com.vrvision.core.browser.ControllerMap
import com.vrvision.core.browser.DownloadCategory
import com.vrvision.core.browser.DownloadDecision
import com.vrvision.core.browser.DownloadPolicy
import com.vrvision.core.browser.DownloadRequest
import com.vrvision.core.browser.DwellClicker
import com.vrvision.core.browser.MediaCandidate
import com.vrvision.core.browser.MediaDetector
import com.vrvision.core.browser.MediaKind
import com.vrvision.core.browser.MediaOrigin
import com.vrvision.core.browser.NavigationDecision
import com.vrvision.core.browser.TabManager
import com.vrvision.core.browser.TabState
import com.vrvision.core.browser.UrlPolicy
import com.vrvision.core.browser.VirtualScreen
import com.vrvision.core.browser.VrPointer
import com.vrvision.core.math.Quaternion
import com.vrvision.core.math.Vec3
import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.StereoLayout
import java.net.URLEncoder
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class UrlPolicyTest {

    @Test fun typedHostsBecomeHttps() {
        assertEquals(AddressInput.Url("https://example.com"), UrlPolicy.resolveInput("example.com"))
        assertEquals(AddressInput.Url("https://example.com/vr?x=1"), UrlPolicy.resolveInput(" example.com/vr?x=1 "))
        assertEquals(AddressInput.Url("https://localhost:8080/"), UrlPolicy.resolveInput("localhost:8080/"))
    }

    @Test fun httpIsUpgradedFirst() {
        assertEquals(AddressInput.Url("https://example.com/a"), UrlPolicy.resolveInput("http://example.com/a"))
        assertEquals(AddressInput.Url("http://example.com/a"), UrlPolicy.resolveInput("http://example.com/a", allowInsecure = true))
        assertEquals(NavigationDecision.Upgrade("https://site.org/x"), UrlPolicy.decide("http://site.org/x"))
        assertEquals(NavigationDecision.Allow("http://site.org/x"), UrlPolicy.decide("http://site.org/x", setOf("site.org")))
    }

    @Test fun wordsBecomeSearch() {
        val s = assertIs<AddressInput.Search>(UrlPolicy.resolveInput("vr180 hiking video"))
        assertEquals("https://duckduckgo.com/?q=vr180+hiking+video", s.url)
        assertIs<AddressInput.Search>(UrlPolicy.resolveInput("singleword"))
    }

    @Test fun dangerousSchemesAreRejected() {
        for (u in listOf("javascript:alert(1)", "file:///sdcard/x", "content://media/1", "data:text/html,<b>x</b>", "intent://x#Intent;end", "chrome://flags")) {
            assertIs<AddressInput.Rejected>(UrlPolicy.resolveInput(u), u)
            assertIs<NavigationDecision.Block>(UrlPolicy.decide(u), u)
        }
        assertIs<AddressInput.Rejected>(UrlPolicy.resolveInput("https://user:pass@example.com/"))
        assertIs<AddressInput.Rejected>(UrlPolicy.resolveInput("   "))
    }

    @Test fun externalSchemesNeedConfirmation() {
        assertEquals(NavigationDecision.External("tel:123", "tel"), UrlPolicy.decide("tel:123"))
        assertIs<NavigationDecision.External>(UrlPolicy.decide("mailto:a@b.c"))
        assertEquals(NavigationDecision.Allow("about:blank"), UrlPolicy.decide("about:blank"))
    }
}

class TabManagerTest {
    private var next = 1L
    private fun id() = next++

    @Test fun openSelectCloseKeepsAnActiveTab() {
        var s = TabManager.ensureOne(TabState(), ::id)
        assertEquals(1, s.tabs.size); assertEquals(1L, s.activeId)
        s = TabManager.open(s, "https://a.com", id())
        s = TabManager.open(s, "https://b.com", id())
        assertEquals(3L, s.activeId)
        s = TabManager.select(s, 2)
        s = TabManager.close(s, 2) // active closed -> right neighbour
        assertEquals(3L, s.activeId)
        s = TabManager.close(s, 3) // last closed -> left neighbour
        assertEquals(1L, s.activeId)
        s = TabManager.close(s, 1)
        assertNull(s.activeId)
        s = TabManager.ensureOne(s, ::id)
        assertEquals(1, s.tabs.size)
    }

    @Test fun limitAndUpdates() {
        var s = TabState()
        repeat(TabManager.MAX_TABS + 3) { s = TabManager.open(s, "https://x.com/$it", id()) }
        assertEquals(TabManager.MAX_TABS, s.tabs.size)
        assertFalse(TabManager.canOpen(s))
        val t = s.tabs.first()
        s = TabManager.update(s, t.id, title = "Hello")
        assertEquals("Hello", s.tabs.first().title)
        assertEquals(t.url, s.tabs.first().url)
        assertEquals(s, TabManager.select(s, 9999))
        assertEquals(s, TabManager.close(s, 9999))
    }
}

class MediaDetectionTest {

    @Test fun kindsFromExtensionAndMime() {
        assertEquals(MediaKind.MP4, MediaDetector.kindOf("https://cdn.x/v/Trip_VR180_SBS.mp4?token=1"))
        assertEquals(MediaKind.WEBM, MediaDetector.kindOf("https://x/a.webm"))
        assertEquals(MediaKind.HLS, MediaDetector.kindOf("https://x/master.m3u8"))
        assertEquals(MediaKind.DASH, MediaDetector.kindOf("https://x/manifest.mpd"))
        assertEquals(MediaKind.HLS, MediaDetector.kindOf("https://x/play", "application/vnd.apple.mpegurl"))
        assertEquals(MediaKind.MP4, MediaDetector.kindOf("https://x/stream", "video/mp4; codecs=avc1"))
        assertEquals(MediaKind.BLOB, MediaDetector.kindOf("blob:https://x/123"))
        assertEquals(MediaKind.UNKNOWN, MediaDetector.kindOf("https://x/page.html"))
        assertTrue(MediaDetector.isMediaRequest("https://x/seg/master.m3u8"))
        assertFalse(MediaDetector.isMediaRequest("https://x/app.js"))
    }

    private fun e(s: String) = URLEncoder.encode(s, "UTF-8").replace("+", "%20")

    @Test fun parsesScriptOutputAndMerges() {
        val raw = listOf(
            "T\t" + e("Alps 360 TB demo"),
            "V\t" + e("https://cdn.x/alps_360_TB.mp4") + "\t" + e("video/mp4") + "\t0",
            "V\t" + e("https://cdn.x/alps_360_TB.mp4") + "\t\t0",
            "V\t" + e("blob:https://x/abc") + "\t\t1",
            "L\t" + e("https://cdn.x/hls/master.m3u8") + "\t\t0",
        ).joinToString("\n")
        val c = MediaDetector.parseScriptResult(raw, "https://x/page")
        assertEquals(3, c.size)
        val mp4 = c.first { it.kind == MediaKind.MP4 }
        assertEquals("Alps 360 TB demo", mp4.pageTitle)
        assertEquals(MediaOrigin.VIDEO_ELEMENT, mp4.origin)
        assertTrue(c.first { it.kind == MediaKind.BLOB }.drmProtected)
        assertEquals(MediaOrigin.LINK, c.first { it.kind == MediaKind.HLS }.origin)
    }

    @Test fun assessmentsExplainWhy() {
        val mp4 = MediaDetector.assess(MediaCandidate("https://cdn.x/alps_360_TB.mp4", MediaKind.MP4, "https://x"))
        assertTrue(mp4.canPlay); assertTrue(mp4.canEnhance)
        assertEquals(ProjectionType.EQUIRECT_360, mp4.format.projection)
        assertEquals(StereoLayout.TOP_BOTTOM, mp4.format.layout)

        val hls = MediaDetector.assess(MediaCandidate("https://x/master.m3u8", MediaKind.HLS, "https://x"))
        assertTrue(hls.canPlay); assertFalse(hls.canEnhance)
        assertTrue(hls.enhanceReason.contains("Adaptive"))

        val drm = MediaDetector.assess(MediaCandidate("https://x/a.mp4", MediaKind.MP4, "https://x", drmProtected = true))
        assertFalse(drm.canPlay); assertFalse(drm.canEnhance)
        assertTrue(drm.playReason.contains("DRM"))

        assertFalse(MediaDetector.assess(MediaCandidate("blob:https://x/1", MediaKind.BLOB, "https://x")).canPlay)
        assertFalse(MediaDetector.assess(MediaCandidate("http://x/a.mp4", MediaKind.MP4, "http://x")).canPlay)
        val flat = MediaDetector.assess(MediaCandidate("https://x/holiday.mp4", MediaKind.MP4, "https://x"))
        assertEquals(ProjectionType.FLAT, flat.format.projection)
        assertFalse(flat.format.confident)
    }
}

class DownloadPolicyTest {
    private fun req(url: String, mime: String? = null, cd: String? = null, len: Long = 1000, user: Boolean = true) =
        DownloadRequest(url, mime, cd, len, user)

    @Test fun neverAutomatic() {
        assertIs<DownloadDecision.Block>(DownloadPolicy.evaluate(req("https://x/a.mp4", user = false)))
    }

    @Test fun mediaNeedsConfirmationWithDetails() {
        val d = assertIs<DownloadDecision.Confirm>(DownloadPolicy.evaluate(req("https://cdn.x/v/clip%20sbs.mp4", "video/mp4")))
        assertEquals("clip sbs.mp4", d.fileName)
        assertEquals(DownloadCategory.VIDEO, d.category)
        assertEquals("cdn.x", d.host)
        assertTrue(d.warnings.isEmpty())
    }

    @Test fun executablesAndPageMemoryBlocked() {
        assertIs<DownloadDecision.Block>(DownloadPolicy.evaluate(req("https://x/app.apk")))
        assertIs<DownloadDecision.Block>(DownloadPolicy.evaluate(req("https://x/get", "application/vnd.android.package-archive")))
        assertIs<DownloadDecision.Block>(DownloadPolicy.evaluate(req("https://x/f", cd = "attachment; filename=\"setup.exe\"")))
        assertIs<DownloadDecision.Block>(DownloadPolicy.evaluate(req("blob:https://x/1")))
        assertIs<DownloadDecision.Block>(DownloadPolicy.evaluate(req("data:video/mp4;base64,AAAA")))
        assertIs<DownloadDecision.Block>(DownloadPolicy.evaluate(req("https://x/a.mp4", len = DownloadPolicy.MAX_BYTES + 1)))
    }

    @Test fun insecureAndUnknownSizeWarn() {
        val d = assertIs<DownloadDecision.Confirm>(DownloadPolicy.evaluate(req("http://x/a.mp4", len = -1)))
        assertEquals(2, d.warnings.size)
    }

    @Test fun fileNamesAreSanitized() {
        assertEquals("report.pdf", DownloadPolicy.fileName("https://x/dl?id=1", "attachment; filename=\"../../report.pdf\"", null))
        assertEquals("Über clip.mp4", DownloadPolicy.fileName("https://x/dl", "attachment; filename*=UTF-8''%C3%9Cber%20clip.mp4", null))
        assertEquals("video.mp4", DownloadPolicy.fileName("https://x/video", null, "video/mp4"))
        assertEquals("download", DownloadPolicy.fileName("https://x/", null, null))
        assertEquals("evil.txt", DownloadPolicy.sanitize("..\\..\\evil.txt"))
        assertTrue(DownloadPolicy.sanitize("a".repeat(300) + ".mp4").let { it.length <= 120 && it.endsWith(".mp4") })
    }
}

class VrBrowserInteractionTest {

    @Test fun gazeStraightAheadHitsScreenCenter() {
        val hit = assertNotNull(VrPointer.hit(Quaternion.IDENTITY, VirtualScreen(2f, 2.4f, 16f / 9f)))
        assertEquals(0.5f, hit.first, 1e-5f); assertEquals(0.5f, hit.second, 1e-5f)
    }

    @Test fun lookingRightAndUpMovesPointer() {
        val screen = VirtualScreen(2f, 2.4f, 16f / 9f)
        val right = Quaternion.fromAxisAngle(Vec3(0f, 1f, 0f), -0.2f) // yaw right
        assertTrue(VrPointer.hit(right, screen)!!.first > 0.5f)
        val up = Quaternion.fromAxisAngle(Vec3(1f, 0f, 0f), 0.15f) // pitch up
        assertTrue(VrPointer.hit(up, screen)!!.second < 0.5f)
        // Exact: yaw atan(1.2/2) puts the pointer on the right edge (x = 1.2 m at 2 m).
        val edge = Quaternion.fromAxisAngle(Vec3(0f, 1f, 0f), -kotlin.math.atan(1.199f / 2f))
        assertEquals(1f, VrPointer.hit(edge, screen)!!.first, 1e-3f)
    }

    @Test fun lookingAwayHasNoPointer() {
        val screen = VirtualScreen()
        assertNull(VrPointer.hit(Quaternion.fromAxisAngle(Vec3(0f, 1f, 0f), 3.14f), screen))
        assertNull(VrPointer.hit(Quaternion.fromAxisAngle(Vec3(0f, 1f, 0f), 1.2f), screen))
    }

    @Test fun screenConfigIsClamped() {
        val s = VirtualScreen(100f, 0.1f, 9f).validated()
        assertEquals(VirtualScreen.MAX_DISTANCE, s.distanceMeters)
        assertEquals(VirtualScreen.MIN_WIDTH, s.widthMeters)
        assertEquals(3f, s.aspect)
    }

    @Test fun dwellClicksOnceAfterHolding() {
        val d = DwellClicker(dwellMs = 1000, radius = 0.02f)
        assertNull(d.update(0.5f to 0.5f, 0))
        assertNull(d.update(0.505f to 0.5f, 500))
        assertEquals(0.5f, d.progress, 0.01f)
        val click = assertNotNull(d.update(0.505f to 0.505f, 1000))
        assertEquals(0.5f to 0.5f, click)
        assertNull(d.update(0.5f to 0.5f, 3000)) // no repeat while still dwelling
        assertNull(d.update(0.7f to 0.5f, 3100)) // moved: re-arm
        assertNotNull(d.update(0.7f to 0.5f, 4200))
        assertNull(d.update(null, 4300))
        assertEquals(0f, d.progress)
    }

    @Test fun controllerMapping() {
        assertEquals(ControllerAction.CLICK, ControllerMap.action(ControllerMap.KEYCODE_BUTTON_A))
        assertEquals(ControllerAction.CLICK, ControllerMap.action(ControllerMap.KEYCODE_DPAD_CENTER))
        assertEquals(ControllerAction.BACK, ControllerMap.action(ControllerMap.KEYCODE_BUTTON_B))
        assertEquals(ControllerAction.SCROLL_DOWN, ControllerMap.action(ControllerMap.KEYCODE_DPAD_DOWN))
        assertEquals(ControllerAction.RECENTER, ControllerMap.action(ControllerMap.KEYCODE_BUTTON_Y))
        assertNull(ControllerMap.action(24)) // volume keys stay with the system
    }
}
