package com.vrvision.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Dest
import com.vrvision.app.Navigator
import com.vrvision.app.cloud.CloudClient
import com.vrvision.app.enhance.JobModes
import com.vrvision.app.ui.components.ScreenTopBar
import com.vrvision.app.ui.components.SectionCard
import com.vrvision.app.ui.components.StatusPill
import com.vrvision.app.ui.theme.Danger
import com.vrvision.app.ui.theme.Ok
import com.vrvision.app.ui.theme.Warn
import com.vrvision.core.planning.OutputPlan
import com.vrvision.core.routing.CloudQuote
import com.vrvision.core.routing.LocalMemoryModel
import com.vrvision.core.routing.LocalThroughput
import com.vrvision.core.routing.ProcessingRoute
import com.vrvision.core.routing.RouteOption
import com.vrvision.core.routing.RoutingDecision
import com.vrvision.core.routing.RoutingEngine
import com.vrvision.core.routing.RoutingInput
import kotlinx.coroutines.launch

@Composable
fun RecommendationScreen(c: AppContainer, nav: Navigator, videoId: Long) {
    val video by remember(videoId) { c.videos.observe(videoId) }.collectAsState(initial = null)
    val prefs by c.settings.state.collectAsState()
    val scope = rememberCoroutineScope()
    var plan by remember { mutableStateOf<OutputPlan?>(null) }
    var decision by remember { mutableStateOf<RoutingDecision?>(null) }
    var cloudNote by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf<String?>(null) }
    var refresh by remember { mutableIntStateOf(0) }

    LaunchedEffect(video?.id, refresh) {
        val v = video ?: return@LaunchedEffect
        val d = c.draft(v)
        val p = c.plan(v, d)
        plan = p
        val state = c.device.deviceState()
        val cloudConfigured = prefs.cloudEnabled && !prefs.privacyLocalOnly && prefs.cloudUrl.isNotBlank() && !c.settings.cloudApiKey.isNullOrBlank()
        var quote: CloudQuote? = null
        cloudNote = null
        if (cloudConfigured && d.mode != ModePreference.LOCAL) {
            // Only metadata is sent for a quote (size, resolution, duration); never the video.
            try {
                val q = CloudClient(prefs.cloudUrl, c.settings.cloudApiKey!!).quote(v.width, v.height, (v.frameRate ?: 30f).toDouble(), v.durationMs, v.sizeBytes ?: 0)
                quote = CloudQuote(q.getDouble("estimated_seconds"), if (q.isNull("estimated_cost")) null else q.getDouble("estimated_cost"),
                    if (q.isNull("currency")) null else q.getString("currency"), q.getLong("max_upload_bytes"), q.getLong("max_duration_ms"))
            } catch (e: Exception) { cloudNote = "Cloud backend unreachable: ${e.message}" }
        }
        val model = c.models.forDenoise(d.denoise)
        decision = RoutingEngine.decide(
            RoutingInput(
                plan = p, localModelAvailable = model != null, localModelName = model?.name,
                localMemoryBytes = LocalMemoryModel.estimateBytes(v.width, v.height, p.requested.width, p.requested.height, 128, 4, 4_859_007),
                localThroughput = c.settings.benchmarkMsPerMp?.let { LocalThroughput(it.toDouble(), c.settings.benchmarkInfo ?: "a measurement") },
                privacyLocalOnly = prefs.privacyLocalOnly || d.mode == ModePreference.LOCAL || !prefs.cloudEnabled,
                cloudConfigured = cloudConfigured, connectivity = c.device.connectivity(), sourceSizeBytes = v.sizeBytes,
                cloudQuote = quote, thermal = state.thermal, batteryPercent = state.batteryPercent, charging = state.charging,
            ),
            state.availableRamBytes,
        )
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        ScreenTopBar("Processing recommendation", onBack = nav::back)
        val v = video; val p = plan; val dec = decision
        if (v == null || p == null || dec == null) { CircularProgressIndicator(Modifier.padding(32.dp)); return@Column }
        val draft = c.draft(v)
        val settings = settingsFor(v, draft, p)
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SectionCard("Recommendation") {
                StatusPill(
                    when (dec.recommended) { ProcessingRoute.LOCAL -> "On this phone"; ProcessingRoute.CLOUD -> "Cloud"; ProcessingRoute.UNSUPPORTED -> "Not supported" },
                    when (dec.recommended) { ProcessingRoute.LOCAL -> Ok; ProcessingRoute.CLOUD -> Warn; ProcessingRoute.UNSUPPORTED -> Danger },
                )
                dec.reasons.forEach { Text(it) }
                cloudNote?.let { Text(it, color = Warn) }
            }
            OptionCard("On this phone (AI)", dec.local)
            c.settings.benchmarkMsPerMp?.let { msPerMp ->
                val frames = (v.frameRate ?: 30f) * com.vrvision.core.enhance.PreviewSegment.length(v.durationMs) / 1000f
                val seconds = frames * (v.width.toDouble() * v.height / 1e6) * msPerMp / 1000.0
                Text(
                    "Local 10-second preview: about ${com.vrvision.app.ui.components.formatDuration((seconds * 1000).toLong())} " +
                        "(${c.settings.benchmarkInfo ?: "measured"}).",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } ?: Text("Tap \"Measure local speed\" to estimate how long local processing takes on this phone.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            OptionCard("Cloud (AI)", dec.cloud)

            busy?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            if (dec.local.feasible && settings != null) {
                Button(onClick = {
                    scope.launch {
                        val id = c.jobs.startPreview(v.id, v.durationMs, JobModes.LOCAL_AI, settings, draft.previewStartMs)
                        nav.replace(Dest.Progress(id))
                    }
                }, modifier = Modifier.fillMaxWidth().height(56.dp)) { Text("Process 10-second preview on this phone") }
            }
            if (dec.cloud.feasible && settings != null) {
                FilledTonalButton(onClick = { nav.go(Dest.CloudConsent(v.id)) }, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                    Text("Use cloud… (review what will be uploaded)")
                }
            }
            if (settings != null) {
                OutlinedButton(onClick = {
                    scope.launch {
                        val id = c.jobs.startPreview(v.id, v.durationMs, JobModes.LOCAL_CONVENTIONAL, settings, draft.previewStartMs)
                        nav.replace(Dest.Progress(id))
                    }
                }, modifier = Modifier.fillMaxWidth()) { Text("Conventional upscale preview (Lanczos, not AI, fast)") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    scope.launch {
                        busy = "Measuring on-device AI speed…"
                        busy = try {
                            val ms = c.jobs.benchmark(c.models, draft.denoise)
                            refresh++
                            "Measured %.0f ms per source megapixel (inference only).".format(ms)
                        } catch (e: Exception) { "Benchmark failed: ${e.message}" }
                    }
                }) { Text("Measure local speed") }
                OutlinedButton(onClick = { nav.replace(Dest.Player(v.id)) }) { Text("Play original instead") }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun OptionCard(title: String, o: RouteOption) {
    SectionCard(title) {
        StatusPill(if (o.feasible) "Possible" else "Not possible", if (o.feasible) Ok else Danger)
        o.reasons.forEach { Text("• $it", color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}
