package com.vrvision.core

import com.vrvision.core.media.MediaEvent
import com.vrvision.core.media.MediaReducer
import com.vrvision.core.media.MediaState
import com.vrvision.core.media.PlaybackErrorClassifier
import com.vrvision.core.media.PlaybackErrorKind
import com.vrvision.core.media.PlaybackPhase
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class MediaStateTest {

    private fun run(vararg events: MediaEvent): MediaState =
        events.fold(MediaState()) { s, e -> MediaReducer.reduce(s, e) }

    @Test fun normalLifecycle() {
        val s = run(MediaEvent.Load, MediaEvent.Prepared(60_000, hasSubtitles = false), MediaEvent.Play)
        assertEquals(PlaybackPhase.Ready, s.phase)
        assertTrue(s.isPlaying)
        assertTrue(s.keepScreenOn)
        val paused = MediaReducer.reduce(s, MediaEvent.Pause)
        assertFalse(paused.isPlaying)
        assertFalse(paused.keepScreenOn)
    }

    @Test fun seekIsClampedToDuration() {
        val s = run(MediaEvent.Load, MediaEvent.Prepared(10_000, false))
        assertEquals(10_000, MediaReducer.reduce(s, MediaEvent.SeekTo(99_000)).positionMs)
        assertEquals(0, MediaReducer.reduce(s, MediaEvent.SeekBy(-5_000)).positionMs)
        assertEquals(4_000, MediaReducer.reduce(MediaReducer.reduce(s, MediaEvent.SeekTo(9_000)), MediaEvent.SeekBy(-5_000)).positionMs)
    }

    @Test fun seekIgnoredBeforePrepared() {
        val s = run(MediaEvent.Load, MediaEvent.SeekTo(5_000))
        assertEquals(0, s.positionMs)
    }

    @Test fun playAfterEndRestarts() {
        val s = run(MediaEvent.Load, MediaEvent.Prepared(5_000, false), MediaEvent.Play, MediaEvent.Completed)
        assertEquals(PlaybackPhase.Ended, s.phase)
        assertFalse(s.keepScreenOn)
        val again = MediaReducer.reduce(s, MediaEvent.TogglePlay)
        assertEquals(0, again.positionMs)
        assertTrue(again.isPlaying)
    }

    @Test fun errorStopsPlaybackAndIsSticky() {
        val s = run(
            MediaEvent.Load, MediaEvent.Prepared(5_000, false), MediaEvent.Play,
            MediaEvent.Error(PlaybackErrorKind.UNSUPPORTED_CODEC, "hev1"),
        )
        assertTrue(s.phase is PlaybackPhase.Failed)
        assertFalse(s.playWhenReady)
        // Late callbacks must not resurrect a failed player.
        val late = run(MediaEvent.Load, MediaEvent.Error(PlaybackErrorKind.CORRUPT_OR_UNREADABLE, "x"), MediaEvent.Prepared(1, false), MediaEvent.Play)
        assertTrue(late.phase is PlaybackPhase.Failed)
        assertFalse(late.isPlaying)
    }

    @Test fun volumeAndSubtitles() {
        var s = run(MediaEvent.Load, MediaEvent.Prepared(5_000, hasSubtitles = false))
        s = MediaReducer.reduce(s, MediaEvent.SetVolume(3f)); assertEquals(1f, s.volume)
        s = MediaReducer.reduce(s, MediaEvent.SetVolume(-1f)); assertEquals(0f, s.volume)
        s = MediaReducer.reduce(s, MediaEvent.SetSubtitles(true)); assertFalse(s.subtitlesEnabled)
        val withSubs = MediaReducer.reduce(run(MediaEvent.Load, MediaEvent.Prepared(5_000, true)), MediaEvent.SetSubtitles(true))
        assertTrue(withSubs.subtitlesEnabled)
    }

    @Test fun bufferingKeepsScreenOnWhilePlaying() {
        val s = run(MediaEvent.Load, MediaEvent.Prepared(5_000, false), MediaEvent.Play, MediaEvent.BufferingStarted)
        assertEquals(PlaybackPhase.Buffering, s.phase)
        assertTrue(s.keepScreenOn)
        assertEquals(PlaybackPhase.Ready, MediaReducer.reduce(s, MediaEvent.BufferingEnded).phase)
    }

    @Test fun releaseKeepsVolumePreference() {
        val s = run(MediaEvent.Load, MediaEvent.Prepared(5_000, false), MediaEvent.SetVolume(0.3f), MediaEvent.Release)
        assertEquals(PlaybackPhase.Idle, s.phase)
        assertEquals(0.3f, s.volume)
    }

    @Test fun errorClassification() {
        assertEquals(PlaybackErrorKind.UNSUPPORTED_CODEC, PlaybackErrorClassifier.classify("ERROR_CODE_DECODING_FORMAT_UNSUPPORTED"))
        assertEquals(PlaybackErrorKind.EXCEEDS_DECODER_CAPABILITIES, PlaybackErrorClassifier.classify("ERROR_CODE_DECODING_FORMAT_EXCEEDS_CAPABILITIES"))
        assertEquals(PlaybackErrorKind.CORRUPT_OR_UNREADABLE, PlaybackErrorClassifier.classify("ERROR_CODE_PARSING_CONTAINER_MALFORMED"))
        assertEquals(PlaybackErrorKind.FILE_ACCESS_LOST, PlaybackErrorClassifier.classify("ERROR_CODE_IO_NO_PERMISSION"))
        assertEquals(PlaybackErrorKind.UNKNOWN, PlaybackErrorClassifier.classify("ERROR_CODE_REMOTE_ERROR"))
    }
}
