package com.lensprompt.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

object LensColors {
    val Background = Color(0xFF0B0B0D)
    val Surface = Color(0xFF16161A)
    val SurfaceHigh = Color(0xFF222228)
    val Accent = Color(0xFFFFC83D)
    val OnAccent = Color(0xFF1A1400)
    val Recording = Color(0xFFFF3B30)
    val Listening = Color(0xFF34C759)
    val Muted = Color(0xFFA0A0A8)
}

private val scheme = darkColorScheme(
    primary = LensColors.Accent,
    onPrimary = LensColors.OnAccent,
    secondary = Color(0xFF7FD1C7),
    onSecondary = Color.Black,
    background = LensColors.Background,
    onBackground = Color(0xFFF2F2F5),
    surface = LensColors.Surface,
    onSurface = Color(0xFFF2F2F5),
    surfaceVariant = LensColors.SurfaceHigh,
    onSurfaceVariant = LensColors.Muted,
    error = LensColors.Recording,
)

@Composable
fun LensPromptTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = scheme, content = content)
}
