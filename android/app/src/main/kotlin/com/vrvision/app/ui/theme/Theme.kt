package com.vrvision.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val Accent = Color(0xFF5EC8FF)
val AccentDim = Color(0xFF1E4F6B)
val Background = Color(0xFF0E1116)
val Surface1 = Color(0xFF161B22)
val Surface2 = Color(0xFF1F2630)
val Ok = Color(0xFF5FD38D)
val Warn = Color(0xFFFFC857)
val Danger = Color(0xFFFF6B6B)

private val scheme = darkColorScheme(
    primary = Accent,
    onPrimary = Color(0xFF00121D),
    primaryContainer = AccentDim,
    onPrimaryContainer = Color(0xFFD7F1FF),
    secondary = Color(0xFFB4C7D9),
    background = Background,
    onBackground = Color(0xFFE6EDF3),
    surface = Surface1,
    onSurface = Color(0xFFE6EDF3),
    surfaceVariant = Surface2,
    onSurfaceVariant = Color(0xFF9DA9B5),
    surfaceContainer = Surface1,
    surfaceContainerHigh = Surface2,
    error = Danger,
    outline = Color(0xFF3A4552),
)

private val typography = Typography(
    headlineMedium = TextStyle(fontSize = 26.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.sp),
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Medium),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 22.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.Medium),
)

@Composable
fun VRVisionTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = scheme, typography = typography, content = content)
}
