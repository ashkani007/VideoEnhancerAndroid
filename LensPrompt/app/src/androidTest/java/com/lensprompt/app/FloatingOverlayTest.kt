package com.lensprompt.app

import android.accessibilityservice.AccessibilityServiceInfo
import android.graphics.Bitmap
import android.view.accessibility.AccessibilityNodeInfo
import android.graphics.Canvas
import android.graphics.Color
import android.os.Build
import android.os.SystemClock
import android.util.Log
import android.view.View
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.lensprompt.app.overlay.OverlayService
import com.lensprompt.app.overlay.OverlaySettingsPanel
import com.lensprompt.app.overlay.ScriptViewport
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The floating teleprompter's layout on a real Android view stack:
 * the script viewport never draws outside its bounds, reflows when the window
 * width or the font changes, and can show the whole script; the settings panel
 * builds; the overlay service starts and draws its window.
 */
@RunWith(AndroidJUnit4::class)
class FloatingOverlayTest {

    private val instr = InstrumentationRegistry.getInstrumentation()
    private val context = instr.targetContext

    private val longScript = (1..60).joinToString(" ") { "Sentence number $it of a long teleprompter script that must wrap." }

    private fun layoutView(v: View, w: Int, h: Int) {
        v.measure(View.MeasureSpec.makeMeasureSpec(w, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(h, View.MeasureSpec.EXACTLY))
        v.layout(0, 0, w, h)
    }

    /**
     * Rows of [bmp] at or below [fromY] that contain any drawn pixel, ignoring
     * the reading marker on the left edge (text starts after a 12 dp padding).
     */
    private fun drawnRowsFrom(bmp: Bitmap, fromY: Int): Int {
        val xFrom = (8 * context.resources.displayMetrics.density).toInt()
        var rows = 0
        for (y in fromY until bmp.height) {
            for (x in xFrom until bmp.width) if (Color.alpha(bmp.getPixel(x, y)) != 0) { rows++; break }
        }
        return rows
    }

    @Test
    fun textNeverRendersOutsideTheViewportAndReflows() {
        instr.runOnMainSync {
            val v = ScriptViewport(context).apply { textSizeSp = 28f; text = longScript }
            layoutView(v, 600, 300)
            val layout = v.textLayout!!
            assertTrue("script must be longer than the viewport", layout.height > 300)

            // Draw into a canvas twice as tall as the view: nothing may appear below it.
            val bmp = Bitmap.createBitmap(600, 600, Bitmap.Config.ARGB_8888)
            v.draw(Canvas(bmp))
            assertEquals("text drawn outside the viewport", 0, drawnRowsFrom(bmp, 300))
            assertTrue("nothing drawn inside the viewport", drawnRowsFrom(bmp, 0) > 0)

            // Narrower window → more lines (reflow), and the reflow callback fires.
            var reflows = 0
            v.onReflow = { reflows++ }
            val wideLines = layout.lineCount
            layoutView(v, 300, 300)
            assertTrue("narrower width must wrap into more lines", v.textLayout!!.lineCount > wideLines)
            assertTrue(reflows >= 1)

            // Larger font → reflow too.
            val before = v.textLayout!!.lineCount
            v.textSizeSp = 56f
            assertTrue("larger font must wrap into more lines", v.textLayout!!.lineCount > before)

            // Scrolled to the end, the last line is drawn inside the viewport.
            v.scrollPx = v.textLayout!!.getLineTop(v.textLayout!!.lineCount - 1).toFloat()
            val end = Bitmap.createBitmap(300, 600, Bitmap.Config.ARGB_8888)
            v.draw(Canvas(end))
            assertTrue("last line not visible", drawnRowsFrom(end, 0) - drawnRowsFrom(end, 300) > 0)
            assertEquals(0, drawnRowsFrom(end, 300))
        }
    }

    @Test
    fun settingsPanelBuilds() {
        instr.runOnMainSync {
            val calls = mutableListOf<String>()
            val cb = object : OverlaySettingsPanel.Callbacks {
                override fun onFontSize(sp: Float) { calls += "font" }
                override fun onLineSpacing(mult: Float) = Unit
                override fun onBackgroundOpacity(v: Float) = Unit
                override fun onTextOpacity(v: Float) = Unit
                override fun onWidth(px: Int) = Unit
                override fun onHeight(px: Int) = Unit
                override fun onSizeChangeFinished() = Unit
                override fun onManualSpeed(v: Float) = Unit
                override fun onSmartFollow(on: Boolean) = Unit
                override fun onAlignCenter(on: Boolean) = Unit
                override fun onMirror(on: Boolean) = Unit
                override fun onLock(on: Boolean) = Unit
                override fun onAutoHide(on: Boolean) = Unit
                override fun onPreset(preset: OverlaySettingsPanel.Preset) = Unit
                override fun onBackToStart() = Unit
                override fun onOpenCamera() = Unit
                override fun onCloseTeleprompter() = Unit
                override fun onDone() = Unit
            }
            val panel = OverlaySettingsPanel(context, cb)
            val view = panel.build(
                OverlaySettingsPanel.Values(
                    fontSp = 28f, lineSpacing = 1.25f, backgroundOpacity = 0.6f, textOpacity = 1f,
                    width = 800, height = 400, minWidth = 300, minHeight = 200, maxWidth = 1080, maxHeight = 2200,
                    manualSpeed = 4f, smartFollow = true, alignCenter = false, mirror = false, locked = false, autoHide = true,
                ),
            )
            layoutView(view, 800, 1200)
            panel.showSize(500, 300)
            assertTrue(view.height > 0)
        }
    }

    @Test
    fun overlayServiceShowsItsWindow() {
        val pkg = context.packageName
        fun shell(cmd: String) = instr.uiAutomation.executeShellCommand(cmd).close()
        shell("appops set $pkg SYSTEM_ALERT_WINDOW allow")
        shell("pm grant $pkg android.permission.RECORD_AUDIO")
        if (Build.VERSION.SDK_INT >= 33) shell("pm grant $pkg android.permission.POST_NOTIFICATIONS")
        SystemClock.sleep(500)
        assumeTrue("overlay permission not granted on this image", OverlayService.canDrawOverlays(context))

        val app = context.applicationContext as LensPromptApplication
        // Let the repository finish its first (async) load, which seeds the welcome
        // script; creating a script earlier would suppress that seeding and leave
        // the library empty for the other tests.
        val loadDeadline = SystemClock.uptimeMillis() + 5_000
        while (app.scripts.scripts.value.isEmpty() && SystemClock.uptimeMillis() < loadDeadline) SystemClock.sleep(50)
        val script = app.scripts.create("Overlay test", longScript)
        try {
            try {
                OverlayService.start(context, script.id)
            } catch (e: Exception) {
                // Android 12+ may refuse a foreground-service start from a test process
                // that is not in the foreground; that is not what this test checks.
                Log.w("FloatingOverlayTest", "service start refused", e)
                assumeTrue("foreground service start not allowed here: ${e.javaClass.simpleName}", false)
            }
            val deadline = SystemClock.uptimeMillis() + 5_000
            while (!OverlayService.running && SystemClock.uptimeMillis() < deadline) SystemClock.sleep(100)
            assertTrue("overlay service did not start", OverlayService.running)
            SystemClock.sleep(1_500) // window added, script laid out, first frames drawn
            assertTrue("overlay service stopped (crash or refused window)", OverlayService.running)
        } finally {
            OverlayService.stop(context)
            SystemClock.sleep(500)
            app.scripts.delete(script.id)
        }
    }

    // ------------------------------------------------------------ exit paths

    private fun grantOverlayPermissions() {
        val pkg = context.packageName
        fun shell(cmd: String) = instr.uiAutomation.executeShellCommand(cmd).close()
        shell("appops set $pkg SYSTEM_ALERT_WINDOW allow")
        shell("pm grant $pkg android.permission.RECORD_AUDIO")
        if (Build.VERSION.SDK_INT >= 33) shell("pm grant $pkg android.permission.POST_NOTIFICATIONS")
        SystemClock.sleep(300)
        assumeTrue("overlay permission not granted on this image", OverlayService.canDrawOverlays(context))
    }

    private fun waitFor(timeoutMs: Long, cond: () -> Boolean): Boolean {
        val end = SystemClock.uptimeMillis() + timeoutMs
        while (!cond() && SystemClock.uptimeMillis() < end) SystemClock.sleep(50)
        return cond()
    }

    private fun startOverlay() {
        try {
            OverlayService.start(context)
        } catch (e: Exception) {
            assumeTrue("foreground service start not allowed here: ${e.javaClass.simpleName}", false)
        }
        assertTrue("overlay did not start", waitFor(5_000) { OverlayService.running })
        SystemClock.sleep(600) // window added and laid out
    }

    /**
     * Clicks the overlay view with this content description, via accessibility
     * (like a user tap). Waits up to [timeoutMs] for it to appear: on a loaded
     * device the overlay's accessibility tree is published a little after the
     * window is added.
     */
    private fun clickOverlay(description: String, timeoutMs: Long = 2_500): Boolean {
        val ua = instr.uiAutomation
        val info = ua.serviceInfo
        info.flags = info.flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
        ua.serviceInfo = info
        val end = SystemClock.uptimeMillis() + timeoutMs
        do {
            for (w in ua.windows) {
                val node = w.root?.findAccessibilityNodeInfosByText(description)
                    ?.firstOrNull { it.contentDescription?.toString() == description && it.isVisibleToUser } ?: continue
                return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            }
            SystemClock.sleep(100)
        } while (SystemClock.uptimeMillis() < end)
        return false
    }

    private fun overlayWindowCount(): Int =
        instr.uiAutomation.windows.count { w -> w.root?.packageName == context.packageName }

    @Test
    fun everyExitPathClosesTheOverlayAndItRestarts() {
        grantOverlayPermissions()
        try {
            // 1. × on the overlay (revealing auto-hidden controls first if needed).
            startOverlay()
            if (!clickOverlay("Close floating teleprompter")) {
                assertTrue("no controls handle", clickOverlay("Show teleprompter controls; drag to move"))
                SystemClock.sleep(400)
                assertTrue("× not found", clickOverlay("Close floating teleprompter"))
            }
            assertTrue("× did not close the overlay", waitFor(3_000) { !OverlayService.running })
            assertTrue("LensPrompt banner state not cleared", !OverlayService.runningState.value)
            assertTrue("an overlay window remained", waitFor(2_000) { overlayWindowCount() == 0 })

            // 2. Locked → 🔒 → [UNLOCK | ×] → ×.
            startOverlay()
            if (!clickOverlay("Lock the teleprompter")) {
                assertTrue("no controls handle", clickOverlay("Show teleprompter controls; drag to move"))
                SystemClock.sleep(400)
                assertTrue("lock button missing", clickOverlay("Lock the teleprompter"))
            }
            SystemClock.sleep(500)
            assertTrue("lock badge missing", clickOverlay("Locked. Tap for Unlock and Close"))
            SystemClock.sleep(400)
            assertTrue("× in lock strip missing", clickOverlay("Close floating teleprompter"))
            assertTrue("lock-strip × did not close", waitFor(3_000) { !OverlayService.running })
            (context.applicationContext as LensPromptApplication).settings.update { it.copy(overlayLocked = false) }

            // 3. "Stop teleprompter" from the notification (same intent the action sends).
            startOverlay()
            context.startService(android.content.Intent(context, OverlayService::class.java).setAction(OverlayService.ACTION_STOP))
            assertTrue("notification stop did not close", waitFor(3_000) { !OverlayService.running })
            assertTrue("an overlay window remained", waitFor(2_000) { overlayWindowCount() == 0 })

            // 4. "Stop floating mode" inside LensPrompt.
            startOverlay()
            OverlayService.stop(context)
            assertTrue("in-app stop did not close", waitFor(3_000) { !OverlayService.running })
            assertTrue("an overlay window remained", waitFor(2_000) { overlayWindowCount() == 0 })

            // 5. And it starts normally again.
            startOverlay()
        } finally {
            OverlayService.stop(context)
            waitFor(3_000) { !OverlayService.running }
            (context.applicationContext as LensPromptApplication).settings.update { it.copy(overlayLocked = false) }
        }
    }
}
