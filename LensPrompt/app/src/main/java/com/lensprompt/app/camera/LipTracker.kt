package com.lensprompt.app.camera

import android.os.SystemClock
import androidx.annotation.OptIn
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceContour
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetector
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlin.math.hypot

/**
 * Measures how open the speaker's mouth is, per camera frame, on-device (ML Kit
 * face contours; no images leave the phone or are stored).
 *
 * Openness = distance between the inner lip contours at the middle of the
 * mouth, divided by the face height, so it is independent of how far the
 * speaker is from the camera. The talking/not-talking decision is made by
 * [com.lensprompt.core.MouthActivityDetector] from how this value moves.
 */
class LipTracker {

    private val detector: FaceDetector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setContourMode(FaceDetectorOptions.CONTOUR_MODE_ALL)
            .build(),
    )
    @Volatile private var lastAnalysisMs = 0L

    fun analyzer(onMouth: (Double?, Long) -> Unit) = ImageAnalysis.Analyzer { proxy -> analyze(proxy, onMouth) }

    @OptIn(ExperimentalGetImage::class)
    private fun analyze(proxy: ImageProxy, onMouth: (Double?, Long) -> Unit) {
        val now = SystemClock.elapsedRealtime()
        val media = proxy.image
        // ~15 analyses per second are plenty for lip movement and keep CPU low.
        if (media == null || now - lastAnalysisMs < MIN_INTERVAL_MS) {
            proxy.close()
            return
        }
        lastAnalysisMs = now
        val input = InputImage.fromMediaImage(media, proxy.imageInfo.rotationDegrees)
        detector.process(input)
            .addOnSuccessListener { faces ->
                val face = faces.maxByOrNull { it.boundingBox.height() }
                onMouth(face?.let { openness(it) }, now)
            }
            .addOnFailureListener { onMouth(null, now) }
            .addOnCompleteListener { proxy.close() }
    }

    private fun openness(face: com.google.mlkit.vision.face.Face): Double? {
        val upper = face.getContour(FaceContour.UPPER_LIP_BOTTOM)?.points ?: return null
        val lower = face.getContour(FaceContour.LOWER_LIP_TOP)?.points ?: return null
        if (upper.isEmpty() || lower.isEmpty()) return null
        val u = upper[upper.size / 2]
        val l = lower[lower.size / 2]
        val faceHeight = face.boundingBox.height().toDouble()
        if (faceHeight <= 0) return null
        return hypot((u.x - l.x).toDouble(), (u.y - l.y).toDouble()) / faceHeight
    }

    fun close() = detector.close()

    private companion object { const val MIN_INTERVAL_MS = 66L }
}
