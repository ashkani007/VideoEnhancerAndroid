package com.vrvision.app

import androidx.media3.common.MimeTypes
import com.vrvision.core.browser.MediaKind
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/** The MIME types the browser hands to the player must be the ones Media3 recognizes. */
class BrowserHandoffTest {
    @Test fun mediaKindMimesMatchMedia3() {
        assertEquals(MimeTypes.VIDEO_MP4, MediaKind.MP4.mime)
        assertEquals(MimeTypes.VIDEO_WEBM, MediaKind.WEBM.mime)
        assertEquals(MimeTypes.APPLICATION_M3U8, MediaKind.HLS.mime)
        assertEquals(MimeTypes.APPLICATION_MPD, MediaKind.DASH.mime)
        assertNull(MediaKind.BLOB.mime)
    }
}
