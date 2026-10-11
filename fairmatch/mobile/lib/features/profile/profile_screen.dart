import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(meProvider);
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: me.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => MessageState.error(e, onRetry: () => ref.invalidate(meProvider)),
          data: (m) => RefreshIndicator(
            onRefresh: () => ref.refresh(meProvider.future),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.lg, FmSpace.md, 130),
              children: [
                _Header(me: m),
                const SizedBox(height: FmSpace.md),
                _PlanCard(me: m),
                SectionCard(
                  title: 'Profile',
                  children: [
                    _Row(icon: Icons.edit_rounded, label: 'Edit profile', onTap: () => context.push('/edit-profile')),
                    _Row(icon: Icons.tune_rounded, label: 'Discovery preferences', onTap: () => context.push('/preferences')),
                    _Row(
                      icon: Icons.verified_outlined,
                      label: 'Verification',
                      trailing: Text(_verificationLabel(m.verificationStatus), style: context.text.bodySmall),
                      onTap: () => _verificationInfo(context, m),
                    ),
                  ],
                ),
                SectionCard(
                  title: 'Privacy & safety',
                  children: [
                    _Row(icon: Icons.lock_outline_rounded, label: 'Privacy controls', onTap: () => context.push('/privacy')),
                    _Row(icon: Icons.shield_outlined, label: 'Safety center', onTap: () => context.push('/safety')),
                  ],
                ),
                SectionCard(
                  title: 'App',
                  children: [
                    _ThemeRow(),
                    _Row(
                      icon: Icons.logout_rounded,
                      label: m.isDemo ? 'Leave demo' : 'Sign out',
                      onTap: () => ref.read(sessionProvider.notifier).logout(),
                    ),
                  ],
                ),
                const SizedBox(height: FmSpace.lg),
                Center(
                  child: Text('FairMatch 0.1.0${m.isDemo ? ' · Demo mode — all people are fictional' : ''}', style: context.text.bodySmall),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _verificationLabel(String s) => switch (s) {
    'verified' => 'Verified',
    'pending' => 'In review',
    'rejected' => 'Try again',
    _ => 'Not verified',
  };

  void _verificationInfo(BuildContext context, Me m) => showModalBottomSheet(
    context: context,
    builder: (_) => Padding(
      padding: const EdgeInsets.fromLTRB(FmSpace.lg, 0, FmSpace.lg, FmSpace.xl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Photo verification', style: context.text.headlineSmall),
          const SizedBox(height: FmSpace.sm),
          Text(
            m.verificationStatus == 'verified'
                ? 'Your profile shows a verified badge. Thanks for helping keep FairMatch genuine.'
                : 'Verified profiles show a blue badge. Selfie verification is reviewed by our safety team; '
                      'automated liveness checks are on our roadmap. Verification is never used to rank attractiveness.',
            style: context.text.bodyMedium,
          ),
        ],
      ),
    ),
  );
}

class _Header extends StatelessWidget {
  const _Header({required this.me});
  final Me me;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final p = me.profile;
    final completeness = p?.completeness ?? 0;
    return Row(
      children: [
        SizedBox(
          width: 96,
          height: 96,
          child: Stack(
            alignment: Alignment.center,
            children: [
              SizedBox(
                width: 96,
                height: 96,
                child: TweenAnimationBuilder<double>(
                  tween: Tween(end: completeness),
                  duration: FmMotion.of(context, FmMotion.slow),
                  builder: (_, v, _) =>
                      CircularProgressIndicator(value: v, strokeWidth: 4, color: fm.accent, backgroundColor: fm.surfaceHigh),
                ),
              ),
              SizedBox(
                width: 82,
                height: 82,
                child: ClipOval(
                  child: Portrait(name: p?.firstName ?? '?', url: p?.photos.firstOrNull?.url, borderRadius: 0),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: FmSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Flexible(child: Text('${p?.firstName ?? ''}, ${me.age}', style: context.text.headlineMedium)),
                  if (me.verificationStatus == 'verified') const Padding(padding: EdgeInsets.only(left: 6), child: VerifiedBadge(size: 22)),
                ],
              ),
              const SizedBox(height: 4),
              Text('Profile ${(completeness * 100).round()}% complete', style: context.text.bodySmall),
              if (completeness < 1) Text('More answers → more meaningful pairs', style: context.text.bodySmall?.copyWith(color: fm.accent)),
            ],
          ),
        ),
      ],
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({required this.me});
  final Me me;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final e = me.entitlements;
    return InkWell(
      borderRadius: BorderRadius.circular(FmRadius.lg),
      onTap: () => context.push('/subscription'),
      child: Container(
        padding: const EdgeInsets.all(FmSpace.md),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(FmRadius.lg),
          gradient: LinearGradient(colors: [fm.accent.withValues(alpha: 0.24), fm.accent2.withValues(alpha: 0.14)]),
          border: Border.all(color: fm.accent.withValues(alpha: 0.3)),
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(shape: BoxShape.circle, gradient: fm.brandGradient),
              child: Icon(e.aiAssistant ? Icons.auto_awesome : Icons.workspace_premium_rounded, color: Colors.white),
            ),
            const SizedBox(width: FmSpace.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('FairMatch ${e.label}', style: context.text.titleMedium),
                  Text(
                    '${me.selections.remaining} of ${me.selections.dailyLimit} selections left today'
                    '${me.boostActiveUntil != null ? ' · Boost active' : ''}',
                    style: context.text.bodySmall,
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, color: fm.textMuted),
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.icon, required this.label, this.onTap, this.trailing});
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => ListTile(
    onTap: onTap,
    leading: Icon(icon, color: context.fm.accent),
    title: Text(label, style: context.text.titleSmall),
    trailing: trailing ?? Icon(Icons.chevron_right_rounded, color: context.fm.textMuted),
  );
}

class _ThemeRow extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(themeModeProvider);
    return ListTile(
      leading: Icon(Icons.contrast_rounded, color: context.fm.accent),
      title: Text('Appearance', style: context.text.titleSmall),
      trailing: SegmentedButton<ThemeMode>(
        showSelectedIcon: false,
        style: const ButtonStyle(visualDensity: VisualDensity.compact),
        segments: const [
          ButtonSegment(value: ThemeMode.system, label: Text('Auto')),
          ButtonSegment(value: ThemeMode.dark, label: Text('Dark')),
          ButtonSegment(value: ThemeMode.light, label: Text('Light')),
        ],
        selected: {mode},
        onSelectionChanged: (s) => ref.read(themeModeProvider.notifier).set(s.first),
      ),
    );
  }
}
