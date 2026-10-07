package com.lensprompt.app.ui

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Cameraswitch
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.FiberManualRecord
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PictureInPictureAlt
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.RestartAlt
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import com.lensprompt.app.R
import com.lensprompt.app.data.AppSettings
import com.lensprompt.app.data.PromptAlign
import com.lensprompt.app.prompter.BannerAction
import com.lensprompt.app.prompter.PrompterViewModel
import com.lensprompt.app.prompter.RunState
import com.lensprompt.core.FollowState
import com.lensprompt.core.Token
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PrompterScreen(scriptId: String, onBack: () -> Unit, onEdit: () -> Unit, onSettings: () -> Unit) {
    val context = LocalContext.current
    val app = context.applicationContext as Application
    val vm: PrompterViewModel = viewModel(key = "prompter-$scriptId", factory = PrompterViewModel.Factory(app, scriptId))
    val settings by vm.settings.collectAsState()
    val ui by vm.ui.collectAsState()
    val script by vm.script.collectAsState()
    val followState by vm.followState.collectAsState()
    val lifecycleOwner = LocalLifecycleOwner.current
    val view = LocalView.current

    val camera = vm.camera
    val cameraState by camera.state.collectAsState()
    var previewView by remember { mutableStateOf<PreviewView?>(null) }
    var controlsVisible by remember { mutableStateOf(true) }
    var showSheet by remember { mutableStateOf(false) }
    var showFloating by remember { mutableStateOf(false) }
    val untitled = stringResource(R.string.common_untitled)
    val endOfScript = stringResource(R.string.prompter_end_of_script)

    fun granted(p: String) = ContextCompat.checkSelfPermission(context, p) == PackageManager.PERMISSION_GRANTED
    var cameraGranted by remember { mutableStateOf(granted(Manifest.permission.CAMERA)) }

    val micLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vm.play() else vm.onMicPermissionDenied()
    }
    // Recording with sound needs the microphone (LensPrompt records the audio itself).
    val recordMicLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vm.toggleRecording() else camera.startSilentRecording()
    }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        cameraGranted = ok
    }

    fun startOrToggle() {
        val needsMic = settings.smartFollow && !(settings.debugMode && ui.simulating)
        val idle = ui.runState == RunState.STOPPED || ui.runState == RunState.PAUSED
        if (idle && needsMic && !granted(Manifest.permission.RECORD_AUDIO)) {
            micLauncher.launch(Manifest.permission.RECORD_AUDIO)
        } else {
            vm.togglePlay()
        }
    }

    // Keep the screen awake while prompting.
    DisposableEffect(view) {
        view.keepScreenOn = true
        onDispose { view.keepScreenOn = false }
    }

    // Leaving the foreground (home, phone call, screen off): stop listening and recording.
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                vm.onBackground()
                camera.stopRecording()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            camera.unbind()
        }
    }

    LaunchedEffect(settings.showCamera) {
        if (settings.showCamera && !cameraGranted) cameraLauncher.launch(Manifest.permission.CAMERA)
    }

    // Bind / unbind the camera; keep the capture rotation in sync with the display.
    val orientation = LocalConfiguration.current.orientation
    val rotation = view.display?.rotation ?: android.view.Surface.ROTATION_0
    val onMouth: ((Double?, Long) -> Unit)? = if (settings.lipTracking) vm::onMouthOpenness else null
    LaunchedEffect(settings.showCamera, cameraGranted, previewView, settings.lipTracking) {
        val pv = previewView
        if (cameraState.isRecording) return@LaunchedEffect // never rebind mid-recording
        if (settings.showCamera && cameraGranted && pv != null) camera.bind(lifecycleOwner, pv, rotation = rotation, onMouth = onMouth)
        else camera.unbind()
    }
    LaunchedEffect(orientation, rotation) { camera.setRotation(rotation) }

    // Auto-hide controls while running.
    LaunchedEffect(controlsVisible, ui.runState) {
        if (controlsVisible && ui.runState == RunState.RUNNING) {
            delay(3_000)
            controlsVisible = false
        }
        if (ui.runState != RunState.RUNNING) controlsVisible = true
    }


    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (settings.showCamera && cameraGranted) {
            AndroidView(
                factory = { ctx ->
                    PreviewView(ctx).apply {
                        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                        scaleType = PreviewView.ScaleType.FILL_CENTER
                        previewView = this
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )
            Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = settings.backgroundDim)))
        }

        PromptText(
            text = script?.body.orEmpty(),
            tokens = remember(script?.body, settings.languageTag) { vm.tokens(script?.body.orEmpty()) },
            settings = settings,
            vm = vm,
            onTap = { controlsVisible = !controlsVisible },
        )

        ReadingAnchor(settings)

        // Top bar: back, title, status
        AnimatedVisibility(controlsVisible, enter = fadeIn(), exit = fadeOut(), modifier = Modifier.align(Alignment.TopCenter)) {
            Row(
                Modifier.fillMaxWidth().background(Color.Black.copy(alpha = 0.55f)).statusBarsPadding().padding(horizontal = 4.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.common_back), tint = Color.White) }
                Text(
                    script?.title?.ifBlank { untitled } ?: "",
                    color = Color.White,
                    maxLines = 1,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleMedium,
                )
                IconButton(onClick = { if (!cameraState.isRecording) { vm.stop(); showFloating = true } }) {
                    Icon(Icons.Filled.PictureInPictureAlt, contentDescription = stringResource(R.string.prompter_use_with_camera_desc), tint = Color.White)
                }
                IconButton(onClick = onEdit) { Icon(Icons.Filled.Edit, contentDescription = stringResource(R.string.prompter_edit_script), tint = Color.White) }
                IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, contentDescription = stringResource(R.string.common_settings), tint = Color.White) }
            }
        }

        // Always-visible status: mode / listening indicator / recording timer.
        Column(
            Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(top = if (controlsVisible) 56.dp else 8.dp, end = 12.dp),
            horizontalAlignment = Alignment.End,
        ) {
            StatusChip(settings, ui.runState, followState, ui.simulating)
            if (cameraState.isRecording) {
                Spacer(Modifier.height(6.dp))
                RecordingChip(cameraState.recordedMs, cameraState.withAudio)
            } else if (cameraState.processing) {
                Spacer(Modifier.height(6.dp))
                Surface(color = Color.Black.copy(alpha = 0.6f), shape = RoundedCornerShape(50)) {
                    Text(stringResource(R.string.prompter_saving_video), color = Color.White, style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp))
                }
            }
        }

        // Bottom controls
        AnimatedVisibility(controlsVisible, enter = fadeIn(), exit = fadeOut(), modifier = Modifier.align(Alignment.BottomCenter)) {
            BottomControls(
                runState = ui.runState,
                smartFollow = settings.smartFollow,
                cameraReady = cameraState.bound,
                isRecording = cameraState.isRecording,
                canSwitchCamera = cameraState.bound && cameraState.hasFront && cameraState.hasBack,
                onPlayPause = ::startOrToggle,
                onStop = vm::stop,
                onReset = vm::resetToStart,
                onToggleMode = { vm.setSmartFollow(!settings.smartFollow) },
                onRecord = {
                    if (!cameraState.isRecording && settings.recordAudio && !granted(Manifest.permission.RECORD_AUDIO)) {
                        recordMicLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    } else {
                        vm.toggleRecording()
                    }
                },
                onSwitchCamera = { previewView?.let { camera.switchCamera(lifecycleOwner, it, rotation, onMouth) } },
                onTune = { showSheet = true },
            )
        }

        if (ui.runState == RunState.COUNTDOWN && ui.countdown > 0) {
            Text(
                "${ui.countdown}",
                color = Color.White,
                fontSize = 120.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.align(Alignment.Center),
            )
        }

        val bannerText = ui.banner?.message ?: cameraState.error ?: cameraState.lastSaved
            ?: if (ui.atEnd) endOfScript else null
        if (bannerText != null) {
            Surface(
                color = LensColors.SurfaceHigh.copy(alpha = 0.95f),
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.align(Alignment.Center).padding(24.dp),
            ) {
                Column(Modifier.padding(16.dp)) {
                    Text(bannerText, color = Color.White)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        if (ui.banner?.action == BannerAction.OPEN_SETTINGS && !cameraState.isRecording) {
                            TextButton(onClick = { vm.dismissBanner(); onSettings() }) { Text(stringResource(R.string.common_settings)) }
                        }
                        if (ui.banner?.action == BannerAction.SWITCH_TO_MANUAL) {
                            TextButton(onClick = { vm.onBannerAction(BannerAction.SWITCH_TO_MANUAL) }) { Text(stringResource(R.string.prompter_use_manual)) }
                        }
                        TextButton(onClick = { vm.dismissBanner(); camera.clearMessages() }) { Text(stringResource(R.string.common_ok)) }
                    }
                }
            }
        }

        if (settings.debugMode) DebugOverlay(vm, Modifier.align(Alignment.BottomStart))

        FloatingModeBanner(Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(horizontal = 12.dp, vertical = 96.dp))
    }

    if (showFloating) FloatingPrompterDialog(scriptId) { showFloating = false }

    if (showSheet) {
        ModalBottomSheet(onDismissRequest = { showSheet = false }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
            QuickSettings(settings, vm)
        }
    }
}

/** The script, positioned by the scroll controller every frame without recomposition. */
@Composable
private fun PromptText(
    text: String,
    tokens: List<Token>,
    settings: AppSettings,
    vm: PrompterViewModel,
    onTap: () -> Unit,
) {
    val density = LocalDensity.current
    var scrollPx by remember { mutableFloatStateOf(0f) }

    // Runs every display frame while the text moves; sleeps when the prompter is settled.
    LaunchedEffect(vm) {
        while (true) {
            withFrameNanos { t -> scrollPx = vm.onFrame(t, density.density) }
            if (!vm.needsFrames()) vm.awaitFrameDemand()
        }
    }

    BoxWithConstraints(
        Modifier
            .fillMaxSize()
            .clipToBounds()
            .graphicsLayer {
                scaleX = if (settings.mirrorHorizontal) -1f else 1f
                scaleY = if (settings.mirrorVertical) -1f else 1f
            }
            .pointerInput(Unit) { detectTapGestures(onTap = { onTap() }) }
            .pointerInput(settings.mirrorVertical) {
                detectVerticalDragGestures(onDragEnd = { vm.onDragEnd() }) { change, dy ->
                    change.consume()
                    vm.onDrag(if (settings.mirrorVertical) -dy else dy)
                }
            },
    ) {
        val viewport = constraints.maxHeight.toFloat()
        val anchorY = viewport * settings.anchorFraction
        val lineHeightPx = with(density) { (settings.fontSizeSp * settings.lineSpacing).sp.toPx() }
        val marginDp = with(density) { (constraints.maxWidth * settings.marginFraction).toDp() }
        val style = TextStyle(
            color = Color.White,
            fontSize = settings.fontSizeSp.sp,
            lineHeight = (settings.fontSizeSp * settings.lineSpacing).sp,
            fontWeight = FontWeight.Medium,
            fontFamily = FontFamily.SansSerif,
            textAlign = if (settings.align == PromptAlign.CENTER) TextAlign.Center else TextAlign.Start,
            textDirection = TextDirection.Content,
        )
        androidx.compose.foundation.text.BasicText(
            text = text,
            style = style,
            onTextLayout = { r -> vm.onLayout(tokenPositions(r, tokens), r.size.height.toFloat()) },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = marginDp)
                .wrapContentHeight(align = Alignment.Top, unbounded = true)
                .graphicsLayer { translationY = anchorY - lineHeightPx / 2f - scrollPx },
        )
    }
}

/**
 * y (px) for every script token. Within a line, y advances in proportion to the
 * character position, so steady reading maps to steady scrolling.
 */
private fun tokenPositions(r: TextLayoutResult, tokens: List<Token>): FloatArray {
    val len = r.layoutInput.text.length
    val out = FloatArray(tokens.size)
    if (len == 0) return out
    for (i in tokens.indices) {
        val off = tokens[i].start.coerceIn(0, len - 1)
        val line = r.getLineForOffset(off)
        val ls = r.getLineStart(line)
        val le = r.getLineEnd(line)
        val frac = if (le > ls) (off - ls).toFloat() / (le - ls) else 0f
        val top = r.getLineTop(line)
        val bottom = r.getLineBottom(line)
        out[i] = top + frac * (bottom - top)
        if (i > 0 && out[i] < out[i - 1]) out[i] = out[i - 1]
    }
    return out
}

@Composable
private fun ReadingAnchor(settings: AppSettings) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val y = maxHeight * settings.anchorFraction
        Box(
            Modifier
                .offset(y = y - 6.dp)
                .padding(start = 2.dp)
                .size(width = 6.dp, height = 12.dp)
                .background(LensColors.Accent.copy(alpha = 0.85f), RoundedCornerShape(3.dp)),
        )
    }
}

@Composable
private fun StatusChip(settings: AppSettings, runState: RunState, follow: FollowState, simulating: Boolean) {
    val listening = settings.smartFollow && runState == RunState.RUNNING && !simulating
    val (label, color) = when {
        !settings.smartFollow -> stringResource(R.string.prompter_status_manual, "%.0f".format(settings.manualSpeed)) to LensColors.Muted
        runState != RunState.RUNNING -> "Smart Follow" to LensColors.Muted
        else -> when (follow) {
            FollowState.LISTENING -> stringResource(R.string.prompter_status_listening) to LensColors.Listening
            FollowState.TRACKING -> stringResource(R.string.prompter_status_following) to LensColors.Listening
            FollowState.SHORT_GAP -> stringResource(R.string.prompter_status_following) to LensColors.Listening
            FollowState.PAUSED -> stringResource(R.string.prompter_status_waiting) to LensColors.Accent
            FollowState.LOW_CONFIDENCE -> stringResource(R.string.prompter_status_finding_place) to LensColors.Accent
            FollowState.RECOVERING -> stringResource(R.string.prompter_status_finding_place) to LensColors.Accent
            FollowState.PACING -> stringResource(R.string.prompter_status_following_voice) to LensColors.Listening
            FollowState.ERROR -> stringResource(R.string.prompter_status_mic_unavailable) to LensColors.Recording
            FollowState.IDLE -> "Smart Follow" to LensColors.Muted
        }
    }
    Surface(color = Color.Black.copy(alpha = 0.6f), shape = RoundedCornerShape(50)) {
        Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            if (listening) {
                Icon(Icons.Filled.Mic, contentDescription = stringResource(R.string.prompter_mic_on), tint = LensColors.Listening, modifier = Modifier.size(16.dp))
            } else if (!settings.smartFollow) {
                Icon(Icons.Filled.Speed, contentDescription = null, tint = color, modifier = Modifier.size(16.dp))
            } else {
                Box(Modifier.size(8.dp).background(color, CircleShape))
            }
            Spacer(Modifier.width(6.dp))
            Text(if (simulating) "SIM · $label" else label, color = Color.White, style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
private fun RecordingChip(ms: Long, withSound: Boolean) {
    val s = ms / 1000
    Surface(color = Color.Black.copy(alpha = 0.6f), shape = RoundedCornerShape(50)) {
        Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(10.dp).background(LensColors.Recording, CircleShape))
            Spacer(Modifier.width(6.dp))
            Text(
                "REC %02d:%02d".format(s / 60, s % 60) + if (withSound) "" else " · " + stringResource(R.string.prompter_rec_no_sound),
                color = Color.White,
                style = MaterialTheme.typography.labelLarge,
            )
        }
    }
}

@Composable
private fun BottomControls(
    runState: RunState,
    smartFollow: Boolean,
    cameraReady: Boolean,
    isRecording: Boolean,
    canSwitchCamera: Boolean,
    onPlayPause: () -> Unit,
    onStop: () -> Unit,
    onReset: () -> Unit,
    onToggleMode: () -> Unit,
    onRecord: () -> Unit,
    onSwitchCamera: () -> Unit,
    onTune: () -> Unit,
) {
    val white = IconButtonDefaults.iconButtonColors(contentColor = Color.White)
    Row(
        Modifier
            .fillMaxWidth()
            .background(Color.Black.copy(alpha = 0.6f))
            .navigationBarsPadding()
            .padding(horizontal = 8.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onReset, colors = white) { Icon(Icons.Filled.RestartAlt, contentDescription = stringResource(R.string.prompter_back_to_start)) }
        IconButton(onClick = onStop, colors = white, enabled = runState != RunState.STOPPED) {
            Icon(Icons.Filled.Stop, contentDescription = stringResource(R.string.common_stop))
        }
        val running = runState == RunState.RUNNING || runState == RunState.COUNTDOWN
        FilledIconButton(onClick = onPlayPause, modifier = Modifier.size(64.dp)) {
            Icon(
                if (running) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                contentDescription = if (running) stringResource(R.string.common_pause) else if (runState == RunState.PAUSED) stringResource(R.string.prompter_resume) else stringResource(R.string.common_start),
                modifier = Modifier.size(34.dp),
            )
        }
        TextButton(onClick = onToggleMode) {
            Icon(if (smartFollow) Icons.Filled.Mic else Icons.Filled.Speed, contentDescription = null, tint = if (smartFollow) LensColors.Listening else Color.White)
            Spacer(Modifier.width(4.dp))
            Text(if (smartFollow) stringResource(R.string.prompter_mode_smart) else stringResource(R.string.prompter_mode_manual), color = Color.White)
        }
        IconButton(onClick = onRecord, enabled = cameraReady, colors = white) {
            Icon(
                if (isRecording) Icons.Filled.Stop else Icons.Filled.FiberManualRecord,
                contentDescription = if (isRecording) stringResource(R.string.prompter_stop_recording) else stringResource(R.string.prompter_record_video),
                tint = if (cameraReady) LensColors.Recording else Color.Gray,
            )
        }
        if (canSwitchCamera) {
            IconButton(onClick = onSwitchCamera, enabled = !isRecording, colors = white) {
                Icon(Icons.Filled.Cameraswitch, contentDescription = stringResource(R.string.prompter_switch_camera))
            }
        }
        IconButton(onClick = onTune, colors = white) { Icon(Icons.Filled.Tune, contentDescription = stringResource(R.string.prompter_display_settings)) }
    }
}

@Composable
private fun DebugOverlay(vm: PrompterViewModel, modifier: Modifier) {
    val d by vm.debug.collectAsState()
    val f = d.follow
    Surface(color = Color.Black.copy(alpha = 0.7f), modifier = modifier.padding(start = 8.dp, bottom = 120.dp).width(300.dp)) {
        Column(Modifier.padding(8.dp)) {
            val line: @Composable (String) -> Unit = { s ->
                Text(s, color = Color(0xFF9EF0B0), fontSize = 11.sp, fontFamily = FontFamily.Monospace, lineHeight = 13.sp)
            }
            if (f == null) {
                line("Smart Follow idle")
            } else {
                line("Recognized: \"${f.lastRecognized.takeLast(42)}\"")
                line("Matched index: ${f.matchedIndex}  pending: ${f.pendingJumpIndex}")
                line("Confidence: ${"%.2f".format(f.confidence)}")
                line("Reading velocity: ${"%.2f".format(f.readingVelocity)} tok/s")
                line("Target: ${"%.2f".format(f.targetProgress)} @ ${"%.2f".format(f.targetVelocity)} tok/s")
                line("Scroll velocity: ${"%.0f".format(d.scrollVelocityPx)} px/s")
                line("State: ${f.state}${if (f.pacing) " (${f.pacingReason})" else ""}")
                line("Voice: ${f.voice}  Lips: ${f.visual}")
                line("Since progress: ${f.msSinceProgress} ms")
            }
            line("Route: ${d.route}")
            d.diag.forEach { line(it) }
            line("Frame: ${"%.1f".format(d.frameMs)} ms")
            val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
            TextButton(onClick = {
                clipboard.setText(androidx.compose.ui.text.AnnotatedString(com.lensprompt.app.diag.Diagnostics.text()))
            }) { Text("Copy diagnostics", fontSize = 11.sp) }
        }
    }
}

@Composable
private fun QuickSettings(settings: AppSettings, vm: PrompterViewModel) {
    val app = LocalContext.current.applicationContext as com.lensprompt.app.LensPromptApplication
    val update = app.settings::update
    Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
        Text(stringResource(R.string.settings_section_display), style = MaterialTheme.typography.titleMedium)
        if (!settings.smartFollow) {
            LabeledSlider(stringResource(R.string.prompter_manual_speed), settings.manualSpeed, 1f..10f, "%.1f") { v -> update { it.copy(manualSpeed = v) } }
        }
        LabeledSlider(stringResource(R.string.settings_font_size), settings.fontSizeSp, 18f..72f, "%.0f sp") { v -> update { it.copy(fontSizeSp = v) } }
        LabeledSlider(stringResource(R.string.settings_line_spacing), settings.lineSpacing, 1.0f..2.2f, "%.2f×") { v -> update { it.copy(lineSpacing = v) } }
        LabeledSlider(stringResource(R.string.settings_margins), settings.marginFraction, 0f..0.25f, "%.2f") { v -> update { it.copy(marginFraction = v) } }
        LabeledSlider(stringResource(R.string.settings_reading_anchor), settings.anchorFraction, 0.2f..0.7f, "%.2f") { v -> update { it.copy(anchorFraction = v) } }
        LabeledSlider(stringResource(R.string.settings_background_dim), settings.backgroundDim, 0f..1f, "%.2f") { v -> update { it.copy(backgroundDim = v) } }
        LabeledSwitch(stringResource(R.string.settings_mirror_horizontal), settings.mirrorHorizontal) { v -> update { it.copy(mirrorHorizontal = v) } }
        LabeledSwitch(stringResource(R.string.settings_mirror_vertical), settings.mirrorVertical) { v -> update { it.copy(mirrorVertical = v) } }
        LabeledSwitch(stringResource(R.string.settings_center_text), settings.align == PromptAlign.CENTER) { v ->
            update { it.copy(align = if (v) PromptAlign.CENTER else PromptAlign.START) }
        }
        LabeledSwitch(stringResource(R.string.prompter_camera_preview), settings.showCamera) { v -> update { it.copy(showCamera = v) } }
        LabeledSwitch(stringResource(R.string.prompter_lip_tracking), settings.lipTracking) { v -> update { it.copy(lipTracking = v) } }
        // Simulated speech is a development tool: debug builds only.
        if (settings.debugMode && com.lensprompt.app.BuildConfig.DEBUG) {
            val ui by vm.ui.collectAsState()
            LabeledSwitch("Debug: simulated speech (no mic)", ui.simulating) { v -> vm.setSimulation(v) }
        }
    }
}
