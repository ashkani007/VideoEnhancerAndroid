package com.lensprompt.app.camera

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.MediaStoreOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.lensprompt.core.AudioDsp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

data class CameraUiState(
    val bound: Boolean = false,
    val lensFacing: Int = CameraSelector.LENS_FACING_FRONT,
    val hasFront: Boolean = true,
    val hasBack: Boolean = true,
    val isRecording: Boolean = false,
    val recordedMs: Long = 0,
    val withAudio: Boolean = false,
    /** Muxing the recorded video with LensPrompt's audio. */
    val processing: Boolean = false,
    /** Lip tracking is bound and running. */
    val lipTracking: Boolean = false,
    val lastSaved: String? = null,
    val error: String? = null,
)

/** A finished video-only recording waiting to be muxed with app-captured audio. */
data class VideoForMux(val file: File, val videoStartNanos: Long, val error: String?)

/**
 * CameraX preview, video recording and (optionally) lip tracking for the
 * prompter screen. Main-thread only.
 *
 * Video is always recorded WITHOUT CameraX audio: CameraX would capture the
 * CAMCORDER source, which silences every other microphone user on the device —
 * including the speech recognizer Smart Follow depends on. When sound is
 * wanted, LensPrompt captures the microphone itself and muxes it in afterwards
 * (see [com.lensprompt.app.audio.AvMuxer]).
 */
class PrompterCamera(private val context: Context) {

    private var provider: ProcessCameraProvider? = null
    private var preview: Preview? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var analysis: ImageAnalysis? = null
    private var recording: Recording? = null
    private val analysisExecutor = Executors.newSingleThreadExecutor { r -> Thread(r, "lensprompt-lips") }
    private var lipTracker: LipTracker? = null

    private var pendingMux: ((VideoForMux) -> Unit)? = null
    private var muxFile: File? = null
    private var startEstimator = AudioDsp.VideoStartEstimator()

    private val _state = MutableStateFlow(CameraUiState())
    val state: StateFlow<CameraUiState> = _state.asStateFlow()

    /**
     * @param onMouth receives lip openness per analysed frame (null = no face), or
     *   null to disable lip tracking.
     */
    fun bind(
        owner: LifecycleOwner,
        previewView: PreviewView,
        lensFacing: Int = _state.value.lensFacing,
        rotation: Int,
        onMouth: ((Double?, Long) -> Unit)? = null,
    ) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            try {
                val p = future.get()
                provider = p
                val hasFront = p.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA)
                val hasBack = p.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)
                val facing = when {
                    lensFacing == CameraSelector.LENS_FACING_FRONT && hasFront -> lensFacing
                    lensFacing == CameraSelector.LENS_FACING_BACK && hasBack -> lensFacing
                    hasFront -> CameraSelector.LENS_FACING_FRONT
                    hasBack -> CameraSelector.LENS_FACING_BACK
                    else -> {
                        _state.update { it.copy(bound = false, hasFront = false, hasBack = false, error = "No camera available") }
                        return@addListener
                    }
                }
                val selector = CameraSelector.Builder().requireLensFacing(facing).build()
                val prev = Preview.Builder().setTargetRotation(rotation).build()
                prev.setSurfaceProvider(previewView.surfaceProvider)
                val recorder = Recorder.Builder()
                    .setQualitySelector(QualitySelector.from(Quality.FHD, FallbackStrategy.lowerQualityOrHigherThan(Quality.SD)))
                    .build()
                val vc = VideoCapture.withOutput(recorder)
                vc.targetRotation = rotation

                // Lip tracking needs a third use case; not every camera supports
                // preview + video + analysis together, so fall back without it.
                var ana: ImageAnalysis? = null
                p.unbindAll()
                if (onMouth != null) {
                    val tracker = lipTracker ?: LipTracker().also { lipTracker = it }
                    val a = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setResolutionSelector(
                            ResolutionSelector.Builder()
                                .setResolutionStrategy(ResolutionStrategy(Size(640, 480), ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER))
                                .build(),
                        )
                        .setTargetRotation(rotation)
                        .build()
                        .also { it.setAnalyzer(analysisExecutor, tracker.analyzer(onMouth)) }
                    ana = a
                    try {
                        p.bindToLifecycle(owner, selector, prev, vc, a)
                    } catch (e: Exception) {
                        Log.w(TAG, "preview+video+analysis not supported here; lip tracking off", e)
                        p.unbindAll()
                        ana = null
                        p.bindToLifecycle(owner, selector, prev, vc)
                    }
                } else {
                    p.bindToLifecycle(owner, selector, prev, vc)
                }
                preview = prev
                videoCapture = vc
                analysis = ana
                _state.update {
                    it.copy(bound = true, lensFacing = facing, hasFront = hasFront, hasBack = hasBack, lipTracking = ana != null, error = null)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Camera bind failed", e)
                _state.update { it.copy(bound = false, error = "Camera unavailable: ${e.message ?: e.javaClass.simpleName}") }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun switchCamera(owner: LifecycleOwner, previewView: PreviewView, rotation: Int, onMouth: ((Double?, Long) -> Unit)?) {
        if (_state.value.isRecording) return
        val next = if (_state.value.lensFacing == CameraSelector.LENS_FACING_FRONT) CameraSelector.LENS_FACING_BACK else CameraSelector.LENS_FACING_FRONT
        bind(owner, previewView, next, rotation, onMouth)
    }

    fun setRotation(rotation: Int) {
        preview?.targetRotation = rotation
        analysis?.targetRotation = rotation
        // Changing rotation mid-recording would change the file orientation; keep it fixed then.
        if (!_state.value.isRecording) videoCapture?.targetRotation = rotation
    }

    fun unbind() {
        stopRecording()
        try { provider?.unbindAll() } catch (e: Exception) { Log.w(TAG, "unbind failed", e) }
        preview = null
        videoCapture = null
        analysis = null
        _state.update { it.copy(bound = false, lipTracking = false) }
    }

    fun release() {
        unbind()
        lipTracker?.close()
        lipTracker = null
        analysisExecutor.shutdown()
    }

    /** Silent recording straight to Movies/LensPrompt (sound disabled in settings). */
    fun startSilentRecording(): Boolean {
        val vc = videoCapture ?: return notReady()
        if (recording != null) return true
        val name = fileName()
        return startInternal(withAudioLabel = false) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                    put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/LensPrompt")
                }
                vc.output.prepareRecording(
                    context,
                    MediaStoreOutputOptions.Builder(context.contentResolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI)
                        .setContentValues(values).build(),
                )
            } else {
                val dir = context.getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: context.filesDir
                vc.output.prepareRecording(context, FileOutputOptions.Builder(File(dir, "$name.mp4")).build())
            }
        }
    }

    /**
     * Video-only recording into [tempFile]; when it finishes, [onFinished] gets the
     * file and the estimated time of its first frame so app-captured audio can be
     * muxed in.
     */
    fun startRecordingForMux(tempFile: File, onFinished: (VideoForMux) -> Unit): Boolean {
        val vc = videoCapture ?: return notReady()
        if (recording != null) return true
        pendingMux = onFinished
        muxFile = tempFile
        return startInternal(withAudioLabel = true) {
            vc.output.prepareRecording(context, FileOutputOptions.Builder(tempFile).build())
        }
    }

    fun stopRecording() {
        try { recording?.stop() } catch (e: Exception) { Log.w(TAG, "stop failed", e) }
        recording = null
    }

    fun setProcessing(processing: Boolean) = _state.update { it.copy(processing = processing) }
    fun reportSaved(message: String) = _state.update { it.copy(processing = false, lastSaved = message) }
    fun reportError(message: String) = _state.update { it.copy(processing = false, error = message) }
    fun clearMessages() = _state.update { it.copy(error = null, lastSaved = null) }

    fun newVideoName(): String = fileName()

    private fun startInternal(withAudioLabel: Boolean, prepare: () -> androidx.camera.video.PendingRecording): Boolean = try {
        startEstimator = AudioDsp.VideoStartEstimator()
        recording = prepare().start(ContextCompat.getMainExecutor(context)) { event -> onRecordEvent(event) }
        _state.update { it.copy(isRecording = true, recordedMs = 0, withAudio = withAudioLabel, error = null, lastSaved = null) }
        true
    } catch (e: Exception) {
        Log.e(TAG, "startRecording failed", e)
        recording = null
        pendingMux = null
        _state.update { it.copy(isRecording = false, error = "Could not start recording: ${e.message ?: e.javaClass.simpleName}") }
        false
    }

    private fun notReady(): Boolean {
        _state.update { it.copy(error = "Camera is not ready") }
        return false
    }

    private fun fileName() = "LensPrompt_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())

    private fun onRecordEvent(event: VideoRecordEvent) {
        val now = System.nanoTime()
        when (event) {
            is VideoRecordEvent.Start -> startEstimator.onStarted(now)
            is VideoRecordEvent.Status -> {
                val d = event.recordingStats.recordedDurationNanos
                startEstimator.onStatus(now, d)
                _state.update { it.copy(recordedMs = d / 1_000_000) }
            }
            is VideoRecordEvent.Finalize -> {
                recording = null
                val mux = pendingMux
                pendingMux = null
                if (mux != null) {
                    val file = muxFile
                    muxFile = null
                    val ok = file != null && file.exists() && file.length() > 0
                    _state.update { it.copy(isRecording = false, processing = ok) }
                    mux(
                        VideoForMux(
                            file = file ?: File(""),
                            videoStartNanos = if (startEstimator.hasEstimate) startEstimator.estimateNanos else now,
                            error = if (!ok) "Recording failed (code ${event.error})" else null,
                        ),
                    )
                } else {
                    val uri = event.outputResults.outputUri
                    val saved = uri != Uri.EMPTY
                    val err = if (event.hasError() && !saved) "Recording failed (code ${event.error})" else null
                    _state.update {
                        it.copy(isRecording = false, lastSaved = if (saved) "Saved to Movies/LensPrompt (no sound)" else null, error = err)
                    }
                }
            }
            else -> Unit
        }
    }

    private companion object { const val TAG = "PrompterCamera" }
}
