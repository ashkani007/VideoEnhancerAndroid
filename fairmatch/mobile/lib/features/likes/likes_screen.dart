import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';
import '../discover/match_celebration.dart';
import '../discover/profile_detail_screen.dart';

class LikesScreen extends ConsumerStatefulWidget {
  const LikesScreen({super.key});

  @override
  ConsumerState<LikesScreen> createState() => _LikesScreenState();
}

class _LikesScreenState extends ConsumerState<LikesScreen> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final likes = ref.watch(likesProvider);
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () => ref.refresh(likesProvider.future),
          child: CustomScrollView(slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.lg, FmSpace.md, FmSpace.md),
              sliver: SliverToBoxAdapter(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Likes', style: context.text.displaySmall),
                  const SizedBox(height: FmSpace.md),
                  _Segmented(
                    index: _tab,
                    labels: ['Chose you${likes.value != null ? ' · ${likes.value!.incomingCount}' : ''}', 'Your requests'],
                    onChanged: (i) => setState(() => _tab = i),
                  ),
                ]),
              ),
            ),
            ...likes.when(
              loading: () => [
                SliverList.list(children: [
                  for (var i = 0; i < 4; i++)
                    const Padding(padding: EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.sm), child: Skeleton(height: 84)),
                ]),
              ],
              error: (e, _) => [SliverFillRemaining(child: MessageState.error(e, onRetry: () => ref.invalidate(likesProvider)))],
              data: (d) => _tab == 0 ? _incoming(d) : _outgoing(d),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 120)),
          ]),
        ),
      ),
    );
  }

  List<Widget> _incoming(LikesData d) {
    if (d.incomingCount == 0) {
      return [
        const SliverFillRemaining(
          hasScrollBody: false,
          child: MessageState(
            icon: Icons.favorite_border_rounded,
            title: 'No new requests yet',
            body: 'When someone chooses you, it appears here. Keep your profile fresh — more answers mean better pairs.',
          ),
        ),
      ];
    }
    if (!d.canSeeIncoming) {
      return [SliverToBoxAdapter(child: _LockedIncoming(count: d.incomingCount, note: d.note))];
    }
    return [
      SliverList.list(children: [
        for (final it in d.incoming) _IncomingTile(item: it),
      ]),
    ];
  }

  List<Widget> _outgoing(LikesData d) {
    if (d.outgoing.isEmpty) {
      return [
        const SliverFillRemaining(
          hasScrollBody: false,
          child: MessageState(
            icon: Icons.send_rounded,
            title: 'No requests sent',
            body: 'People you choose in Discover appear here with their real status.',
          ),
        ),
      ];
    }
    return [
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.sm),
          child: Text(
            "Each person can only have a couple of open requests at a time, so some requests wait in line until they have room. "
            "We'll always tell you exactly where yours stands.",
            style: context.text.bodySmall,
          ),
        ),
      ),
      SliverList.list(children: [for (final it in d.outgoing) _OutgoingTile(item: it)]),
    ];
  }
}

class _Segmented extends StatelessWidget {
  const _Segmented({required this.index, required this.labels, required this.onChanged});
  final int index;
  final List<String> labels;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: fm.surface, borderRadius: BorderRadius.circular(FmRadius.pill), border: Border.all(color: fm.stroke)),
      child: Row(children: [
        for (var i = 0; i < labels.length; i++)
          Expanded(
            child: Semantics(
              selected: i == index,
              button: true,
              child: GestureDetector(
                onTap: () => onChanged(i),
                child: AnimatedContainer(
                  duration: FmMotion.of(context, FmMotion.fast),
                  padding: const EdgeInsets.symmetric(vertical: 11),
                  decoration: BoxDecoration(
                    gradient: i == index ? fm.brandGradient : null,
                    borderRadius: BorderRadius.circular(FmRadius.pill),
                  ),
                  alignment: Alignment.center,
                  child: Text(labels[i], style: context.text.labelLarge?.copyWith(color: i == index ? Colors.white : fm.textMuted, fontSize: 13.5)),
                ),
              ),
            ),
          ),
      ]),
    );
  }
}

class _LockedIncoming extends StatelessWidget {
  const _LockedIncoming({required this.count, this.note});
  final int count;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: FmSpace.md),
      child: Column(children: [
        SizedBox(
          height: 170,
          child: Row(children: [
            for (var i = 0; i < count.clamp(1, 3); i++)
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Stack(fit: StackFit.expand, children: [
                    ImageFiltered(
                      imageFilter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
                      child: Portrait(name: 'xyz$i'),
                    ),
                    Center(child: Icon(Icons.lock_rounded, color: Colors.white.withValues(alpha: 0.85))),
                  ]),
                ),
              ),
          ]),
        ),
        const SizedBox(height: FmSpace.lg),
        Text('$count ${count == 1 ? 'person has' : 'people have'} chosen you', style: context.text.headlineSmall, textAlign: TextAlign.center),
        const SizedBox(height: FmSpace.xs),
        Text(note ?? '', style: context.text.bodyMedium?.copyWith(color: fm.textMuted), textAlign: TextAlign.center),
        const SizedBox(height: FmSpace.lg),
        FmButton(label: 'Go to Discover', onPressed: () => context.go('/discover')),
        const SizedBox(height: FmSpace.xs),
        TextButton(onPressed: () => context.push('/subscription'), child: const Text('See them here with Plus')),
      ]),
    );
  }
}

class _IncomingTile extends ConsumerStatefulWidget {
  const _IncomingTile({required this.item});
  final InterestItem item;

  @override
  ConsumerState<_IncomingTile> createState() => _IncomingTileState();
}

class _IncomingTileState extends ConsumerState<_IncomingTile> {
  bool _busy = false;

  Future<void> _respond(bool accept) async {
    setState(() => _busy = true);
    try {
      final out = await ref.read(repoProvider).respond(widget.item.id, accept);
      ref.invalidate(likesProvider);
      ref.invalidate(pairProvider);
      if (out.matched && mounted) {
        ref.invalidate(matchesProvider);
        final go = await showMatchCelebration(context, me: 'You', other: widget.item.profile!);
        if (go == true && mounted && out.matchId != null) context.push('/chat/${out.matchId}');
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.item.profile;
    final fm = context.fm;
    if (p == null) return const SizedBox.shrink();
    final hoursLeft = widget.item.expiresAt?.difference(DateTime.now()).inHours;
    return Padding(
      padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.sm),
      child: Container(
        padding: const EdgeInsets.all(FmSpace.sm),
        decoration: BoxDecoration(color: fm.surface, borderRadius: BorderRadius.circular(FmRadius.lg), border: Border.all(color: fm.stroke)),
        child: Row(children: [
          GestureDetector(
            onTap: () => context.push('/view', extra: ProfileDetailArgs(cards: [p])),
            child: SizedBox(width: 64, height: 80, child: Portrait(name: p.firstName, url: p.photos.firstOrNull, borderRadius: FmRadius.sm)),
          ),
          const SizedBox(width: FmSpace.sm),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${p.firstName}, ${p.age}', style: context.text.titleMedium),
              Text(profileSubtitle(p), style: context.text.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
              if (hoursLeft != null) Text('Answer within ${hoursLeft}h', style: context.text.bodySmall?.copyWith(color: fm.warning)),
            ]),
          ),
          IconButton(
            tooltip: 'Not for me',
            onPressed: _busy ? null : () => _respond(false),
            icon: Icon(Icons.close_rounded, color: fm.textMuted),
          ),
          IconButton.filled(
            tooltip: 'Choose ${p.firstName} back',
            onPressed: _busy ? null : () => _respond(true),
            style: IconButton.styleFrom(backgroundColor: fm.accent2),
            icon: const Icon(Icons.favorite_rounded, color: Colors.white),
          ),
        ]),
      ),
    );
  }
}

class _OutgoingTile extends ConsumerWidget {
  const _OutgoingTile({required this.item});
  final InterestItem item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fm = context.fm;
    final p = item.profile;
    final (color, icon) = switch (item.state) {
      InterestState.pending => (fm.accent, Icons.mark_email_read_rounded),
      InterestState.waitlisted => (fm.warning, Icons.hourglass_top_rounded),
      InterestState.matched => (fm.success, Icons.favorite_rounded),
      _ => (fm.textMuted, Icons.history_rounded),
    };
    final cancelable = item.state == InterestState.pending || item.state == InterestState.waitlisted;
    return Padding(
      padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.sm),
      child: Container(
        padding: const EdgeInsets.all(FmSpace.sm),
        decoration: BoxDecoration(color: fm.surface, borderRadius: BorderRadius.circular(FmRadius.lg), border: Border.all(color: fm.stroke)),
        child: Row(children: [
          SizedBox(width: 52, height: 52, child: ClipOval(child: Portrait(name: p?.firstName ?? '?', url: p?.photos.firstOrNull, borderRadius: 0))),
          const SizedBox(width: FmSpace.sm),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(p?.firstName ?? 'Someone', style: context.text.titleMedium),
              const SizedBox(height: 2),
              Row(children: [
                Icon(icon, size: 14, color: color),
                const SizedBox(width: 5),
                Expanded(child: Text(item.statusText, style: context.text.bodySmall?.copyWith(color: color), maxLines: 2)),
              ]),
            ]),
          ),
          if (cancelable)
            TextButton(
              onPressed: () async {
                try {
                  await ref.read(repoProvider).cancelInterest(item.id);
                  ref.invalidate(likesProvider);
                } on ApiException catch (e) {
                  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
                }
              },
              child: const Text('Withdraw'),
            ),
        ]),
      ),
    );
  }
}
