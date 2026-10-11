import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

class AiScreen extends ConsumerWidget {
  const AiScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(meProvider);
    return AmbientBackground(
      child: SafeArea(
        bottom: false,
        child: me.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => MessageState.error(e, onRetry: () => ref.invalidate(meProvider)),
          data: (m) => ListView(
            padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.lg, FmSpace.md, 130),
            children: [
              Row(
                children: [
                  Expanded(child: Text('AI Match', style: context.text.displaySmall)),
                  if (m.entitlements.aiAssistant) const Tag('Premium AI', icon: Icons.auto_awesome, highlighted: true),
                ],
              ),
              const SizedBox(height: 4),
              Text('Understand connections — not scores.', style: context.text.bodyMedium?.copyWith(color: context.fm.textMuted)),
              const SizedBox(height: FmSpace.lg),
              if (!m.entitlements.aiAssistant)
                const _Upsell()
              else if (!(m.profile?.aiConsent ?? false))
                const _ConsentCard()
              else ...[
                const _PeopleSection(),
                const SizedBox(height: FmSpace.lg),
                const _ReflectionCard(),
              ],
              const SizedBox(height: FmSpace.lg),
              const _HowItWorks(),
            ],
          ),
        ),
      ),
    );
  }
}

class _Upsell extends StatelessWidget {
  const _Upsell();

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Container(
      padding: const EdgeInsets.all(FmSpace.lg),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(FmRadius.xl),
        gradient: LinearGradient(
          colors: [fm.accent.withValues(alpha: 0.28), fm.accent2.withValues(alpha: 0.16)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: fm.accent.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.auto_awesome, color: fm.accent, size: 32),
          const SizedBox(height: FmSpace.sm),
          Text('A thoughtful companion for dating', style: context.text.headlineSmall),
          const SizedBox(height: FmSpace.sm),
          for (final f in const [
            'See what you might genuinely have in common',
            'Respectful notes on differences worth talking about',
            'Conversation starters drawn from both profiles',
            'Help phrasing messages kindly and clearly',
          ])
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Icon(Icons.check_rounded, size: 18, color: fm.success),
                  const SizedBox(width: 8),
                  Expanded(child: Text(f, style: context.text.bodyMedium)),
                ],
              ),
            ),
          const SizedBox(height: FmSpace.md),
          FmButton(label: 'Explore Premium AI', onPressed: () => context.push('/subscription')),
        ],
      ),
    );
  }
}

class _ConsentCard extends ConsumerStatefulWidget {
  const _ConsentCard();
  @override
  ConsumerState<_ConsentCard> createState() => _ConsentCardState();
}

class _ConsentCardState extends ConsumerState<_ConsentCard> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Container(
      padding: const EdgeInsets.all(FmSpace.lg),
      decoration: BoxDecoration(
        color: fm.surface,
        borderRadius: BorderRadius.circular(FmRadius.xl),
        border: Border.all(color: fm.stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Your data, your choice', style: context.text.headlineSmall),
          const SizedBox(height: FmSpace.sm),
          Text(
            'To give insights, FairMatch sends the text profile details you chose to share (and the other person\'s public profile, '
            'unless they opted out) to our AI provider. Photos, precise location and your private messages are never sent. '
            'You can switch this off anytime in Privacy.',
            style: context.text.bodyMedium?.copyWith(color: fm.textMuted),
          ),
          const SizedBox(height: FmSpace.lg),
          FmButton(
            label: 'Turn on AI insights',
            loading: _busy,
            onPressed: () async {
              setState(() => _busy = true);
              try {
                await ref.read(repoProvider).updateProfile({'ai_processing_consent': true});
                ref.invalidate(meProvider);
              } finally {
                if (mounted) setState(() => _busy = false);
              }
            },
          ),
        ],
      ),
    );
  }
}

class _PeopleSection extends ConsumerWidget {
  const _PeopleSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pair = ref.watch(pairProvider).value;
    final matches = ref.watch(matchesProvider).value ?? const <MatchItem>[];
    final people = <ProfileCard>[...?pair?.candidates, ...matches.map((m) => m.profile)];
    final seen = <String>{};
    final unique = people.where((p) => seen.add(p.id)).toList();
    if (unique.isEmpty) {
      return const MessageState(
        icon: Icons.people_outline_rounded,
        title: 'No one to analyse yet',
        body: 'People from your current pair and matches show up here.',
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Explore a connection', style: context.text.titleLarge),
        const SizedBox(height: FmSpace.sm),
        SizedBox(
          height: 170,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: unique.length,
            separatorBuilder: (_, _) => const SizedBox(width: FmSpace.sm),
            itemBuilder: (_, i) {
              final p = unique[i];
              return GestureDetector(
                onTap: () => showModalBottomSheet(
                  context: context,
                  isScrollControlled: true,
                  builder: (_) => _InsightSheet(profile: p),
                ),
                child: SizedBox(
                  width: 118,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Portrait(name: p.firstName, url: p.photos.firstOrNull),
                      Positioned(
                        left: 10,
                        bottom: 10,
                        right: 10,
                        child: Text(p.firstName, style: context.text.titleMedium?.copyWith(color: Colors.white)),
                      ),
                      const Positioned(top: 8, right: 8, child: Icon(Icons.auto_awesome, color: Colors.white, size: 18)),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _InsightSheet extends ConsumerWidget {
  const _InsightSheet({required this.profile});
  final ProfileCard profile;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fm = context.fm;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      maxChildSize: 0.95,
      builder: (ctx, scroll) => FutureBuilder<AiInsights>(
        future: ref.read(repoProvider).aiInsights(profile.id),
        builder: (ctx, snap) {
          if (snap.hasError) {
            return MessageState.error(snap.error!);
          }
          if (!snap.hasData) {
            return Padding(
              padding: const EdgeInsets.all(FmSpace.lg),
              child: Column(
                children: const [
                  Skeleton(height: 28),
                  SizedBox(height: 12),
                  Skeleton(height: 90),
                  SizedBox(height: 12),
                  Skeleton(height: 140),
                ],
              ),
            );
          }
          final ai = snap.data!;
          Widget section(String title, IconData icon, Color color, List<String> items) => items.isEmpty
              ? const SizedBox.shrink()
              : Padding(
                  padding: const EdgeInsets.only(top: FmSpace.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: context.text.titleMedium),
                      const SizedBox(height: FmSpace.xs),
                      for (final s in items)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(icon, size: 17, color: color),
                              const SizedBox(width: 8),
                              Expanded(child: Text(s, style: context.text.bodyMedium)),
                            ],
                          ),
                        ),
                    ],
                  ),
                );
          return ListView(
            controller: scroll,
            padding: const EdgeInsets.fromLTRB(FmSpace.lg, 0, FmSpace.lg, FmSpace.xl),
            children: [
              Row(
                children: [
                  Icon(Icons.auto_awesome, color: fm.accent),
                  const SizedBox(width: 8),
                  Text('You & ${profile.firstName}', style: context.text.headlineSmall),
                ],
              ),
              const SizedBox(height: FmSpace.sm),
              Text(ai.summary, style: context.text.bodyLarge),
              if (ai.note != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(ai.note!, style: context.text.bodySmall),
                ),
              section('Common ground', Icons.check_circle_rounded, fm.success, ai.commonGround),
              section('Worth talking about', Icons.forum_outlined, fm.warning, ai.thingsToTalkAbout),
              section('Conversation starters', Icons.chat_bubble_outline_rounded, fm.accent, ai.starters),
              const SizedBox(height: FmSpace.lg),
              Container(
                padding: const EdgeInsets.all(FmSpace.sm),
                decoration: BoxDecoration(color: fm.surfaceHigh, borderRadius: BorderRadius.circular(FmRadius.sm)),
                child: Text(ai.disclaimer, style: context.text.bodySmall),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _ReflectionCard extends ConsumerStatefulWidget {
  const _ReflectionCard();
  @override
  ConsumerState<_ReflectionCard> createState() => _ReflectionCardState();
}

class _ReflectionCardState extends ConsumerState<_ReflectionCard> {
  Future<List<String>>? _future;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Container(
      padding: const EdgeInsets.all(FmSpace.lg),
      decoration: BoxDecoration(
        color: fm.surface,
        borderRadius: BorderRadius.circular(FmRadius.xl),
        border: Border.all(color: fm.stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.self_improvement_rounded, color: fm.accent2),
              const SizedBox(width: 8),
              Text('Reflect on your preferences', style: context.text.titleLarge),
            ],
          ),
          const SizedBox(height: FmSpace.xs),
          Text('Uses only your own profile and activity.', style: context.text.bodySmall),
          const SizedBox(height: FmSpace.md),
          if (_future == null)
            FmButton(
              label: 'Show my reflection',
              secondary: true,
              onPressed: () => setState(() => _future = ref.read(repoProvider).aiReflection()),
            )
          else
            FutureBuilder<List<String>>(
              future: _future,
              builder: (ctx, snap) {
                if (snap.hasError) return Text((snap.error as ApiException?)?.message ?? 'Unavailable right now');
                if (!snap.hasData) return const LinearProgressIndicator();
                return Column(
                  children: [
                    for (final r in snap.data!)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.circle, size: 7, color: fm.accent),
                            const SizedBox(width: 10),
                            Expanded(child: Text(r, style: context.text.bodyMedium)),
                          ],
                        ),
                      ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}

class _HowItWorks extends StatelessWidget {
  const _HowItWorks();

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Container(
      padding: const EdgeInsets.all(FmSpace.md),
      decoration: BoxDecoration(color: fm.surfaceHigh.withValues(alpha: 0.6), borderRadius: BorderRadius.circular(FmRadius.lg)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.privacy_tip_outlined, size: 18, color: fm.textMuted),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'AI suggestions are not scientific predictions of relationship success. FairMatch never analyses photos for '
              'attractiveness, never infers sensitive traits, and never reads your conversations.',
              style: context.text.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}
