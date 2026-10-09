package com.vrvision.app.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.vrvision.app.AppContainer
import com.vrvision.app.Navigator
import com.vrvision.app.player.HeadTracker
import com.vrvision.app.player.RenderConfig
import com.vrvision.app.player.TestPattern
import com.vrvision.app.player.VrSurface
import com.vrvision.app.ui.components.LabeledSlider
import com.vrvision.app.ui.components.SwitchRow
import com.vrvision.core.calibration.CalibrationCodec
import com.vrvision.core.calibration.HeadsetCalibration
import com.vrvision.core.calibration.HeadsetCalibration.Limits
import kotlinx.coroutines.launch
import java.util.Locale

@Composable
fun CalibrationScreen(c: AppContainer, nav: Navigator) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs by c.settings.state.collectAsState()
    val tracker = remember { HeadTracker(context) }
    var profiles by remember { mutableStateOf(listOf<HeadsetCalibration>()) }
    var cal by remember { mutableStateOf(HeadsetCalibration()) }
    var pattern by remember { mutableStateOf(TestPattern.GRID) }
    var panel by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf<String?>(null) }

    suspend fun reload() {
        val active = c.profiles.active()
        profiles = c.profiles.profiles()
        cal = active
    }
    LaunchedEffect(Unit) { reload() }
    ImmersiveLandscape(keepScreenOn = true)

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        VrSurface(
            config = RenderConfig(calibration = cal, headsetMode = true, pattern = pattern),
            videoSize = Pair(0, 0),
            tracker = tracker,
            respectCutout = prefs.respectCutout,
            modifier = Modifier.fillMaxSize(),
            onTap = { panel = !panel },
        )
        if (!panel) {
            Text(
                "Tap the screen to show calibration controls",
                color = Color(0xFF9DA9B5),
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 16.dp),
            )
            return@Box
        }
        Column(
            Modifier.align(Alignment.CenterEnd).fillMaxHeight().width(420.dp)
                .background(Color(0xEE0E1116)).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Headset calibration", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                OutlinedButton(onClick = nav::back) { Text("Done") }
            }
            Text(
                "Put the phone in the headset with the panel hidden (tap to hide). Grid lines should look " +
                    "straight and the green crosses should sit in the middle of each lens. The red dot must be " +
                    "seen only by the left eye and the blue dot only by the right eye.",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
            )
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                profiles.forEach { p ->
                    FilterChip(selected = p.id == cal.id, onClick = {
                        scope.launch { c.profiles.select(p.id); reload() }
                    }, label = { Text(p.name) })
                }
            }
            OutlinedTextField(
                value = cal.name, onValueChange = { cal = cal.copy(name = it.take(HeadsetCalibration.MAX_NAME)) },
                label = { Text("Profile name") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(TestPattern.GRID to "Grid", TestPattern.CHECKERBOARD to "Checkerboard").forEach { (p, l) ->
                    FilterChip(selected = pattern == p, onClick = { pattern = p }, label = { Text(l) })
                }
            }

            Text("Lens geometry", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            Text(
                "Physical IPD is fixed by your headset's lenses (or its IPD slider). Lens separation here only " +
                    "moves each eye's image under its lens; it cannot change optical IPD.",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
            )
            LabeledSlider("Lens separation (mm)", cal.lensSeparationMm, Limits.LENS_SEPARATION_MM, { cal = cal.copy(lensSeparationMm = it) }) { "%.1f".fmt(it) }
            LabeledSlider("Lens height from bottom (mm, 0 = centered)", cal.lensToBottomMm, Limits.LENS_TO_BOTTOM_MM, { cal = cal.copy(lensToBottomMm = it) }) { "%.0f".fmt(it) }
            SwitchRow("Lens distortion correction", cal.distortionEnabled, { cal = cal.copy(distortionEnabled = it) })
            LabeledSlider("Distortion k1", cal.k1, Limits.K1, { cal = cal.copy(k1 = it) })
            LabeledSlider("Distortion k2", cal.k2, Limits.K2, { cal = cal.copy(k2 = it) })

            Text("Per-eye optical centers", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            LabeledSlider("Left eye horizontal", cal.leftCenterOffsetX, Limits.CENTER_OFFSET, { cal = cal.copy(leftCenterOffsetX = it) }) { "%.3f".fmt(it) }
            LabeledSlider("Left eye vertical", cal.leftCenterOffsetY, Limits.CENTER_OFFSET, { cal = cal.copy(leftCenterOffsetY = it) }) { "%.3f".fmt(it) }
            LabeledSlider("Right eye horizontal", cal.rightCenterOffsetX, Limits.CENTER_OFFSET, { cal = cal.copy(rightCenterOffsetX = it) }) { "%.3f".fmt(it) }
            LabeledSlider("Right eye vertical", cal.rightCenterOffsetY, Limits.CENTER_OFFSET, { cal = cal.copy(rightCenterOffsetY = it) }) { "%.3f".fmt(it) }

            Text("Image", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            LabeledSlider("Horizontal image offset", cal.imageOffsetX, Limits.IMAGE_OFFSET, { cal = cal.copy(imageOffsetX = it) }) { "%.3f".fmt(it) }
            LabeledSlider("Vertical image offset", cal.imageOffsetY, Limits.IMAGE_OFFSET, { cal = cal.copy(imageOffsetY = it) }) { "%.3f".fmt(it) }
            LabeledSlider("Zoom", cal.zoom, Limits.ZOOM, { cal = cal.copy(zoom = it) })
            LabeledSlider("Field of view (°)", cal.fovDegrees, Limits.FOV_DEG, { cal = cal.copy(fovDegrees = it) }) { "%.0f".fmt(it) }
            LabeledSlider("Edge margin", cal.viewportMargin, Limits.VIEWPORT_MARGIN, { cal = cal.copy(viewportMargin = it) })

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { scope.launch { cal = c.profiles.save(cal); profiles = c.profiles.profiles(); message = "Saved" } }, modifier = Modifier.height(52.dp)) { Text("Save") }
                FilledTonalButton(onClick = {
                    scope.launch { val n = c.profiles.createFrom(cal, cal.name); c.profiles.select(n.id); reload(); message = "Created \"${n.name}\"" }
                }, modifier = Modifier.height(52.dp)) { Text("Save as new") }
                OutlinedButton(onClick = { cal = HeadsetCalibration(id = cal.id, name = cal.name) }, modifier = Modifier.height(52.dp)) { Text("Defaults") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    clipboard(context).setPrimaryClip(ClipData.newPlainText("VRVision calibration", CalibrationCodec.encode(cal)))
                    message = "Profile copied to clipboard as JSON"
                }) { Text("Export") }
                OutlinedButton(onClick = {
                    val text = clipboard(context).primaryClip?.getItemAt(0)?.text?.toString()
                    scope.launch {
                        message = try {
                            val p = c.profiles.importJson(text ?: "")
                            c.profiles.select(p.id); reload(); "Imported \"${p.name}\""
                        } catch (e: IllegalArgumentException) { "Clipboard does not contain a valid profile: ${e.message}" }
                    }
                }) { Text("Import") }
                OutlinedButton(onClick = {
                    scope.launch { message = if (c.profiles.delete(cal.id)) { reload(); "Deleted" } else "The last profile can't be deleted" }
                }) { Text("Delete") }
            }
            message?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
        }
    }
}

private fun clipboard(context: Context) = context.getSystemService(ClipboardManager::class.java)
private fun String.fmt(v: Float) = String.format(Locale.US, this, v)
