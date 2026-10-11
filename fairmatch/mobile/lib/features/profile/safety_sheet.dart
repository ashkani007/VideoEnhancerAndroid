import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

const reportReasons = {
  'fake_profile': 'Fake profile or impersonation',
  'harassment': 'Harassment or hateful behaviour',
  'inappropriate': 'Inappropriate photos or content',
  'scam': 'Scam or asking for money',
  'spam': 'Spam or advertising',
  'underage': 'May be under 18',
  'other': 'Something else',
};

/// Report / block entry point available on every profile and conversation.
Future<bool?> showSafetySheet(BuildContext context, {required String userId, required String name, String? matchId}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _SafetySheet(userId: userId, name: name, matchId: matchId),
  );
}

class _SafetySheet extends ConsumerStatefulWidget {
  const _SafetySheet({required this.userId, required this.name, this.matchId});
  final String userId, name;
  final String? matchId;

  @override
  ConsumerState<_SafetySheet> createState() => _SafetySheetState();
}

class _SafetySheetState extends ConsumerState<_SafetySheet> {
  String? _reason;
  final _details = TextEditingController();
  bool _busy = false, _reporting = false;

  @override
  void dispose() {
    _details.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action, String done) async {
    setState(() => _busy = true);
    try {
      await action();
      ref.invalidate(matchesProvider);
      ref.invalidate(pairProvider);
      ref.invalidate(likesProvider);
      if (!mounted) return;
      Navigator.pop(context, true);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(done)));
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final repo = ref.read(repoProvider);
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(FmSpace.lg, 0, FmSpace.lg, FmSpace.lg + MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_reporting ? 'Report ${widget.name}' : 'Safety', style: context.text.headlineSmall),
              const SizedBox(height: 4),
              Text(
                _reporting
                    ? "Reports are confidential — ${widget.name} won't know who reported them."
                    : 'You are always in control of who can reach you.',
                style: context.text.bodyMedium?.copyWith(color: fm.textMuted),
              ),
              const SizedBox(height: FmSpace.md),
              if (!_reporting) ...[
                if (widget.matchId != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.heart_broken_outlined),
                    title: const Text('Unmatch'),
                    subtitle: const Text('End the conversation quietly'),
                    onTap: _busy ? null : () => _run(() => repo.unmatch(widget.matchId!), 'Unmatched'),
                  ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.block_rounded),
                  title: Text('Block ${widget.name}'),
                  subtitle: const Text("They won't be able to see or contact you"),
                  onTap: _busy ? null : () => _run(() => repo.block(widget.userId), '${widget.name} is blocked'),
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.flag_outlined, color: fm.danger),
                  title: Text('Report ${widget.name}', style: TextStyle(color: fm.danger)),
                  subtitle: const Text('Tell our safety team what happened'),
                  onTap: () => setState(() => _reporting = true),
                ),
              ] else ...[
                RadioGroup<String>(
                  groupValue: _reason,
                  onChanged: (v) => setState(() => _reason = v),
                  child: Column(
                    children: [
                      for (final e in reportReasons.entries)
                        RadioListTile<String>(contentPadding: EdgeInsets.zero, value: e.key, title: Text(e.value)),
                    ],
                  ),
                ),
                const SizedBox(height: FmSpace.xs),
                TextField(
                  controller: _details,
                  maxLines: 3,
                  maxLength: 2000,
                  decoration: const InputDecoration(hintText: 'Anything else we should know? (optional)'),
                ),
                const SizedBox(height: FmSpace.sm),
                FmButton(
                  label: 'Report and block',
                  loading: _busy,
                  onPressed: _reason == null
                      ? null
                      : () => _run(() => repo.report(widget.userId, _reason!, _details.text), 'Thanks — our team will review this.'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
