package com.lensprompt.app.ui

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.MediaStore
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import com.lensprompt.app.overlay.OverlayService

/**
 * "Use with phone camera": explains the floating teleprompter, walks through the
 * permissions it needs (display over other apps; microphone for Smart Follow;
 * notifications for the foreground service) and starts it for [scriptId].
 */
@Composable
fun FloatingPrompterDialog(scriptId: String?, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var canDraw by remember { mutableStateOf(OverlayService.canDrawOverlays(context)) }
    var openCameraAfter by remember { mutableStateOf(true) }

    fun launch() {
        OverlayService.start(context, scriptId)
        if (openCameraAfter) openCameraApp(context)
        onDismiss()
    }

    val notifLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { launch() }
    fun afterMic() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            launch()
        }
    }
    // The microphone must be granted before the service starts: Android only lets a
    // foreground service use the mic if it had the permission when it started.
    val micLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { afterMic() }
    fun proceed() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            micLauncher.launch(Manifest.permission.RECORD_AUDIO)
        } else {
            afterMic()
        }
    }
    val overlayLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        canDraw = OverlayService.canDrawOverlays(context)
        if (canDraw) proceed()
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Use with phone camera") },
        text = {
            Column {
                Text(
                    "A floating teleprompter stays on top of Samsung Camera, Google Camera, Instagram or any other " +
                        "camera app. Move it by the ⠿ handle, resize it from the bottom edge and corner, and use ⚙ for " +
                        "text size, speed and transparency.",
                )
                Text(
                    "\nSmart Follow listens with LensPrompt's microphone. If the camera app records video WITH sound, " +
                        "Android gives it the microphone and other apps hear silence; the teleprompter then scrolls at " +
                        "your manual speed and resumes following when the microphone is free.",
                    color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
                )
                if (!canDraw) {
                    Text(
                        "\nFirst, allow LensPrompt to \"Display over other apps\" on the next screen, then come back.",
                        color = LensColors.Accent, style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                openCameraAfter = true
                if (canDraw) proceed() else overlayLauncher.launch(OverlayService.permissionIntent(context))
            }) { Text(if (canDraw) "Start & open camera" else "Allow display over apps") }
        },
        dismissButton = {
            if (canDraw) {
                TextButton(onClick = { openCameraAfter = false; proceed() }) { Text("Start only") }
            } else {
                TextButton(onClick = onDismiss) { Text("Cancel") }
            }
        },
    )
}

fun openCameraApp(context: Context) {
    for (action in listOf(MediaStore.INTENT_ACTION_VIDEO_CAMERA, MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA)) {
        try {
            context.startActivity(Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        } catch (_: ActivityNotFoundException) {
        } catch (_: SecurityException) {
        }
    }
}

/**
 * Shown inside LensPrompt while the floating teleprompter is on, with a
 * prominent way to stop it (the third exit, next to × on the overlay and
 * "Stop teleprompter" in the notification).
 */
@Composable
fun FloatingModeBanner(modifier: Modifier = Modifier) {
    val running by OverlayService.runningState.collectAsState()
    if (!running) return
    val context = LocalContext.current
    Surface(
        color = LensColors.SurfaceHigh,
        shape = RoundedCornerShape(14.dp),
        modifier = modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                "Floating Teleprompter is running",
                color = Color.White,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            Button(
                onClick = { OverlayService.stop(context) },
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC62828), contentColor = Color.White),
            ) { Text("STOP FLOATING MODE") }
        }
    }
}
