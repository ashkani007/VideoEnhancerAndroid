import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';

/// Profile imagery. Real photos when available; otherwise a generated abstract portrait
/// (used for fictional demo profiles — no stock photos of real people).
class Portrait extends StatelessWidget {
  const Portrait({super.key, required this.name, this.url, this.borderRadius = FmRadius.lg, this.parallax = Offset.zero, this.initialSize});

  final String name;
  final String? url;
  final double borderRadius;
  final Offset parallax;
  final double? initialSize;

  static List<Color> palette(String seed) {
    final h = seed.codeUnits.fold<int>(7, (a, c) => (a * 31 + c) & 0x7fffffff);
    final hue = (h % 360).toDouble();
    return [
      HSLColor.fromAHSL(1, hue, 0.62, 0.42).toColor(),
      HSLColor.fromAHSL(1, (hue + 48) % 360, 0.70, 0.58).toColor(),
      HSLColor.fromAHSL(1, (hue + 200) % 360, 0.55, 0.30).toColor(),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final cols = palette(name);
    Widget art = CustomPaint(
      painter: _PortraitPainter(cols, parallax),
      child: LayoutBuilder(
        builder: (ctx, c) => Center(
          child: Transform.translate(
            offset: parallax * 0.6,
            child: Text(
              name.isEmpty ? '?' : name.characters.first.toUpperCase(),
              style: TextStyle(
                fontFamily: 'Jakarta',
                fontWeight: FontWeight.w800,
                fontSize: initialSize ?? c.maxWidth * 0.62,
                height: 1,
                color: Colors.white.withValues(alpha: 0.22),
              ),
            ),
          ),
        ),
      ),
    );
    if (url != null && url!.isNotEmpty) {
      art = Stack(fit: StackFit.expand, children: [
        art,
        Transform.translate(
          offset: parallax,
          child: Transform.scale(
            scale: 1.08,
            child: Image.network(url!, fit: BoxFit.cover, errorBuilder: (_, _, _) => const SizedBox.shrink()),
          ),
        ),
      ]);
    }
    return ClipRRect(borderRadius: BorderRadius.circular(borderRadius), child: art);
  }
}

class _PortraitPainter extends CustomPainter {
  _PortraitPainter(this.cols, this.parallax);
  final List<Color> cols;
  final Offset parallax;

  @override
  void paint(Canvas canvas, Size size) {
    final r = Offset.zero & size;
    canvas.drawRect(r, Paint()..shader = LinearGradient(colors: [cols[2], cols[0]], begin: Alignment.bottomLeft, end: Alignment.topRight).createShader(r));
    void blob(Offset c, double radius, Color color) {
      canvas.drawCircle(
        c + parallax * 0.5,
        radius,
        Paint()
          ..shader = RadialGradient(colors: [color.withValues(alpha: 0.85), color.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: c, radius: radius)),
      );
    }

    blob(Offset(size.width * 0.8, size.height * 0.18), size.width * 0.75, cols[1]);
    blob(Offset(size.width * 0.1, size.height * 0.7), size.width * 0.6, cols[0]);
    // Fine diagonal sheen for depth.
    canvas.drawRect(
      r,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Colors.white.withValues(alpha: 0.10), Colors.transparent, Colors.black.withValues(alpha: 0.18)],
        ).createShader(r),
    );
  }

  @override
  bool shouldRepaint(covariant _PortraitPainter old) => old.parallax != parallax || old.cols != cols;
}

class GlassPanel extends StatelessWidget {
  const GlassPanel({super.key, required this.child, this.radius = FmRadius.md, this.padding = const EdgeInsets.all(FmSpace.md), this.blur = 18, this.tint});
  final Widget child;
  final double radius, blur;
  final EdgeInsets padding;
  final Color? tint;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: tint ?? fm.glass,
            borderRadius: BorderRadius.circular(radius),
            border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
          ),
          child: child,
        ),
      ),
    );
  }
}

/// Primary call-to-action with brand gradient, press-scale micro-interaction and haptics.
class FmButton extends StatefulWidget {
  const FmButton({super.key, required this.label, this.onPressed, this.icon, this.loading = false, this.secondary = false, this.expand = true, this.dense = false});
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading, secondary, expand, dense;

  @override
  State<FmButton> createState() => _FmButtonState();
}

class _FmButtonState extends State<FmButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final enabled = widget.onPressed != null && !widget.loading;
    final fg = widget.secondary ? fm.text : Colors.white;
    final content = Row(
      mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.loading)
          SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2.2, color: fg))
        else ...[
          if (widget.icon != null) ...[Icon(widget.icon, color: fg, size: 20), const SizedBox(width: 8)],
          Flexible(child: Text(widget.label, overflow: TextOverflow.ellipsis, style: context.text.labelLarge?.copyWith(color: fg))),
        ],
      ],
    );
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      child: GestureDetector(
        onTapDown: enabled ? (_) => setState(() => _down = true) : null,
        onTapCancel: () => setState(() => _down = false),
        onTapUp: enabled ? (_) => setState(() => _down = false) : null,
        onTap: enabled
            ? () {
                HapticFeedback.selectionClick();
                widget.onPressed!();
              }
            : null,
        child: AnimatedScale(
          scale: _down ? 0.96 : 1,
          duration: FmMotion.of(context, FmMotion.fast),
          child: AnimatedOpacity(
            opacity: enabled || widget.loading ? 1 : 0.45,
            duration: FmMotion.of(context, FmMotion.fast),
            child: Container(
              height: widget.dense ? 44 : 56,
              padding: const EdgeInsets.symmetric(horizontal: 22),
              decoration: BoxDecoration(
                gradient: widget.secondary ? null : fm.brandGradient,
                color: widget.secondary ? fm.surfaceHigh : null,
                borderRadius: BorderRadius.circular(FmRadius.pill),
                border: widget.secondary ? Border.all(color: fm.stroke) : null,
                boxShadow: widget.secondary
                    ? null
                    : [BoxShadow(color: fm.accent.withValues(alpha: 0.35), blurRadius: 24, offset: const Offset(0, 10))],
              ),
              child: content,
            ),
          ),
        ),
      ),
    );
  }
}

class Tag extends StatelessWidget {
  const Tag(this.label, {super.key, this.icon, this.highlighted = false, this.onDark = false});
  final String label;
  final IconData? icon;
  final bool highlighted, onDark;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final fg = onDark ? Colors.white : (highlighted ? fm.accent : fm.text);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: onDark ? Colors.white.withValues(alpha: 0.16) : (highlighted ? fm.accent.withValues(alpha: 0.14) : fm.surfaceHigh),
        borderRadius: BorderRadius.circular(FmRadius.pill),
        border: Border.all(color: highlighted ? fm.accent.withValues(alpha: 0.4) : Colors.transparent),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 14, color: fg), const SizedBox(width: 5)],
        Text(label, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: fg)),
      ]),
    );
  }
}

class DemoBadge extends StatelessWidget {
  const DemoBadge({super.key, this.compact = false});
  final bool compact;

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Demo: fictional profile',
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: compact ? 7 : 10, vertical: compact ? 3 : 5),
          decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.45), borderRadius: BorderRadius.circular(FmRadius.pill)),
          child: Text(compact ? 'DEMO' : 'DEMO · FICTIONAL',
              style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.8)),
        ),
      );
}

class VerifiedBadge extends StatelessWidget {
  const VerifiedBadge({super.key, this.size = 18});
  final double size;
  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Photo verified',
        child: Icon(Icons.verified_rounded, size: size, color: const Color(0xFF60A5FA)),
      );
}

/// Shimmering placeholder used for skeleton loading states.
class Skeleton extends StatefulWidget {
  const Skeleton({super.key, this.width, this.height, this.radius = FmRadius.md});
  final double? width, height;
  final double radius;

  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (FmMotion.reduced(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return AnimatedBuilder(
      animation: _c,
      builder: (_, _) => Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(widget.radius),
          gradient: LinearGradient(
            begin: Alignment(-1 + 2 * _c.value - 1, -0.3),
            end: Alignment(1 + 2 * _c.value - 1, 0.3),
            colors: [fm.surface, fm.surfaceHigh, fm.surface],
          ),
        ),
      ),
    );
  }
}

class MessageState extends StatelessWidget {
  const MessageState({super.key, required this.icon, required this.title, required this.body, this.action, this.actionLabel});
  final IconData icon;
  final String title, body;
  final VoidCallback? action;
  final String? actionLabel;

  factory MessageState.error(Object error, {VoidCallback? onRetry}) {
    final offline = error is ApiException && error.isOffline;
    return MessageState(
      icon: offline ? Icons.wifi_off_rounded : Icons.error_outline_rounded,
      title: offline ? "You're offline" : 'Something went wrong',
      body: error is ApiException ? error.message : 'Please try again in a moment.',
      action: onRetry,
      actionLabel: 'Try again',
    );
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(FmSpace.xl),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 76,
            height: 76,
            decoration: BoxDecoration(shape: BoxShape.circle, color: fm.accent.withValues(alpha: 0.12)),
            child: Icon(icon, color: fm.accent, size: 34),
          ),
          const SizedBox(height: FmSpace.lg),
          Text(title, style: context.text.headlineSmall, textAlign: TextAlign.center),
          const SizedBox(height: FmSpace.xs),
          Text(body, style: context.text.bodyMedium?.copyWith(color: fm.textMuted), textAlign: TextAlign.center),
          if (action != null) ...[
            const SizedBox(height: FmSpace.lg),
            FmButton(label: actionLabel ?? 'Continue', onPressed: action, expand: false, secondary: true),
          ],
        ]),
      ),
    );
  }
}

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.children, this.title});
  final List<Widget> children;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (title != null)
        Padding(
          padding: const EdgeInsets.fromLTRB(FmSpace.xs, FmSpace.lg, FmSpace.xs, FmSpace.xs),
          child: Text(title!.toUpperCase(), style: context.text.labelSmall),
        ),
      Container(
        decoration: BoxDecoration(color: fm.surface, borderRadius: BorderRadius.circular(FmRadius.lg), border: Border.all(color: fm.stroke)),
        child: Column(children: [
          for (var i = 0; i < children.length; i++) ...[
            children[i],
            if (i < children.length - 1) Divider(indent: FmSpace.md, endIndent: FmSpace.md, color: fm.stroke),
          ],
        ]),
      ),
    ]);
  }
}

/// Ambient background glow used behind hero screens.
class AmbientBackground extends StatelessWidget {
  const AmbientBackground({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Stack(children: [
      Positioned.fill(child: ColoredBox(color: fm.background)),
      Positioned(
        top: -160,
        left: -120,
        child: _Glow(color: fm.accent.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? 0.32 : 0.18), size: 420),
      ),
      Positioned(
        top: 120,
        right: -180,
        child: _Glow(color: fm.accent2.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? 0.20 : 0.12), size: 380),
      ),
      Positioned.fill(child: child),
    ]);
  }
}

class _Glow extends StatelessWidget {
  const _Glow({required this.color, required this.size});
  final Color color;
  final double size;
  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: Container(
          width: size,
          height: size,
          decoration: BoxDecoration(shape: BoxShape.circle, gradient: RadialGradient(colors: [color, color.withValues(alpha: 0)])),
        ),
      );
}

String lifestyleLabel(String key, String value) {
  const keys = {'smoking': 'Smoking', 'drinking': 'Drinking', 'exercise': 'Exercise', 'kids_want': 'Kids', 'pets': 'Pets', 'diet': 'Diet', 'sleep': 'Sleep'};
  return '${keys[key] ?? key}: ${value.replaceAll('_', ' ')}';
}

double clampDouble(double v, double lo, double hi) => math.min(hi, math.max(lo, v));

IconData intentIcon(String? intent) => switch (intent) {
      'long_term' => Icons.favorite_rounded,
      'long_term_open_short' || 'short_term_open_long' => Icons.all_inclusive_rounded,
      'short_term' => Icons.local_fire_department_rounded,
      'friendship_first' => Icons.emoji_people_rounded,
      _ => Icons.explore_rounded,
    };

String? shortIntent(String? intent) => switch (intent) {
      'long_term' => 'Long-term',
      'long_term_open_short' => 'Long-term, open',
      'short_term_open_long' => 'Short-term, open',
      'short_term' => 'Casual',
      'friendship_first' => 'Friendship first',
      'figuring_out' => 'Figuring it out',
      _ => null,
    };

String profileSubtitle(ProfileCard p) => [p.intentLabel, p.distance].whereType<String>().join(' · ');
