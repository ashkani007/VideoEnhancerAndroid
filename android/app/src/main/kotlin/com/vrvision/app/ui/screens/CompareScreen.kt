package com.vrvision.app.ui.screens

import android.graphics.Bitmap
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.enhance.EnhanceSettings
import com.vrvision.app.ui.components.InfoRow
import com.vrvision.app.ui.components.LabeledSlider
import com.vrvision.app.ui.components.ScreenTopBar
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.formatBytes
import com.vrvision.app.ui.components.formatDuration
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

/**
 * Frame-accurate before/after comparison: both images are decoded at the same presentation
 * time (source time = preview start + t), shown with a draggable split and a shared zoom.
 */
@Composable
fun CompareScreen(c: AppContainer, nav: Navigator, jobId: Long) {
    val context = LocalContext.current
    val job by remember(jobId) { c.jobs.observe(jobId) }.collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    var t by remember { mutableFloatStateOf(0f) }
    var split by remember { mutableFloatStateOf(0.5f) }
    var zoom by remember { mutableFloatStateOf(1f) }
    var frames by remember { mutableStateOf<Pair<Bitmap?, Bitmap?>?>(null) }

    val j = job
    val video by remember(j?.videoId) { c.videos.observe(j?.videoId ?: -1) }.collectAsState(initial = null)
    LaunchedEffect(j?.outputPath, video?.uri, t) {
        val v = video ?: return@LaunchedEffect
        val path = j?.outputPath ?: return@LaunchedEffect
        frames = withContext(Dispatchers.IO) {
            val us = (t * 1000).toLong() * 1000
            Pair(frameAt(context, Uri.parse(v.uri), j.previewStartMs * 1000 + us), frameAt(context, Uri.fromFile(File(path)), us))
        }
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        ScreenTopBar("Before / after", onBack = nav::back)
        val v = video
        if (j == null || v == null) { CircularProgressIndicator(Modifier.padding(32.dp)); return@Column }
        val result = j.resultJson?.let { JSONObject(it) }
        val s = EnhanceSettings.fromJson(j.settingsJson)
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val (orig, enh) = frames ?: Pair(null, null)
            Box(
                Modifier.fillMaxWidth().aspectRatio(v.width.toFloat() / v.height).background(Color.Black).clipToBounds(),
            ) {
                orig?.let { Image(it.asImageBitmap(), "Original", Modifier.fillMaxSize().graphicsLayer(scaleX = zoom, scaleY = zoom), contentScale = ContentScale.Fit) }
                enh?.let {
                    // Clip in screen space (before the zoom layer) so the split line stays put.
                    Image(it.asImageBitmap(), "Enhanced", Modifier.fillMaxSize().drawWithContent {
                        clipRect(left = size.width * split) { this@drawWithContent.drawContent() }
                        drawLine(Color.White, Offset(size.width * split, 0f), Offset(size.width * split, size.height), 3f)
                    }.graphicsLayer(scaleX = zoom, scaleY = zoom), contentScale = ContentScale.Fit)
                }
                if (orig == null || enh == null) CircularProgressIndicator(Modifier.align(Alignment.Center))
                Text("Original", color = Color.White, modifier = Modifier.align(Alignment.TopStart).padding(8.dp))
                Text("Enhanced", color = Color.White, modifier = Modifier.align(Alignment.TopEnd).padding(8.dp))
            }
            LabeledSlider("Split", split, 0f..1f, { split = it }) { "${(it * 100).toInt()}%" }
            LabeledSlider("Zoom", zoom, 1f..4f, { zoom = it }) { "%.1f×".format(it) }
            LabeledSlider("Time in preview", t, 0f..(j.previewDurationMs / 1000f).coerceAtLeast(0.1f), { t = it }) { "%.1f s".format(it) }

            SectionCard("Details") {
                InfoRow("Method", result?.optString("type") ?: "?")
                InfoRow("Model", listOfNotNull(result?.optString("model")?.ifBlank { null }, result?.optString("modelVersion")?.ifBlank { null }).joinToString(" ").ifBlank { "None (conventional)" })
                InfoRow("Source resolution", "${v.width}×${v.height}")
                InfoRow("Output resolution", result?.optString("output") ?: "${s.outWidth}×${s.outHeight}")
                InfoRow("Output codec", result?.optString("codec") ?: s.outputMime)
                InfoRow("Processing time", result?.optLong("elapsedMs")?.let { formatDuration(it) + " for ${formatDuration(j.previewDurationMs)} of video" } ?: "?")
                val previewBytes = result?.optLong("outputBytes") ?: 0
                if (previewBytes > 0 && j.previewDurationMs > 0) {
                    InfoRow("Estimated full size", formatBytes(previewBytes * v.durationMs / j.previewDurationMs))
                    result?.optLong("elapsedMs")?.takeIf { it > 0 }?.let {
                        InfoRow("Estimated full time", "about " + formatDuration(it * v.durationMs / j.previewDurationMs) + " at the same speed")
                    }
                }
                InfoRow("Audio", result?.optString("audio")?.ifBlank { null } ?: "—")
                Text(
                    "AI super resolution creates plausible detail; compare faces and text carefully. If it looks wrong, reject the preview.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { scope.launch { c.jobs.rejectPreview(j.id); nav.home() } }, modifier = Modifier.weight(1f).height(56.dp)) {
                    Text("Reject")
                }
                Button(onClick = { scope.launch { val id = c.jobs.acceptPreview(j.id); nav.replace(Dest.Progress(id)) } }, modifier = Modifier.weight(1f).height(56.dp)) {
                    Text("Process full video")
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

/** Decodes the frame at [timeUs], scaled to at most 2560 px wide to bound memory. */
private fun frameAt(context: android.content.Context, uri: Uri, timeUs: Long): Bitmap? {
    val r = MediaMetadataRetriever()
    return try {
        r.setDataSource(context, uri)
        val w = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull() ?: 0
        val h = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull() ?: 0
        if (w > 2560 && h > 0) r.getScaledFrameAtTime(timeUs, MediaMetadataRetriever.OPTION_CLOSEST, 2560, 2560 * h / w)
        else r.getFrameAtTime(timeUs, MediaMetadataRetriever.OPTION_CLOSEST)
    } catch (_: Exception) {
        null
    } finally {
        try { r.release() } catch (_: Exception) { }
    }
}
