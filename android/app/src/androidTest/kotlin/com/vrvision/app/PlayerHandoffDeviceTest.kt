package com.vrvision.app

import android.net.Uri
import androidx.media3.common.C
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.vrvision.app.player.PlayerController
import com.vrvision.core.browser.MediaKind
import com.vrvision.core.media.PlaybackPhase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** The browser's "Open in VRVision Player" path: Media3 with an explicit MIME type. */
@RunWith(AndroidJUnit4::class)
class PlayerHandoffDeviceTest {

    private val instr get() = InstrumentationRegistry.getInstrumentation()

    @androidx.annotation.OptIn(markerClass = [UnstableApi::class])
    @Test
    fun hlsAndDashAreAvailable() {
        val types = DefaultMediaSourceFactory(instr.targetContext).supportedTypes.toSet()
        assertTrue("HLS module missing", C.CONTENT_TYPE_HLS in types)
        assertTrue("DASH module missing", C.CONTENT_TYPE_DASH in types)
    }

    @Test
    fun handedOffMp4ReachesReady() {
        val ctx = instr.targetContext
        val file = File(ctx.cacheDir, "handoff.mp4")
        instr.context.assets.open("test_sbs.mp4").use { i -> file.outputStream().use { i.copyTo(it) } }
        lateinit var player: PlayerController
        instr.runOnMainSync {
            player = PlayerController(ctx, CoroutineScope(SupervisorJob() + Dispatchers.Main))
            player.load(Uri.fromFile(file), 0, MediaKind.MP4.mime)
        }
        val end = System.currentTimeMillis() + 15_000
        while (System.currentTimeMillis() < end && player.state.value.phase != PlaybackPhase.Ready) Thread.sleep(100)
        assertEquals(PlaybackPhase.Ready, player.state.value.phase)
        assertTrue(player.state.value.durationMs in 900..1200)
        instr.runOnMainSync { player.release() }
    }
}
