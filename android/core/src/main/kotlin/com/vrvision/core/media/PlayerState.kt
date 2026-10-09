package com.vrvision.core.media

/** Why playback failed, mapped from player errors so the UI can explain it plainly. */
enum class PlaybackErrorKind {
    UNSUPPORTED_CODEC,
    DECODER_INIT_FAILED,
    EXCEEDS_DECODER_CAPABILITIES,
    CORRUPT_OR_UNREADABLE,
    FILE_ACCESS_LOST,
    UNKNOWN,
}

sealed interface PlaybackPhase {
    data object Idle : PlaybackPhase
    data object Preparing : PlaybackPhase
    data object Ready : PlaybackPhase
    data object Buffering : PlaybackPhase
    data object Ended : PlaybackPhase
    data class Failed(val kind: PlaybackErrorKind, val detail: String) : PlaybackPhase
}

/**
 * Single source of truth for the player UI. [playWhenReady] is the user's intent; the actual
 * rendering state is [phase]. Positions are milliseconds.
 */
data class MediaState(
    val phase: PlaybackPhase = PlaybackPhase.Idle,
    val playWhenReady: Boolean = false,
    val positionMs: Long = 0,
    val durationMs: Long = 0,
    val volume: Float = 1f,
    val subtitlesEnabled: Boolean = false,
    val subtitlesAvailable: Boolean = false,
) {
    val isPlaying: Boolean get() = playWhenReady && phase == PlaybackPhase.Ready
    /** Whether the screen must be kept awake (playing or about to play). */
    val keepScreenOn: Boolean
        get() = playWhenReady && (phase == PlaybackPhase.Ready || phase == PlaybackPhase.Buffering || phase == PlaybackPhase.Preparing)
    val canControl: Boolean get() = phase == PlaybackPhase.Ready || phase == PlaybackPhase.Buffering || phase == PlaybackPhase.Ended
}

sealed interface MediaEvent {
    data object Load : MediaEvent
    data class Prepared(val durationMs: Long, val hasSubtitles: Boolean) : MediaEvent
    data object BufferingStarted : MediaEvent
    data object BufferingEnded : MediaEvent
    data object Play : MediaEvent
    data object Pause : MediaEvent
    data object TogglePlay : MediaEvent
    data class SeekTo(val positionMs: Long) : MediaEvent
    data class SeekBy(val deltaMs: Long) : MediaEvent
    data class Progress(val positionMs: Long) : MediaEvent
    data class SetVolume(val volume: Float) : MediaEvent
    data class SetSubtitles(val enabled: Boolean) : MediaEvent
    data object Completed : MediaEvent
    data class Error(val kind: PlaybackErrorKind, val detail: String) : MediaEvent
    data object Release : MediaEvent
}

/** Pure reducer; the app forwards ExoPlayer callbacks as events and renders the result. */
object MediaReducer {

    fun reduce(s: MediaState, e: MediaEvent): MediaState = when (e) {
        MediaEvent.Load -> MediaState(phase = PlaybackPhase.Preparing, volume = s.volume, subtitlesEnabled = s.subtitlesEnabled)
        is MediaEvent.Prepared ->
            if (s.phase is PlaybackPhase.Failed) s
            else s.copy(
                phase = PlaybackPhase.Ready,
                durationMs = e.durationMs.coerceAtLeast(0),
                subtitlesAvailable = e.hasSubtitles,
                subtitlesEnabled = s.subtitlesEnabled && e.hasSubtitles,
            )
        MediaEvent.BufferingStarted -> if (s.canControl) s.copy(phase = PlaybackPhase.Buffering) else s
        MediaEvent.BufferingEnded -> if (s.phase == PlaybackPhase.Buffering) s.copy(phase = PlaybackPhase.Ready) else s
        MediaEvent.Play -> when (s.phase) {
            PlaybackPhase.Ended -> s.copy(phase = PlaybackPhase.Ready, positionMs = 0, playWhenReady = true)
            is PlaybackPhase.Failed, PlaybackPhase.Idle -> s
            else -> s.copy(playWhenReady = true)
        }
        MediaEvent.Pause -> s.copy(playWhenReady = false)
        MediaEvent.TogglePlay -> reduce(s, if (s.playWhenReady && s.phase != PlaybackPhase.Ended) MediaEvent.Pause else MediaEvent.Play)
        is MediaEvent.SeekTo -> seek(s, e.positionMs)
        is MediaEvent.SeekBy -> seek(s, s.positionMs + e.deltaMs)
        is MediaEvent.Progress -> if (s.canControl) s.copy(positionMs = clampPos(e.positionMs, s.durationMs)) else s
        is MediaEvent.SetVolume -> s.copy(volume = if (e.volume.isNaN()) s.volume else e.volume.coerceIn(0f, 1f))
        is MediaEvent.SetSubtitles -> s.copy(subtitlesEnabled = e.enabled && s.subtitlesAvailable)
        MediaEvent.Completed -> if (s.canControl) s.copy(phase = PlaybackPhase.Ended, positionMs = s.durationMs, playWhenReady = false) else s
        is MediaEvent.Error -> s.copy(phase = PlaybackPhase.Failed(e.kind, e.detail), playWhenReady = false)
        MediaEvent.Release -> MediaState(volume = s.volume)
    }

    private fun seek(s: MediaState, target: Long): MediaState {
        if (!s.canControl) return s
        val pos = clampPos(target, s.durationMs)
        val phase = if (s.phase == PlaybackPhase.Ended && pos < s.durationMs) PlaybackPhase.Ready else s.phase
        return s.copy(positionMs = pos, phase = phase)
    }

    private fun clampPos(pos: Long, duration: Long): Long =
        if (duration > 0) pos.coerceIn(0, duration) else pos.coerceAtLeast(0)
}

/** Classifies decoder/extractor error names into user-facing categories. */
object PlaybackErrorClassifier {
    /**
     * @param errorCodeName e.g. ExoPlayer's PlaybackException.errorCodeName
     *        ("ERROR_CODE_DECODER_INIT_FAILED", "ERROR_CODE_PARSING_CONTAINER_MALFORMED", ...).
     */
    fun classify(errorCodeName: String): PlaybackErrorKind = when {
        "DECODING_FORMAT_UNSUPPORTED" in errorCodeName -> PlaybackErrorKind.UNSUPPORTED_CODEC
        "DECODING_FORMAT_EXCEEDS_CAPABILITIES" in errorCodeName -> PlaybackErrorKind.EXCEEDS_DECODER_CAPABILITIES
        "DECODER_INIT_FAILED" in errorCodeName || "DECODER_QUERY_FAILED" in errorCodeName -> PlaybackErrorKind.DECODER_INIT_FAILED
        "PARSING" in errorCodeName || "DECODING_FAILED" in errorCodeName -> PlaybackErrorKind.CORRUPT_OR_UNREADABLE
        "IO_NO_PERMISSION" in errorCodeName || "IO_FILE_NOT_FOUND" in errorCodeName -> PlaybackErrorKind.FILE_ACCESS_LOST
        else -> PlaybackErrorKind.UNKNOWN
    }

    fun userMessage(kind: PlaybackErrorKind): String = when (kind) {
        PlaybackErrorKind.UNSUPPORTED_CODEC -> "This phone has no decoder for this video's codec."
        PlaybackErrorKind.EXCEEDS_DECODER_CAPABILITIES -> "The video's resolution or frame rate exceeds this phone's hardware decoder limits."
        PlaybackErrorKind.DECODER_INIT_FAILED -> "The video decoder could not start. Close other video apps and try again."
        PlaybackErrorKind.CORRUPT_OR_UNREADABLE -> "The file appears corrupt or uses an unsupported container."
        PlaybackErrorKind.FILE_ACCESS_LOST -> "Access to this file was lost. Import it again."
        PlaybackErrorKind.UNKNOWN -> "Playback failed."
    }
}
