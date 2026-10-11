import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';
import '../onboarding/choices.dart';

/// Shared helper: load my profile, edit locally, save a patch.
mixin _ProfileEditing<T extends ConsumerStatefulWidget> on ConsumerState<T> {
  MyProfile? profile;

  @override
  void initState() {
    super.initState();
    ref.read(meProvider.future).then((m) => mounted ? setState(() => profile = m.profile) : null);
  }

  Future<void> save(Map<String, dynamic> patch) async {
    try {
      final me = await ref.read(repoProvider).updateProfile(patch);
      ref.invalidate(meProvider);
      ref.invalidate(pairProvider);
      if (mounted) setState(() => profile = me.profile);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }
}

class PrivacyScreen extends ConsumerStatefulWidget {
  const PrivacyScreen({super.key});
  @override
  ConsumerState<PrivacyScreen> createState() => _PrivacyScreenState();
}

class _PrivacyScreenState extends ConsumerState<PrivacyScreen> with _ProfileEditing {
  bool _exporting = false;

  Widget _toggle(String title, String subtitle, bool value, String key) => SwitchListTile(
        title: Text(title, style: context.text.titleSmall),
        subtitle: Text(subtitle, style: context.text.bodySmall),
        value: value,
        onChanged: (v) => save({key: v}),
      );

  @override
  Widget build(BuildContext context) {
    final p = profile;
    return Scaffold(
      appBar: AppBar(title: const Text('Privacy controls')),
      body: p == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.xxl), children: [
              SectionCard(title: 'Visibility', children: [
                _toggle('Show me in Discover', 'Turn off to pause. Existing matches stay.', p.discoverable, 'discoverable'),
                _toggle('Show approximate distance', 'Others see a rounded distance like “About 10 km away”.', p.showDistance, 'show_distance'),
                _toggle('Show my gender', 'Your gender is still used for matching.', p.showGender, 'show_gender'),
              ]),
              SectionCard(title: 'Messaging', children: [
                _toggle('Read receipts', 'Reciprocal: you only see theirs if you share yours.', p.readReceipts, 'read_receipts'),
              ]),
              SectionCard(title: 'AI', children: [
                _toggle('AI processing of my data', 'Lets the AI assistant use your profile text. Never photos or messages.', p.aiConsent, 'ai_processing_consent'),
                _toggle('Allow AI insights about my profile', "If off, others' AI assistants only get rule-based info about you.", p.allowAiOnMyProfile, 'allow_ai_on_my_profile'),
              ]),
              SectionCard(title: 'Your data', children: [
                ListTile(
                  leading: Icon(Icons.download_rounded, color: context.fm.accent),
                  title: const Text('Export my data'),
                  subtitle: const Text('A machine-readable copy of your personal data'),
                  trailing: _exporting ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : null,
                  onTap: _exporting ? null : _export,
                ),
                ListTile(
                  leading: Icon(Icons.delete_forever_rounded, color: context.fm.danger),
                  title: Text('Delete my account', style: TextStyle(color: context.fm.danger)),
                  subtitle: const Text('Hidden immediately, permanently erased after 7 days'),
                  onTap: _delete,
                ),
              ]),
            ]),
    );
  }

  Future<void> _export() async {
    setState(() => _exporting = true);
    try {
      final data = await ref.read(repoProvider).exportData();
      final pretty = const JsonEncoder.withIndent('  ').convert(data);
      if (!mounted) return;
      await showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        builder: (_) => DraggableScrollableSheet(
          expand: false,
          builder: (ctx, sc) => Column(children: [
            ListTile(
              title: const Text('Your data export'),
              trailing: IconButton(
                tooltip: 'Copy',
                icon: const Icon(Icons.copy_rounded),
                onPressed: () => Clipboard.setData(ClipboardData(text: pretty)),
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                controller: sc,
                padding: const EdgeInsets.all(FmSpace.md),
                child: SelectableText(pretty, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
              ),
            ),
          ]),
        ),
      );
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete your account?'),
        content: const Text(
            'Your profile is hidden right away and your personal data is permanently erased after 7 days. Active subscriptions must be cancelled in Google Play.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: Text('Delete', style: TextStyle(color: context.fm.danger))),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(repoProvider).deleteAccount();
      await ref.read(sessionProvider.notifier).logout();
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }
}

class PreferencesScreen extends ConsumerStatefulWidget {
  const PreferencesScreen({super.key});
  @override
  ConsumerState<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends ConsumerState<PreferencesScreen> with _ProfileEditing {
  RangeValues? _ages;
  double? _distance;

  @override
  Widget build(BuildContext context) {
    final p = profile;
    if (p == null) return Scaffold(appBar: AppBar(title: const Text('Discovery preferences')), body: const Center(child: CircularProgressIndicator()));
    final ages = _ages ?? RangeValues(p.ageMin.toDouble(), p.ageMax.clamp(18, 80).toDouble());
    final dist = _distance ?? p.maxDistanceKm.toDouble().clamp(5, 200);
    final advanced = ref.watch(meProvider).value?.entitlements.advancedFilters ?? false;
    return Scaffold(
      appBar: AppBar(title: const Text('Discovery preferences')),
      body: ListView(padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.xxl), children: [
        SectionCard(title: 'Who you see', children: [
          Padding(
            padding: const EdgeInsets.all(FmSpace.md),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Age ${ages.start.round()}–${ages.end.round()}${ages.end >= 80 ? '+' : ''}', style: context.text.titleSmall),
              RangeSlider(
                values: ages,
                min: 18,
                max: 80,
                divisions: 62,
                onChanged: (v) => setState(() => _ages = v),
                onChangeEnd: (v) => save({'age_min': v.start.round(), 'age_max': v.end >= 80 ? 99 : v.end.round()}),
              ),
              const SizedBox(height: FmSpace.sm),
              Text('Within ${dist.round()} km', style: context.text.titleSmall),
              Slider(
                value: dist,
                min: 5,
                max: 200,
                divisions: 39,
                onChanged: (v) => setState(() => _distance = v),
                onChangeEnd: (v) => save({'max_distance_km': v.round()}),
              ),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.all(FmSpace.md),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Interested in', style: context.text.titleSmall),
              const SizedBox(height: FmSpace.xs),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final e in {...genders, 'everyone': 'Everyone'}.entries)
                  FilterChip(
                    label: Text(e.value),
                    selected: p.interestedIn.contains(e.key),
                    onSelected: (v) {
                      final List<String> next;
                      if (e.key == 'everyone') {
                        next = ['everyone'];
                      } else {
                        final set = {...p.interestedIn}..remove('everyone');
                        v ? set.add(e.key) : set.remove(e.key);
                        next = set.toList();
                      }
                      if (next.isNotEmpty) save({'interested_in': next});
                    },
                  ),
              ]),
            ]),
          ),
        ]),
        SectionCard(title: 'Dealbreakers${advanced ? '' : ' · Plus'}', children: [
          for (final e in dealbreakerOptions.entries)
            SwitchListTile(
              title: Text(e.value, style: context.text.titleSmall),
              value: p.dealbreakers[e.key] ?? false,
              onChanged: advanced || (p.dealbreakers[e.key] ?? false)
                  ? (v) => save({'dealbreakers': {...p.dealbreakers, e.key: v}})
                  : null,
            ),
        ]),
        Padding(
          padding: const EdgeInsets.all(FmSpace.sm),
          child: Text(
            'Preferences are reciprocal: you only see people whose preferences include you too. Narrow filters mean fewer pairs.',
            style: context.text.bodySmall,
          ),
        ),
      ]),
    );
  }
}

class SafetyCenterScreen extends StatelessWidget {
  const SafetyCenterScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    Widget tip(IconData icon, String title, String body) => ListTile(
          leading: Icon(icon, color: fm.accent),
          title: Text(title, style: context.text.titleSmall),
          subtitle: Text(body, style: context.text.bodySmall),
        );
    return Scaffold(
      appBar: AppBar(title: const Text('Safety center')),
      body: ListView(padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.xxl), children: [
        SectionCard(title: 'Tools you always have', children: [
          tip(Icons.block_rounded, 'Block anyone', 'From any profile or chat. They will never see you again.'),
          tip(Icons.flag_outlined, 'Report', 'Reports are confidential and reviewed by people, not just algorithms.'),
          tip(Icons.heart_broken_outlined, 'Unmatch', 'End a conversation at any time, no explanation needed.'),
        ]),
        SectionCard(title: 'Meeting in person', children: [
          tip(Icons.public_rounded, 'Meet in public', 'Choose a busy café or bar for first dates.'),
          tip(Icons.people_alt_outlined, 'Tell a friend', 'Share where you are going and who you are meeting.'),
          tip(Icons.payments_outlined, 'Never send money', 'Report anyone who asks for money, gift cards or crypto.'),
        ]),
        SectionCard(title: 'How we protect you', children: [
          tip(Icons.location_off_outlined, 'Approximate location only', 'We never store or share your exact position.'),
          tip(Icons.lock_outline_rounded, 'Encrypted in transit', 'Messages travel over TLS. They are not end-to-end encrypted.'),
          tip(Icons.badge_outlined, 'Adults only', 'FairMatch is strictly 18+. Report anyone who may be underage.'),
        ]),
      ]),
    );
  }
}
