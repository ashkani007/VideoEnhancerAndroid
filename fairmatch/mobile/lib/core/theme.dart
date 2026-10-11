import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// FairMatch design tokens. Every colour, radius, space and duration in the app
/// comes from here so the visual language stays coherent.
class FmSpace {
  static const double xxs = 4, xs = 8, sm = 12, md = 16, lg = 24, xl = 32, xxl = 48;
}

class FmRadius {
  static const double sm = 12, md = 18, lg = 26, xl = 34, pill = 999;
}

class FmMotion {
  static const fast = Duration(milliseconds: 180);
  static const medium = Duration(milliseconds: 320);
  static const slow = Duration(milliseconds: 560);
  static const curve = Curves.easeOutCubic;
  static const spring = Curves.easeOutBack;

  /// Honour the OS "remove animations" accessibility setting.
  static bool reduced(BuildContext context) => MediaQuery.maybeDisableAnimationsOf(context) ?? false;

  static Duration of(BuildContext context, Duration d) => reduced(context) ? Duration.zero : d;
}

@immutable
class FmColors extends ThemeExtension<FmColors> {
  const FmColors({
    required this.background,
    required this.surface,
    required this.surfaceHigh,
    required this.stroke,
    required this.accent,
    required this.accent2,
    required this.text,
    required this.textMuted,
    required this.success,
    required this.warning,
    required this.danger,
    required this.glass,
  });

  final Color background, surface, surfaceHigh, stroke, accent, accent2, text, textMuted, success, warning, danger, glass;

  LinearGradient get brandGradient => LinearGradient(colors: [accent, accent2], begin: Alignment.topLeft, end: Alignment.bottomRight);

  static const dark = FmColors(
    background: Color(0xFF0B0B14),
    surface: Color(0xFF171725),
    surfaceHigh: Color(0xFF212134),
    stroke: Color(0x1FFFFFFF),
    accent: Color(0xFF8B5CF6),
    accent2: Color(0xFFFF6B9A),
    text: Color(0xFFFFFFFF),
    textMuted: Color(0xFFA6A6BC),
    success: Color(0xFF34D399),
    warning: Color(0xFFFBBF24),
    danger: Color(0xFFF87171),
    glass: Color(0x1AFFFFFF),
  );

  static const light = FmColors(
    background: Color(0xFFF6F4FB),
    surface: Color(0xFFFFFFFF),
    surfaceHigh: Color(0xFFEFEBF8),
    stroke: Color(0x14000000),
    accent: Color(0xFF7C3AED),
    accent2: Color(0xFFE5487D),
    text: Color(0xFF14131F),
    textMuted: Color(0xFF615E77),
    success: Color(0xFF059669),
    warning: Color(0xFFB45309),
    danger: Color(0xFFDC2626),
    glass: Color(0xB3FFFFFF),
  );

  @override
  FmColors copyWith() => this;

  @override
  FmColors lerp(ThemeExtension<FmColors>? other, double t) {
    if (other is! FmColors) return this;
    Color l(Color a, Color b) => Color.lerp(a, b, t)!;
    return FmColors(
      background: l(background, other.background),
      surface: l(surface, other.surface),
      surfaceHigh: l(surfaceHigh, other.surfaceHigh),
      stroke: l(stroke, other.stroke),
      accent: l(accent, other.accent),
      accent2: l(accent2, other.accent2),
      text: l(text, other.text),
      textMuted: l(textMuted, other.textMuted),
      success: l(success, other.success),
      warning: l(warning, other.warning),
      danger: l(danger, other.danger),
      glass: l(glass, other.glass),
    );
  }
}

extension FmThemeX on BuildContext {
  FmColors get fm => Theme.of(this).extension<FmColors>()!;
  TextTheme get text => Theme.of(this).textTheme;
}

ThemeData buildTheme(Brightness brightness) {
  final c = brightness == Brightness.dark ? FmColors.dark : FmColors.light;
  final base = ThemeData(brightness: brightness, useMaterial3: true, fontFamily: 'Inter');
  TextStyle display(double size, FontWeight w, {double ls = -0.5}) =>
      TextStyle(fontFamily: 'Jakarta', fontSize: size, fontWeight: w, letterSpacing: ls, color: c.text, height: 1.12);
  final textTheme = base.textTheme.copyWith(
    displayLarge: display(44, FontWeight.w800, ls: -1.2),
    displayMedium: display(36, FontWeight.w800, ls: -1),
    displaySmall: display(30, FontWeight.w700, ls: -0.8),
    headlineMedium: display(26, FontWeight.w700),
    headlineSmall: display(22, FontWeight.w700, ls: -0.3),
    titleLarge: display(19, FontWeight.w700, ls: -0.2),
    titleMedium: TextStyle(fontFamily: 'Inter', fontSize: 16, fontWeight: FontWeight.w600, color: c.text),
    titleSmall: TextStyle(fontFamily: 'Inter', fontSize: 14, fontWeight: FontWeight.w600, color: c.text),
    bodyLarge: TextStyle(fontFamily: 'Inter', fontSize: 16, height: 1.45, color: c.text),
    bodyMedium: TextStyle(fontFamily: 'Inter', fontSize: 14.5, height: 1.45, color: c.text),
    bodySmall: TextStyle(fontFamily: 'Inter', fontSize: 12.5, height: 1.4, color: c.textMuted),
    labelLarge: TextStyle(fontFamily: 'Inter', fontSize: 15, fontWeight: FontWeight.w600, color: c.text, letterSpacing: 0.1),
    labelMedium: TextStyle(fontFamily: 'Inter', fontSize: 13, fontWeight: FontWeight.w600, color: c.textMuted),
    labelSmall: TextStyle(fontFamily: 'Inter', fontSize: 11, fontWeight: FontWeight.w700, color: c.textMuted, letterSpacing: 0.6),
  );
  final scheme = ColorScheme.fromSeed(
    seedColor: c.accent,
    brightness: brightness,
    primary: c.accent,
    secondary: c.accent2,
    surface: c.surface,
    error: c.danger,
  );
  return base.copyWith(
    colorScheme: scheme,
    scaffoldBackgroundColor: c.background,
    textTheme: textTheme,
    extensions: [c],
    splashFactory: InkSparkle.splashFactory,
    appBarTheme: AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      foregroundColor: c.text,
      titleTextStyle: textTheme.titleLarge,
      systemOverlayStyle: brightness == Brightness.dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
    ),
    dividerTheme: DividerThemeData(color: c.stroke, thickness: 1, space: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: c.surfaceHigh,
      hintStyle: TextStyle(color: c.textMuted),
      labelStyle: TextStyle(color: c.textMuted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(FmRadius.md), borderSide: BorderSide.none),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(FmRadius.md),
        borderSide: BorderSide(color: c.stroke),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(FmRadius.md),
        borderSide: BorderSide(color: c.accent, width: 1.6),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(FmRadius.md),
        borderSide: BorderSide(color: c.danger),
      ),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Colors.white : c.textMuted),
      trackColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? c.accent : c.surfaceHigh),
      trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
    ),
    sliderTheme: SliderThemeData(
      activeTrackColor: c.accent,
      thumbColor: Colors.white,
      inactiveTrackColor: c.surfaceHigh,
      overlayColor: c.accent.withValues(alpha: 0.15),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: c.surfaceHigh,
      contentTextStyle: TextStyle(color: c.text, fontFamily: 'Inter'),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(FmRadius.md)),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: c.surface,
      modalBackgroundColor: c.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(FmRadius.xl))),
      showDragHandle: true,
      dragHandleColor: c.textMuted.withValues(alpha: 0.4),
    ),
    pageTransitionsTheme: const PageTransitionsTheme(builders: {TargetPlatform.android: FadeForwardsPageTransitionsBuilder()}),
  );
}
