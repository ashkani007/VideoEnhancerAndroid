import 'dart:ui';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';

/// Shown only after the server confirms mutual interest. Returns true for "Say hello".
Future<bool?> showMatchCelebration(BuildContext context, {required String me, required ProfileCard other}) {
  return showGeneralDialog<bool>(
    context: context,
    barrierDismissible: false,
    barrierColor: Colors.black.withValues(alpha: 0.6),
    transitionDuration: FmMotion.of(context, FmMotion.slow),
    pageBuilder: (ctx, a, _) => _MatchCelebration(me: me, other: other, animation: a),
  );
}

class _MatchCelebration extends StatefulWidget {
  const _MatchCelebration({required this.me, required this.other, required this.animation});
  final String me;
  final ProfileCard other;
  final Animation<double> animation;

  @override
  State<_MatchCelebration> createState() => _MatchCelebrationState();
}

class _MatchCelebrationState extends State<_MatchCelebration> with SingleTickerProviderStateMixin {
  late final AnimationController _loop = AnimationController(vsync: this, duration: const Duration(seconds: 4));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!FmMotion.reduced(context) && !_loop.isAnimating) _loop.repeat();
  }

  @override
  void dispose() {
    _loop.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final a = CurvedAnimation(parent: widget.animation, curve: Curves.easeOutBack);
    return Material(
      color: Colors.transparent,
      child: Stack(
        children: [
          Positioned.fill(
            child: FadeTransition(
              opacity: widget.animation,
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
                child: ColoredBox(color: fm.background.withValues(alpha: 0.72)),
              ),
            ),
          ),
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _loop,
              builder: (_, _) => CustomPaint(painter: _SparklePainter(_loop.value, [fm.accent, fm.accent2, Colors.white])),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(FmSpace.lg),
              child: Column(
                children: [
                  const Spacer(),
                  SizedBox(
                    height: 200,
                    child: AnimatedBuilder(
                      animation: a,
                      builder: (_, _) {
                        final t = a.value;
                        return Stack(
                          alignment: Alignment.center,
                          children: [
                            Container(
                              width: 230 * t.clamp(0, 1.2),
                              height: 230 * t.clamp(0, 1.2),
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                gradient: RadialGradient(colors: [fm.accent.withValues(alpha: 0.5), fm.accent2.withValues(alpha: 0)]),
                              ),
                            ),
                            Transform.translate(
                              offset: Offset(-58 * t - (1 - t) * 160, 0),
                              child: _Bubble(name: widget.me, color: fm.accent),
                            ),
                            Transform.translate(
                              offset: Offset(58 * t + (1 - t) * 160, 0),
                              child: Hero(
                                tag: 'portrait-${widget.other.id}',
                                child: _Bubble(name: widget.other.firstName, url: widget.other.photos.firstOrNull, color: fm.accent2),
                              ),
                            ),
                            Transform.scale(
                              scale: t,
                              child: Container(
                                width: 46,
                                height: 46,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  gradient: fm.brandGradient,
                                  boxShadow: [BoxShadow(color: fm.accent2.withValues(alpha: 0.6), blurRadius: 24)],
                                ),
                                child: const Icon(Icons.favorite_rounded, color: Colors.white, size: 24),
                              ),
                            ),
                          ],
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: FmSpace.xl),
                  FadeTransition(
                    opacity: widget.animation,
                    child: Column(
                      children: [
                        ShaderMask(
                          shaderCallback: (r) => fm.brandGradient.createShader(r),
                          child: Text("It's mutual.", style: context.text.displayMedium?.copyWith(color: Colors.white)),
                        ),
                        const SizedBox(height: FmSpace.sm),
                        Text(
                          'You and ${widget.other.firstName} chose each other.',
                          textAlign: TextAlign.center,
                          style: context.text.titleMedium?.copyWith(color: Colors.white),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Take your time — a thoughtful first message goes a long way.',
                          textAlign: TextAlign.center,
                          style: context.text.bodyMedium?.copyWith(color: Colors.white70),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  FmButton(label: 'Say hello', icon: Icons.chat_bubble_rounded, onPressed: () => Navigator.pop(context, true)),
                  const SizedBox(height: FmSpace.sm),
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Keep discovering', style: TextStyle(color: Colors.white70)),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.name, required this.color, this.url});
  final String name;
  final String? url;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    width: 132,
    height: 132,
    padding: const EdgeInsets.all(4),
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      color: color,
      boxShadow: [BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 30)],
    ),
    child: ClipOval(
      child: Portrait(name: name, url: url, borderRadius: 0),
    ),
  );
}

class _SparklePainter extends CustomPainter {
  _SparklePainter(this.t, this.colors);
  final double t;
  final List<Color> colors;

  @override
  void paint(Canvas canvas, Size size) {
    final rnd = math.Random(3);
    for (var i = 0; i < 28; i++) {
      final x = rnd.nextDouble() * size.width;
      final speed = 0.3 + rnd.nextDouble() * 0.7;
      final y = size.height * (1 - ((t * speed + rnd.nextDouble()) % 1));
      final r = 1.5 + rnd.nextDouble() * 2.5;
      final c = colors[i % colors.length].withValues(alpha: 0.25 + 0.35 * math.sin((t * 2 + i) * math.pi).abs());
      canvas.drawCircle(Offset(x, y), r, Paint()..color = c);
    }
  }

  @override
  bool shouldRepaint(covariant _SparklePainter old) => old.t != t;
}
