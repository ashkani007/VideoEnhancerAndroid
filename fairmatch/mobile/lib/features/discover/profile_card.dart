import 'package:flutter/material.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';

/// A tall portrait card used in the Two-Choice Arena. Tilts subtly under the finger
/// (parallax) and exposes a dedicated, clearly labelled "Choose" action.
class ArenaCard extends StatefulWidget {
  const ArenaCard({super.key, required this.profile, required this.onOpen, required this.onChoose, this.enabled = true});
  final ProfileCard profile;
  final VoidCallback onOpen, onChoose;
  final bool enabled;

  @override
  State<ArenaCard> createState() => _ArenaCardState();
}

class _ArenaCardState extends State<ArenaCard> {
  Offset _tilt = Offset.zero; // -1..1

  void _move(Offset local, Size size) {
    if (FmMotion.reduced(context)) return;
    setState(() => _tilt = Offset(
          clampDouble(local.dx / size.width * 2 - 1, -1, 1),
          clampDouble(local.dy / size.height * 2 - 1, -1, 1),
        ));
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.profile;
    final fm = context.fm;
    final shared = (p.insights?.sharedInterests.length ?? 0) + (p.insights?.sharedValues.length ?? 0);
    return LayoutBuilder(builder: (ctx, c) {
      final size = Size(c.maxWidth, c.maxHeight);
      return Listener(
        onPointerMove: (e) => _move(e.localPosition, size),
        onPointerUp: (_) => setState(() => _tilt = Offset.zero),
        onPointerCancel: (_) => setState(() => _tilt = Offset.zero),
        child: TweenAnimationBuilder<Offset>(
          tween: Tween(end: _tilt),
          duration: FmMotion.of(context, FmMotion.medium),
          curve: FmMotion.curve,
          builder: (ctx, t, child) => Transform(
            alignment: Alignment.center,
            transform: Matrix4.identity()
              ..setEntry(3, 2, 0.0012)
              ..rotateX(-t.dy * 0.05)
              ..rotateY(t.dx * 0.06),
            child: _body(context, p, fm, shared, t, compact: size.height < 420),
          ),
        ),
      );
    });
  }

  Widget _body(BuildContext context, ProfileCard p, FmColors fm, int shared, Offset t, {required bool compact}) {
    return Semantics(
      container: true,
      label: '${p.firstName}, ${p.age}. ${p.intentLabel ?? ''}. ${p.distance ?? ''}. Double tap to open profile.',
      child: GestureDetector(
        onTap: widget.onOpen,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(FmRadius.xl),
            boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.35), blurRadius: 30, offset: const Offset(0, 16))],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(FmRadius.xl),
            child: Stack(fit: StackFit.expand, children: [
              Hero(
                tag: 'portrait-${p.id}',
                child: Portrait(name: p.firstName, url: p.photos.isEmpty ? null : p.photos.first, borderRadius: 0, parallax: Offset(-t.dx * 10, -t.dy * 10)),
              ),
              const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    stops: [0, 0.38, 0.62, 1],
                    colors: [Color(0x33000000), Color(0x00000000), Color(0x66000000), Color(0xE6000000)],
                  ),
                ),
              ),
              Positioned(
                top: 12,
                left: 12,
                right: 12,
                child: Row(children: [
                  if (p.isDemo) const DemoBadge(compact: true),
                  const Spacer(),
                  if (p.promoted) const Tag('Promoted', onDark: true),
                ]),
              ),
              Positioned(
                left: 14,
                right: 14,
                bottom: 14,
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Flexible(
                      child: Text(
                        '${p.firstName}, ${p.age}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: context.text.headlineSmall?.copyWith(color: Colors.white, fontSize: 21),
                      ),
                    ),
                    if (p.verified) const Padding(padding: EdgeInsets.only(left: 5), child: VerifiedBadge(size: 17)),
                  ]),
                  const SizedBox(height: 4),
                  if (p.intentLabel != null)
                    Row(children: [
                      Icon(intentIcon(p.intent), size: 13, color: Colors.white70),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text(shortIntent(p.intent) ?? p.intentLabel!, maxLines: 1, overflow: TextOverflow.ellipsis,
                            style: const TextStyle(color: Colors.white, fontSize: 12.5, fontWeight: FontWeight.w600)),
                      ),
                    ]),
                  if (p.distance != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(p.distance!, style: const TextStyle(color: Colors.white70, fontSize: 12)),
                    ),
                  // On short screens keep only the essentials so photos stay large.
                  if (!compact) ...[
                    const SizedBox(height: 8),
                    Wrap(spacing: 5, runSpacing: 5, children: [
                      for (final i in p.interests.take(2)) Tag(i, onDark: true),
                    ]),
                  ],
                  if (shared > 0) ...[
                    const SizedBox(height: 8),
                    Row(children: [
                      Icon(Icons.join_inner_rounded, size: 14, color: fm.accent2),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text('$shared in common',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
                      ),
                    ]),
                  ],
                  SizedBox(height: compact ? 8 : 12),
                  _ChooseButton(name: p.firstName, enabled: widget.enabled, onTap: widget.onChoose),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _ChooseButton extends StatelessWidget {
  const _ChooseButton({required this.name, required this.onTap, required this.enabled});
  final String name;
  final VoidCallback onTap;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Semantics(
      button: true,
      label: 'Choose $name',
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        child: AnimatedOpacity(
          opacity: enabled ? 1 : 0.5,
          duration: FmMotion.fast,
          child: Container(
            height: 44,
            decoration: BoxDecoration(
              gradient: fm.brandGradient,
              borderRadius: BorderRadius.circular(FmRadius.pill),
              boxShadow: [BoxShadow(color: fm.accent2.withValues(alpha: 0.4), blurRadius: 16, offset: const Offset(0, 6))],
            ),
            child: const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.favorite_rounded, color: Colors.white, size: 18),
              SizedBox(width: 6),
              Text('Choose', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14.5)),
            ]),
          ),
        ),
      ),
    );
  }
}

class ArenaSkeleton extends StatelessWidget {
  const ArenaSkeleton({super.key});

  @override
  Widget build(BuildContext context) => Row(children: const [
        Expanded(child: Skeleton(radius: FmRadius.xl)),
        SizedBox(width: FmSpace.sm),
        Expanded(child: Skeleton(radius: FmRadius.xl)),
      ]);
}
