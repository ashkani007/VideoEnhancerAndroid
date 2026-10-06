package com.lensprompt.app.camera

import android.Manifest
import android.annotation.SuppressLint
import android.content.ContentValues
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class CameraUiState(
    val bound: Boolean = false,
    val lensFacing: Int = CameraSelector.LENS_FACING_FRONT,
    val hasFront: Boolean = true,
    val hasBack: Boolean = true,
    val isRecording: Boolean = false,
    val recordedMs: Long = 0,
    val withAudio: Boolean = false,
    val lastSaved: String? = null,
    val error: String? = null,
)

/**
 * CameraX preview + video recording for the prompter screen.
 *
 * Recordings go to Movies/LensPrompt via MediaStore (API 29+) or to the app's
 * own Movies folder on older devices (no storage permission needed).
 * Main-thread only.
 */
class PrompterCamera(private val context: Context) {

    private var provider: ProcessCameraProvider? = null
    private var preview: Preview? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var recording: Recording? = null

    private val _state = MutableStateFlow(CameraUiState())
    val state: StateFlow<CameraUiState> = _state.asStateFlow()

    fun bind(owner: LifecycleOwner, previewView: PreviewView, lensFacing: Int = _state.value.lensFacing, rotation: Int) {
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
                p.unbindAll()
                p.bindToLifecycle(owner, selector, prev, vc)
                preview = prev
                videoCapture = vc
                _state.update { it.copy(bound = true, lensFacing = facing, hasFront = hasFront, hasBack = hasBack, error = null) }
            } catch (e: Exception) {
                Log.e(TAG, "Camera bind failed", e)
                _state.update { it.copy(bound = false, error = "Camera unavailable: ${e.message ?: e.javaClass.simpleName}") }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun switchCamera(owner: LifecycleOwner, previewView: PreviewView, rotation: Int) {
        if (_state.value.isRecording) return
        val next = if (_state.value.lensFacing == CameraSelector.LENS_FACING_FRONT) CameraSelector.LENS_FACING_BACK else CameraSelector.LENS_FACING_FRONT
        bind(owner, previewView, next, rotation)
    }

    fun setRotation(rotation: Int) {
        preview?.targetRotation = rotation
        // Changing rotation mid-recording would change the file orientation; keep it fixed then.
        if (!_state.value.isRecording) videoCapture?.targetRotation = rotation
    }

    fun unbind() {
        stopRecording()
        try { provider?.unbindAll() } catch (e: Exception) { Log.w(TAG, "unbind failed", e) }
        preview = null
        videoCapture = null
        _state.update { it.copy(bound = false) }
    }

    /** @return false if recording could not start (state.error explains why). */
    @SuppressLint("MissingPermission") // checked explicitly below
    fun startRecording(withAudio: Boolean): Boolean {
        val vc = videoCapture ?: run {
            _state.update { it.copy(error = "Camera is not ready") }
            return false
        }
        if (recording != null) return true
        val name = "LensPrompt_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        return try {
            val pending = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                    put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/LensPrompt")
                }
                val options = MediaStoreOutputOptions.Builder(context.contentResolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI)
                    .setContentValues(values)
                    .build()
                vc.output.prepareRecording(context, options)
            } else {
                val dir = context.getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: context.filesDir
                vc.output.prepareRecording(context, FileOutputOptions.Builder(File(dir, "$name.mp4")).build())
            }
            val micGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
            val audio = withAudio && micGranted
            val prepared = if (audio) pending.withAudioEnabled() else pending
            recording = prepared.start(ContextCompat.getMainExecutor(context)) { event -> onRecordEvent(event) }
            _state.update { it.copy(isRecording = true, recordedMs = 0, withAudio = audio, error = null) }
            true
        } catch (e: Exception) {
            Log.e(TAG, "startRecording failed", e)
            recording = null
            _state.update { it.copy(isRecording = false, error = "Could not start recording: ${e.message ?: e.javaClass.simpleName}") }
            false
        }
    }

    fun stopRecording() {
        try { recording?.stop() } catch (e: Exception) { Log.w(TAG, "stop failed", e) }
        recording = null
    }

    fun clearMessages() = _state.update { it.copy(error = null, lastSaved = null) }

    private fun onRecordEvent(event: VideoRecordEvent) {
        when (event) {
            is VideoRecordEvent.Status ->
                _state.update { it.copy(recordedMs = event.recordingStats.recordedDurationNanos / 1_000_000) }
            is VideoRecordEvent.Finalize -> {
                recording = null
                val uri = event.outputResults.outputUri
                val saved = uri != Uri.EMPTY
                val err = if (event.hasError() && !saved) "Recording failed (code ${event.error})" else null
                _state.update {
                    it.copy(
                        isRecording = false,
                        lastSaved = if (saved) "Saved to Movies/LensPrompt" else null,
                        error = err,
                    )
                }
            }
            else -> Unit
        }
    }

    private companion object { const val TAG = "PrompterCamera" }
}
