package com.vrvision.app.player

import android.content.Context
import android.net.Uri
import android.view.Surface
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.Tracks
import androidx.media3.common.VideoSize
import androidx.media3.common.text.CueGroup
import androidx.media3.exoplayer.ExoPlayer
import com.vrvision.core.media.MediaEvent
import com.vrvision.core.media.MediaReducer
import com.vrvision.core.media.MediaState
import com.vrvision.core.media.PlaybackErrorClassifier
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Thin ExoPlayer wrapper: forwards player callbacks as [MediaEvent]s into the pure
 * [MediaReducer] and applies user intents to the player. Must be used on the main thread.
 */
class PlayerController(context: Context, private val scope: CoroutineScope) {

    // A/V sync is driven by ExoPlayer's audio clock; the GL renderer only displays frames.
    private val player: ExoPlayer = ExoPlayer.Builder(context).build()

    private val _state = MutableStateFlow(MediaState())
    val state: StateFlow<MediaState> = _state.asStateFlow()
    private val _cues = MutableStateFlow("")
    val cues: StateFlow<String> = _cues.asStateFlow()
    private val _videoSize = MutableStateFlow(Pair(0, 0))
    val videoSize: StateFlow<Pair<Int, Int>> = _videoSize.asStateFlow()

    private var progressJob: Job? = null

    private fun dispatch(e: MediaEvent) { _state.value = MediaReducer.reduce(_state.value, e) }

    private val listener = object : Player.Listener {
        override fun onPlaybackStateChanged(playbackState: Int) {
            when (playbackState) {
                Player.STATE_READY -> {
                    if (_state.value.phase == com.vrvision.core.media.PlaybackPhase.Preparing) {
                        dispatch(MediaEvent.Prepared(player.duration.coerceAtLeast(0), hasTextTracks(player.currentTracks)))
                    } else dispatch(MediaEvent.BufferingEnded)
                }
                Player.STATE_BUFFERING -> dispatch(MediaEvent.BufferingStarted)
                Player.STATE_ENDED -> dispatch(MediaEvent.Completed)
                Player.STATE_IDLE -> Unit
            }
        }

        override fun onPlayerError(error: PlaybackException) {
            val kind = PlaybackErrorClassifier.classify(error.errorCodeName)
            dispatch(MediaEvent.Error(kind, error.message ?: error.errorCodeName))
        }

        override fun onTracksChanged(tracks: Tracks) {
            val s = _state.value
            _state.value = s.copy(subtitlesAvailable = hasTextTracks(tracks))
        }

        override fun onCues(cueGroup: CueGroup) {
            _cues.value = cueGroup.cues.joinToString("\n") { it.text?.toString().orEmpty() }.trim()
        }

        override fun onVideoSizeChanged(videoSize: VideoSize) {
            _videoSize.value = Pair(videoSize.width, videoSize.height)
        }
    }

    init {
        player.addListener(listener)
    }

    fun setSurface(surface: Surface) = player.setVideoSurface(surface)

    /** [mimeType] tells Media3 how to read URLs without a telling extension (HLS, DASH). */
    fun load(uri: Uri, startPositionMs: Long, mimeType: String? = null) {
        dispatch(MediaEvent.Load)
        val item = MediaItem.Builder().setUri(uri).apply { if (mimeType != null) setMimeType(mimeType) }.build()
        player.setMediaItem(item, startPositionMs.coerceAtLeast(0))
        player.prepare()
        applySubtitleSelection(_state.value.subtitlesEnabled)
        startProgress()
    }

    fun togglePlay() { dispatch(MediaEvent.TogglePlay); apply() }
    fun play() { dispatch(MediaEvent.Play); apply() }
    fun pause() { dispatch(MediaEvent.Pause); apply() }

    fun seekTo(ms: Long) { dispatch(MediaEvent.SeekTo(ms)); player.seekTo(_state.value.positionMs) }
    fun seekBy(deltaMs: Long) { dispatch(MediaEvent.SeekBy(deltaMs)); player.seekTo(_state.value.positionMs) }

    fun setVolume(v: Float) { dispatch(MediaEvent.SetVolume(v)); player.volume = _state.value.volume }

    fun setSubtitles(enabled: Boolean) {
        dispatch(MediaEvent.SetSubtitles(enabled))
        applySubtitleSelection(_state.value.subtitlesEnabled)
    }

    private fun applySubtitleSelection(enabled: Boolean) {
        player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
            .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, !enabled)
            .build()
        if (!enabled) _cues.value = ""
    }

    private fun apply() {
        val s = _state.value
        if (s.positionMs == 0L && player.playbackState == Player.STATE_ENDED) player.seekTo(0)
        player.playWhenReady = s.playWhenReady
    }

    private fun startProgress() {
        progressJob?.cancel()
        progressJob = scope.launch(Dispatchers.Main) {
            while (isActive) {
                dispatch(MediaEvent.Progress(player.currentPosition))
                delay(250)
            }
        }
    }

    fun currentPositionMs(): Long = player.currentPosition

    fun release() {
        progressJob?.cancel()
        player.removeListener(listener)
        player.release()
        dispatch(MediaEvent.Release)
    }

    private fun hasTextTracks(tracks: Tracks) = tracks.groups.any { it.type == C.TRACK_TYPE_TEXT }
}
