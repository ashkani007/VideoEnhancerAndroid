import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../widgets/common.dart';
import '../profile/safety_sheet.dart';

class ProfileDetailArgs {
  const ProfileDetailArgs({required this.cards, this.initialIndex = 0, this.onChoose});
  final List<ProfileCard> cards;
  final int initialIndex;

  /// When set, the bottom bar lets the viewer choose directly from the full profile.
  final void Function(int index)? onChoose;
}

/// Full-screen profile. Swipe horizontally to compare the two people of a pair.
class ProfileDetailScreen extends StatefulWidget {
  const ProfileDetailScreen({super.key, required this.args});
  final ProfileDetailArgs args;

  @override
  State<ProfileDetailScreen> createState() => _ProfileDetailScreenState();
}

class _ProfileDetailScreenState extends State<ProfileDetailScreen> {
  late final PageController _pages = PageController(initialPage: widget.args.initialIndex);
  late int _index = widget.args.initialIndex;

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cards = widget.args.cards;
    final current = cards[_index];
    return Scaffold(
      body: Stack(children: [
        PageView.builder(
          controller: _pages,
          itemCount: cards.length,
          onPageChanged: (i) => setState(() => _index = i),
          itemBuilder: (_, i) => _ProfilePage(profile: cards[i]),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(FmSpace.sm),
            child: Row(children: [
              _CircleIcon(icon: Icons.arrow_back_rounded, label: 'Back', onTap: () => Navigator.pop(context)),
              const Spacer(),
              if (cards.length > 1)
                GlassPanel(
                  radius: FmRadius.pill,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  tint: Colors.black.withValues(alpha: 0.3),
                  child: Text('${_index + 1} of ${cards.length} · swipe to compare',
                      style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
                ),
              const Spacer(),
              _CircleIcon(
                icon: Icons.more_horiz_rounded,
                label: 'Safety options',
                onTap: () => showSafetySheet(context, userId: current.id, name: current.firstName),
              ),
            ]),
          ),
        ),
      ]),
      bottomNavigationBar: widget.args.onChoose == null
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.xs, FmSpace.md, FmSpace.md),
                child: FmButton(
                  label: 'Choose ${current.firstName}',
                  icon: Icons.favorite_rounded,
                  onPressed: () {
                    Navigator.pop(context);
                    widget.args.onChoose!(_index);
                  },
                ),
              ),
            ),
    );
  }
}

class _CircleIcon extends StatelessWidget {
  const _CircleIcon({required this.icon, required this.onTap, required this.label});
  final IconData icon;
  final VoidCallback onTap;
  final String label;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: label,
        child: GestureDetector(
          onTap: onTap,
          child: GlassPanel(
            radius: FmRadius.pill,
            padding: const EdgeInsets.all(10),
            tint: Colors.black.withValues(alpha: 0.3),
            child: Icon(icon, color: Colors.white, size: 22),
          ),
        ),
      );
}

class _ProfilePage extends ConsumerStatefulWidget {
  const _ProfilePage({required this.profile});
  final ProfileCard profile;

  @override
  ConsumerState<_ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<_ProfilePage> {
  final _scroll = ScrollController();
  double _offset = 0;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() => setState(() => _offset = _scroll.offset));
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.profile;
    final fm = context.fm;
    final h = MediaQuery.sizeOf(context).height * 0.62;
    final reduced = FmMotion.reduced(context);
    return CustomScrollView(controller: _scroll, slivers: [
      SliverToBoxAdapter(
        child: SizedBox(
          height: h,
          child: Stack(fit: StackFit.expand, children: [
            Hero(
              tag: 'portrait-${p.id}',
              child: Portrait(
                name: p.firstName,
                url: p.photos.firstOrNull,
                borderRadius: 0,
                parallax: reduced ? Offset.zero : Offset(0, _offset * 0.35),
              ),
            ),
            DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  stops: const [0.5, 1],
                  colors: [Colors.transparent, fm.background],
                ),
              ),
            ),
            Positioned(
              left: FmSpace.lg,
              right: FmSpace.lg,
              bottom: FmSpace.md,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (p.isDemo) const Padding(padding: EdgeInsets.only(bottom: 8), child: DemoBadge()),
                Row(children: [
                  Flexible(child: Text('${p.firstName}, ${p.age}', style: context.text.displaySmall)),
                  if (p.verified) const Padding(padding: EdgeInsets.only(left: 8), child: VerifiedBadge(size: 24)),
                ]),
                const SizedBox(height: 4),
                Text([p.distance, p.city].whereType<String>().join(' · '), style: context.text.bodyMedium?.copyWith(color: fm.textMuted)),
              ]),
            ),
          ]),
        ),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(FmSpace.lg, 0, FmSpace.lg, 120),
        sliver: SliverList.list(children: [
          if (p.intentLabel != null)
            Wrap(spacing: 8, runSpacing: 8, children: [
              Tag(p.intentLabel!, icon: intentIcon(p.intent), highlighted: true),
              if (p.gender != null) Tag(p.gender!),
            ]),
          if (p.insights != null) ...[const SizedBox(height: FmSpace.lg), InsightsCard(insights: p.insights!)],
          if (p.bio.isNotEmpty) ...[
            const SizedBox(height: FmSpace.lg),
            Text('About', style: context.text.titleLarge),
            const SizedBox(height: FmSpace.xs),
            Text(p.bio, style: context.text.bodyLarge),
          ],
          for (final pr in p.prompts) ...[
            const SizedBox(height: FmSpace.md),
            Container(
              padding: const EdgeInsets.all(FmSpace.lg),
              decoration: BoxDecoration(color: fm.surface, borderRadius: BorderRadius.circular(FmRadius.lg), border: Border.all(color: fm.stroke)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(pr.question, style: context.text.labelMedium),
                const SizedBox(height: 6),
                Text(pr.answer, style: context.text.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
              ]),
            ),
          ],
          if (p.interests.isNotEmpty) ...[
            const SizedBox(height: FmSpace.lg),
            Text('Interests', style: context.text.titleLarge),
            const SizedBox(height: FmSpace.sm),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final i in p.interests) Tag(i, highlighted: p.insights?.sharedInterests.contains(i.toLowerCase()) ?? false),
            ]),
          ],
          if (p.values.isNotEmpty) ...[
            const SizedBox(height: FmSpace.lg),
            Text('Values', style: context.text.titleLarge),
            const SizedBox(height: FmSpace.sm),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final v in p.values) Tag(v, highlighted: p.insights?.sharedValues.contains(v.toLowerCase()) ?? false),
            ]),
          ],
          if (p.lifestyle.isNotEmpty) ...[
            const SizedBox(height: FmSpace.lg),
            Text('Lifestyle', style: context.text.titleLarge),
            const SizedBox(height: FmSpace.sm),
            Wrap(spacing: 8, runSpacing: 8, children: [for (final e in p.lifestyle.entries) Tag(lifestyleLabel(e.key, e.value))]),
          ],
        ]),
      ),
    ]);
  }
}

/// Honest, qualitative compatibility notes. Never a percentage.
class InsightsCard extends StatelessWidget {
  const InsightsCard({super.key, required this.insights});
  final Insights insights;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Container(
      padding: const EdgeInsets.all(FmSpace.lg),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(FmRadius.lg),
        gradient: LinearGradient(colors: [fm.accent.withValues(alpha: 0.16), fm.accent2.withValues(alpha: 0.08)]),
        border: Border.all(color: fm.accent.withValues(alpha: 0.3)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.join_inner_rounded, color: fm.accent, size: 20),
          const SizedBox(width: 8),
          Text('What you might share', style: context.text.titleMedium),
        ]),
        const SizedBox(height: FmSpace.sm),
        if (!insights.available)
          Text(insights.explanation, style: context.text.bodyMedium?.copyWith(color: fm.textMuted))
        else ...[
          for (final h in insights.highlights)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(Icons.check_circle_rounded, size: 17, color: fm.success),
                const SizedBox(width: 8),
                Expanded(child: Text(h, style: context.text.bodyMedium)),
              ]),
            ),
          if (insights.sharedInterests.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('Both into: ${insights.sharedInterests.join(', ')}', style: context.text.bodyMedium),
            ),
          for (final c in insights.considerations)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(Icons.forum_outlined, size: 17, color: fm.warning),
                const SizedBox(width: 8),
                Expanded(child: Text('Worth talking about: $c', style: context.text.bodyMedium)),
              ]),
            ),
          const SizedBox(height: FmSpace.sm),
          Text(insights.explanation, style: context.text.bodySmall),
        ],
      ]),
    );
  }
}
