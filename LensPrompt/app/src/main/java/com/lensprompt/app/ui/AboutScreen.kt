package com.lensprompt.app.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lensprompt.app.BuildConfig

/** Open-source components shipped in the app (attribution). */
private data class License(val name: String, val license: String, val url: String)

private val LICENSES = listOf(
    License("AndroidX, Jetpack Compose, CameraX, Material 3", "Apache License 2.0", "https://www.apache.org/licenses/LICENSE-2.0"),
    License("Kotlin, kotlinx.coroutines", "Apache License 2.0", "https://www.apache.org/licenses/LICENSE-2.0"),
    License("Vosk speech recognition (vosk-android)", "Apache License 2.0", "https://github.com/alphacep/vosk-api"),
    License("Kaldi (inside Vosk)", "Apache License 2.0", "https://github.com/kaldi-asr/kaldi"),
    License("JNA – Java Native Access", "Apache License 2.0 (dual-licensed with LGPL 2.1)", "https://github.com/java-native-access/jna"),
    License("ML Kit Face Detection", "ML Kit Terms of Service", "https://developers.google.com/ml-kit/terms"),
    License("Google Play Billing Library", "Android Software Development Kit License", "https://developer.android.com/studio/terms"),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    fun open(url: String) = runCatching {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } },
                title = { Text("About LensPrompt") },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp)) {
            Text("LensPrompt ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})", style = MaterialTheme.typography.titleMedium)
            Text("A teleprompter that works over the camera you already use.", color = LensColors.Muted)

            Spacer(Modifier.height(20.dp))
            Text("Your data", fontWeight = FontWeight.SemiBold, color = LensColors.Accent)
            Text(
                "• Scripts and settings are stored on this phone. If Android backup is on, they are included in your device backup.\n" +
                    "• LensPrompt has no account, no ads and no analytics, and it does not upload your scripts, audio or video.\n" +
                    "• Smart Follow with an offline speech pack recognizes speech inside LensPrompt. Without a pack, your phone's " +
                    "speech recognition service (for example Google or Samsung) does it and may process audio online under that provider's terms.\n" +
                    "• Videos you record are saved to Movies/LensPrompt on this phone.\n" +
                    "• Offline speech packs are downloaded from alphacephei.com only when you ask.",
                color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
            )
            if (BuildConfig.PRIVACY_POLICY_URL.isNotBlank()) {
                TextButton(onClick = { open(BuildConfig.PRIVACY_POLICY_URL) }) { Text("Privacy policy") }
            }
            if (BuildConfig.SUPPORT_EMAIL.isNotBlank()) {
                TextButton(onClick = { open("mailto:${BuildConfig.SUPPORT_EMAIL}") }) { Text("Contact support") }
            }

            Spacer(Modifier.height(20.dp))
            Text("Open-source licenses", fontWeight = FontWeight.SemiBold, color = LensColors.Accent)
            LICENSES.forEach { l ->
                Column(Modifier.padding(vertical = 6.dp)) {
                    Text(l.name)
                    Text(l.license, color = LensColors.Muted, style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = { open(l.url) }, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) {
                        Text(l.url, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Text(
                "Offline speech packs are Vosk models by Alpha Cephei, downloaded at your request; each model's license is listed at alphacephei.com/vosk/models.",
                color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(32.dp))
        }
    }
}
