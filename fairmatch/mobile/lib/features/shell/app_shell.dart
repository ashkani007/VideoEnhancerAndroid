import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../state/billing.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.shell});
  final StatefulNavigationShell shell;

  static const _items = [
    (Icons.style_rounded, Icons.style_outlined, 'Discover'),
    (Icons.favorite_rounded, Icons.favorite_border_rounded, 'Likes'),
    (Icons.chat_bubble_rounded, Icons.chat_bubble_outline_rounded, 'Matches'),
    (Icons.auto_awesome, Icons.auto_awesome_outlined, 'AI Match'),
    (Icons.person_rounded, Icons.person_outline_rounded, 'Profile'),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(realtimeProvider); // keep realtime connection & list refresh alive
    ref.watch(billingProvider); // listen to Play purchase updates app-wide
    ref.listen(realtimeProvider, (_, next) {
      final e = next.value;
      if (e is MatchEvent && context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          persist: false,
          content: const Text("It's a match! Someone accepted your request 💜"),
          action: SnackBarAction(label: 'Open', onPressed: () => shell.goBranch(2)),
        ));
      }
    });
    final likes = ref.watch(likesProvider).value;
    final matches = ref.watch(matchesProvider).value;
    final badges = [
      0,
      likes?.incomingCount ?? 0,
      matches?.fold<int>(0, (a, m) => a + m.unread) ?? 0,
      0,
      0,
    ];
    final isDemo = ref.watch(sessionProvider).isDemo;
    return Scaffold(
      extendBody: true,
      body: Stack(children: [
        shell,
        if (isDemo)
          const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(child: Center(child: Padding(padding: EdgeInsets.only(top: 2), child: DemoBadge()))),
          ),
      ]),
      bottomNavigationBar: _FloatingNav(
        index: shell.currentIndex,
        badges: badges,
        onTap: (i) {
          HapticFeedback.selectionClick();
          shell.goBranch(i, initialLocation: i == shell.currentIndex);
        },
      ),
    );
  }
}

class _FloatingNav extends StatelessWidget {
  const _FloatingNav({required this.index, required this.onTap, required this.badges});
  final int index;
  final ValueChanged<int> onTap;
  final List<int> badges;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final bottom = MediaQuery.paddingOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, bottom > 0 ? bottom : FmSpace.md),
      child: GlassPanel(
        radius: FmRadius.xl,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
        tint: fm.surface.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? 0.78 : 0.9),
        child: Row(
          children: [
            for (var i = 0; i < AppShell._items.length; i++)
              Expanded(child: _NavItem(item: AppShell._items[i], selected: i == index, badge: badges[i], onTap: () => onTap(i))),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({required this.item, required this.selected, required this.onTap, required this.badge});
  final (IconData, IconData, String) item;
  final bool selected;
  final VoidCallback onTap;
  final int badge;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final d = FmMotion.of(context, FmMotion.medium);
    return Semantics(
      selected: selected,
      button: true,
      label: badge > 0 ? '${item.$3}, $badge new' : item.$3,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(FmRadius.lg),
        child: AnimatedContainer(
          duration: d,
          curve: FmMotion.curve,
          height: 56,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(FmRadius.lg),
            gradient: selected
                ? LinearGradient(colors: [fm.accent.withValues(alpha: 0.22), fm.accent2.withValues(alpha: 0.14)])
                : null,
          ),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Stack(clipBehavior: Clip.none, children: [
              AnimatedScale(
                scale: selected ? 1.1 : 1,
                duration: d,
                curve: FmMotion.spring,
                child: Icon(selected ? item.$1 : item.$2, size: 23, color: selected ? fm.accent : fm.textMuted),
              ),
              if (badge > 0)
                Positioned(
                  right: -8,
                  top: -4,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: BoxDecoration(color: fm.accent2, borderRadius: BorderRadius.circular(10)),
                    child: Text('$badge', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w800)),
                  ),
                ),
            ]),
            const SizedBox(height: 3),
            Text(
              item.$3,
              maxLines: 1,
              overflow: TextOverflow.fade,
              style: TextStyle(fontSize: 10.5, fontWeight: selected ? FontWeight.w700 : FontWeight.w500, color: selected ? fm.text : fm.textMuted),
            ),
          ]),
        ),
      ),
    );
  }
}
