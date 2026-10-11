import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

class MatchesScreen extends ConsumerWidget {
  const MatchesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final matches = ref.watch(matchesProvider);
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () => ref.refresh(matchesProvider.future),
          child: CustomScrollView(slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.lg, FmSpace.md, FmSpace.sm),
              sliver: SliverToBoxAdapter(child: Text('Matches', style: context.text.displaySmall)),
            ),
            ...matches.when(
              loading: () => [
                SliverList.list(children: [
                  for (var i = 0; i < 5; i++)
                    const Padding(padding: EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.sm), child: Skeleton(height: 72)),
                ]),
              ],
              error: (e, _) => [SliverFillRemaining(child: MessageState.error(e, onRetry: () => ref.invalidate(matchesProvider)))],
              data: (list) {
                if (list.isEmpty) {
                  return [
                    const SliverFillRemaining(
                      hasScrollBody: false,
                      child: MessageState(
                        icon: Icons.forum_outlined,
                        title: 'No matches yet',
                        body: 'Matches appear here when you and someone choose each other. Good things take a little time.',
                      ),
                    ),
                  ];
                }
                final fresh = list.where((m) => m.lastMessage == null).toList();
                final convos = list.where((m) => m.lastMessage != null).toList();
                return [
                  if (fresh.isNotEmpty) ...[
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.sm, FmSpace.md, FmSpace.sm),
                        child: Text('NEW MATCHES', style: context.text.labelSmall),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: SizedBox(
                        height: 116,
                        child: ListView.separated(
                          scrollDirection: Axis.horizontal,
                          padding: const EdgeInsets.symmetric(horizontal: FmSpace.md),
                          itemCount: fresh.length,
                          separatorBuilder: (_, _) => const SizedBox(width: FmSpace.sm),
                          itemBuilder: (_, i) => _NewMatch(m: fresh[i]),
                        ),
                      ),
                    ),
                  ],
                  if (convos.isNotEmpty)
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.md, FmSpace.md, FmSpace.xs),
                        child: Text('CONVERSATIONS', style: context.text.labelSmall),
                      ),
                    ),
                  SliverList.list(children: [for (final m in convos) _ConversationTile(m: m)]),
                ];
              },
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 120)),
          ]),
        ),
      ),
    );
  }
}

class _NewMatch extends StatelessWidget {
  const _NewMatch({required this.m});
  final MatchItem m;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return GestureDetector(
      onTap: () => context.push('/chat/${m.matchId}', extra: m),
      child: Semantics(
        button: true,
        label: 'New match with ${m.profile.firstName}. Start chatting.',
        child: Column(children: [
          Container(
            width: 78,
            height: 78,
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(shape: BoxShape.circle, gradient: fm.brandGradient),
            child: ClipOval(child: Portrait(name: m.profile.firstName, url: m.profile.photos.firstOrNull, borderRadius: 0)),
          ),
          const SizedBox(height: 6),
          Text(m.profile.firstName, style: context.text.titleSmall),
        ]),
      ),
    );
  }
}

class _ConversationTile extends StatelessWidget {
  const _ConversationTile({required this.m});
  final MatchItem m;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final last = m.lastMessage!;
    final mine = last.status != DeliveryStatus.received;
    return InkWell(
      onTap: () => context.push('/chat/${m.matchId}', extra: m),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: FmSpace.md, vertical: FmSpace.sm),
        child: Row(children: [
          SizedBox(width: 58, height: 58, child: ClipOval(child: Portrait(name: m.profile.firstName, url: m.profile.photos.firstOrNull, borderRadius: 0))),
          const SizedBox(width: FmSpace.sm),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(m.profile.firstName, style: context.text.titleMedium)),
                Text(_time(last.createdAt), style: context.text.bodySmall),
              ]),
              const SizedBox(height: 3),
              Row(children: [
                if (mine) Padding(padding: const EdgeInsets.only(right: 4), child: Text('You:', style: context.text.bodySmall)),
                Expanded(
                  child: Text(
                    last.body,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: context.text.bodyMedium?.copyWith(
                      color: m.unread > 0 ? fm.text : fm.textMuted,
                      fontWeight: m.unread > 0 ? FontWeight.w600 : FontWeight.w400,
                    ),
                  ),
                ),
                if (m.unread > 0)
                  Container(
                    margin: const EdgeInsets.only(left: 6),
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(color: fm.accent2, borderRadius: BorderRadius.circular(10)),
                    child: Text('${m.unread}', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
                  ),
              ]),
            ]),
          ),
        ]),
      ),
    );
  }

  String _time(DateTime t) {
    final now = DateTime.now();
    if (now.difference(t).inDays == 0 && now.day == t.day) return DateFormat.Hm().format(t);
    if (now.difference(t).inDays < 7) return DateFormat.E().format(t);
    return DateFormat.MMMd().format(t);
  }
}
