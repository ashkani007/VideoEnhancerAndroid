package com.vrvision.app.enhance

import android.content.Context
import android.net.Uri
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.effect.LanczosResample
import androidx.media3.transformer.Composition
import androidx.media3.transformer.DefaultEncoderFactory
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.Effects
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.ProgressHolder
import androidx.media3.transformer.Transformer
import androidx.media3.transformer.VideoEncoderSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.coroutineScope
import java.io.File
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Conventional GPU upscaling with a Lanczos filter (Media3 Transformer). This is NOT AI super
 * resolution and is labelled as such everywhere in the UI. Encoder fallback is disabled so the
 * requested size and codec are never changed silently. Note: the filter does not split stereo
 * eyes, so pixels within ~3 source pixels of the SBS/TB seam are blended across eyes.
 */
@androidx.annotation.OptIn(markerClass = [UnstableApi::class])
class ConventionalUpscaler(private val context: Context) {

    suspend fun run(
        source: Uri, startMs: Long, endMs: Long?, outW: Int, outH: Int, mime: String, bitrate: Int, output: File,
        onProgress: suspend (Int) -> Unit,
    ): ExportResult = withContext(Dispatchers.Main) {
        coroutineScope {
            val clip = MediaItem.ClippingConfiguration.Builder().setStartPositionMs(startMs)
                .apply { if (endMs != null) setEndPositionMs(endMs) }.build()
            val item = EditedMediaItem.Builder(MediaItem.Builder().setUri(source).setClippingConfiguration(clip).build())
                .setEffects(Effects(emptyList(), listOf(LanczosResample.scaleToFitWithFlexibleOrientation(outW, outH))))
                .build()
            val encoders = DefaultEncoderFactory.Builder(context)
                .setEnableFallback(false)
                .setRequestedVideoEncoderSettings(VideoEncoderSettings.Builder().setBitrate(bitrate).build())
                .build()
            output.parentFile?.mkdirs()
            var poller: kotlinx.coroutines.Job? = null
            try {
                suspendCancellableCoroutine { cont ->
                    val transformer = Transformer.Builder(context)
                        .setVideoMimeType(mime)
                        .setEncoderFactory(encoders)
                        .addListener(object : Transformer.Listener {
                            override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                                if (cont.isActive) cont.resume(exportResult)
                            }

                            override fun onError(composition: Composition, exportResult: ExportResult, exportException: ExportException) {
                                output.delete()
                                if (cont.isActive) cont.resumeWithException(exportException)
                            }
                        })
                        .build()
                    transformer.start(item, output.path)
                    val holder = ProgressHolder()
                    poller = launch {
                        while (true) {
                            if (transformer.getProgress(holder) == Transformer.PROGRESS_STATE_AVAILABLE) onProgress(holder.progress)
                            delay(500)
                        }
                    }
                    cont.invokeOnCancellation {
                        // Transformer must be used on the thread that created it (main).
                        ContextCompat.getMainExecutor(context).execute {
                            transformer.cancel()
                            output.delete()
                        }
                    }
                }
            } finally {
                poller?.cancel()
            }
        }
    }
}
