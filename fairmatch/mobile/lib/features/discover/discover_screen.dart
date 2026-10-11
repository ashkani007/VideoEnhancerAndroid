import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';
import 'match_celebration.dart';
import 'profile_card.dart';
import 'profile_detail_screen.dart';

class DiscoverScreen extends ConsumerWidget {
  const DiscoverScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pair = ref.watch(pairProvider);
    final fm = context.fm;
    final sel = pair.value?.selections;
    return AmbientBackground(
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(FmSpace.md, FmSpace.lg, FmSpace.md, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Discover', style: context.text.displaySmall),
                        const SizedBox(height: 2),
                        Text('Two people, chosen with care.', style: context.text.bodyMedium?.copyWith(color: fm.textMuted)),
                      ],
                    ),
                  ),
                  if (sel != null) _SelectionsPill(sel),
                ],
              ),
              const SizedBox(height: FmSpace.md),
              Expanded(
                child: Padding(
                  // Leave room for the floating navigation bar.
                  padding: EdgeInsets.only(bottom: 84 + MediaQuery.paddingOf(context).bottom),
                  child: pair.when(
                    skipLoadingOnRefresh: false,
                    loading: () => const Padding(padding: EdgeInsets.only(bottom: 128), child: ArenaSkeleton()),
                    error: (e, _) => MessageState.error(e, onRetry: () => ref.read(pairProvider.notifier).next()),
                    data: (p) => p.isEmpty ? _EmptyPool(reason: p.emptyReason) : TwoChoiceArena(key: ValueKey(p.pairId), pair: p),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SelectionsPill extends StatelessWidget {
  const _SelectionsPill(this.s);
  final Selections s;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Tooltip(
      message: 'Positive selections left today. Choosing back someone who already chose you is always free.',
      triggerMode: TooltipTriggerMode.tap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: fm.surface,
          borderRadius: BorderRadius.circular(FmRadius.pill),
          border: Border.all(color: fm.stroke),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.favorite_rounded, size: 15, color: fm.accent2),
            const SizedBox(width: 6),
            Text('${s.remaining}/${s.dailyLimit}', style: context.text.titleSmall),
            Text(' today', style: context.text.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _EmptyPool extends ConsumerWidget {
  const _EmptyPool({this.reason});
  final String? reason;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Padding(
    padding: EdgeInsets.zero,
    child: MessageState(
      icon: Icons.nights_stay_rounded,
      title: "You're all caught up",
      body: reason ?? 'No new people match your preferences right now.',
      actionLabel: 'Check again',
      action: () => ref.read(pairProvider.notifier).next(),
    ),
  );
}

enum _Phase { idle, submitting, result }

/// The signature two-choice experience: two balanced cards, choose one, neither, or open either.
class TwoChoiceArena extends ConsumerStatefulWidget {
  const TwoChoiceArena({super.key, required this.pair});
  final PairData pair;

  @override
  ConsumerState<TwoChoiceArena> createState() => _TwoChoiceArenaState();
}

class _TwoChoiceArenaState extends ConsumerState<TwoChoiceArena> with TickerProviderStateMixin {
  late final AnimationController _choose = AnimationController(vsync: this, duration: FmMotion.slow);
  late final AnimationController _enter = AnimationController(vsync: this, duration: FmMotion.slow)..forward();
  _Phase _phase = _Phase.idle;
  int? _chosenIndex;
  SelectionOutcome? _outcome;
  String? _idempotencyKey;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (FmMotion.reduced(context)) {
      _choose.duration = Duration.zero;
      _enter.value = 1;
    }
  }

  @override
  void dispose() {
    _choose.dispose();
    _enter.dispose();
    super.dispose();
  }

  Future<void> _select(int index) async {
    if (_phase != _Phase.idle) return;
    final repo = ref.read(repoProvider);
    final cand = widget.pair.candidates[index];
    HapticFeedback.mediumImpact();
    setState(() {
      _phase = _Phase.submitting;
      _chosenIndex = index;
      _idempotencyKey ??= const Uuid().v4(); // retries reuse the same key
    });
    unawaited(_choose.forward());
    try {
      final outcome = await repo.select(widget.pair.pairId!, cand.id, _idempotencyKey!);
      if (!mounted) return;
      setState(() {
        _phase = _Phase.result;
        _outcome = outcome;
      });
      ref.invalidate(meProvider);
      ref.invalidate(likesProvider);
      if (outcome.matched) {
        HapticFeedback.heavyImpact();
        ref.invalidate(matchesProvider);
        var myName = 'You';
        try {
          myName = (await ref.read(meProvider.future)).profile?.firstName ?? myName;
        } catch (_) {}
        if (!mounted) return;
        final goChat = await showMatchCelebration(context, me: myName, other: cand);
        if (!mounted) return;
        if (goChat == true && outcome.matchId != null) {
          final matches = await ref.read(matchesProvider.future);
          final m = matches.where((x) => x.matchId == outcome.matchId).firstOrNull;
          if (mounted) context.push('/chat/${outcome.matchId}', extra: m);
        }
        _next();
      } else {
        await Future.delayed(const Duration(milliseconds: 1900));
        if (mounted) _next();
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      await _choose.reverse();
      setState(() {
        _phase = _Phase.idle;
        _chosenIndex = null;
        if (e.code != 'offline') _idempotencyKey = null;
      });
      _showError(e);
    }
  }

  void _showError(ApiException e) {
    if (e.code == 'daily_limit_reached') {
      showModalBottomSheet(context: context, builder: (_) => const _LimitSheet());
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      if (e.code == 'pair_closed' || e.code == 'unavailable') _next();
    }
  }

  Future<void> _pass() async {
    if (_phase != _Phase.idle) return;
    HapticFeedback.selectionClick();
    setState(() => _phase = _Phase.submitting);
    try {
      await ref.read(repoProvider).passPair(widget.pair.pairId!);
      _next();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _phase = _Phase.idle);
        _showError(e);
      }
    }
  }

  void _next() => ref.read(pairProvider.notifier).next();

  void _open(int index) {
    context.push(
      '/view',
      extra: ProfileDetailArgs(
        cards: widget.pair.candidates,
        initialIndex: index,
        onChoose: _phase == _Phase.idle ? (i) => _select(i) : null,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cands = widget.pair.candidates;
    final fm = context.fm;
    return LayoutBuilder(
      builder: (ctx, c) {
        const gap = FmSpace.sm;
        final wide = c.maxWidth > 700;
        final cardW = wide ? 300.0 : (c.maxWidth - gap) / 2;
        final arenaW = cands.length == 1 ? cardW : cardW * 2 + gap;
        return Column(
          children: [
            Expanded(
              child: Center(
                child: SizedBox(
                  width: arenaW,
                  child: AnimatedBuilder(
                    animation: Listenable.merge([_choose, _enter]),
                    builder: (ctx, _) {
                      final t = Curves.easeInOutCubic.transform(_choose.value);
                      final enter = Curves.easeOutCubic.transform(_enter.value);
                      return Stack(
                        clipBehavior: Clip.none,
                        children: [
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              for (var i = 0; i < cands.length; i++) ...[
                                if (i > 0) const SizedBox(width: gap),
                                SizedBox(width: cardW, child: _animatedCard(i, cands[i], t, enter, cardW + gap)),
                              ],
                            ],
                          ),
                          if (cands.length == 2 && _phase == _Phase.idle)
                            Center(
                              child: ExcludeSemantics(
                                child: Opacity(
                                  opacity: enter,
                                  child: Container(
                                    width: 34,
                                    height: 34,
                                    alignment: Alignment.center,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: fm.background,
                                      border: Border.all(color: fm.stroke),
                                    ),
                                    child: Text('or', style: context.text.labelMedium),
                                  ),
                                ),
                              ),
                            ),
                        ],
                      );
                    },
                  ),
                ),
              ),
            ),
            const SizedBox(height: FmSpace.md),
            ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 88),
              child: AnimatedSwitcher(
                duration: FmMotion.of(context, FmMotion.medium),
                child: switch (_phase) {
                  _Phase.idle => _PassBar(single: cands.length == 1, onPass: _pass),
                  _Phase.submitting => _StatusLine(
                    key: const ValueKey('sending'),
                    icon: null,
                    text: _chosenIndex == null ? 'Finding your next pair…' : 'Sending your choice…',
                  ),
                  _Phase.result => _StatusLine(
                    key: const ValueKey('result'),
                    icon: _outcome!.matched
                        ? Icons.favorite_rounded
                        : (_outcome!.state == InterestState.waitlisted ? Icons.hourglass_top_rounded : Icons.mark_email_read_rounded),
                    text: _outcome!.matched ? "It's mutual!" : '${_outcome!.statusText}\nWe\'ll let you know if it becomes a match.',
                  ),
                },
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _animatedCard(int i, ProfileCard p, double t, double enter, double shift) {
    final chosen = _chosenIndex == i;
    final other = _chosenIndex != null && !chosen;
    double dx = 0, scale = 1, opacity = 1;
    if (chosen && widget.pair.candidates.length == 2) {
      dx = (i == 0 ? 1 : -1) * shift / 2 * t;
      scale = 1 + 0.05 * t;
    } else if (other) {
      opacity = 1 - t;
      scale = 1 - 0.08 * t;
    }
    final enterDy = (1 - enter) * (i == 0 ? 40 : 70);
    return Opacity(
      opacity: (opacity * enter).clamp(0, 1),
      child: Transform.translate(
        offset: Offset(dx, enterDy),
        child: Transform.scale(
          scale: scale,
          child: ArenaCard(profile: p, enabled: _phase == _Phase.idle, onOpen: () => _open(i), onChoose: () => _select(i)),
        ),
      ),
    );
  }
}

class _PassBar extends StatelessWidget {
  const _PassBar({required this.onPass, required this.single});
  final VoidCallback onPass;
  final bool single;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Column(
      key: const ValueKey('pass'),
      children: [
        FmButton(
          label: single ? 'Not this time' : 'Neither for now',
          icon: Icons.autorenew_rounded,
          secondary: true,
          expand: false,
          dense: true,
          onPressed: onPass,
        ),
        const SizedBox(height: 8),
        Text(
          single ? 'Only one new person fits your preferences right now.' : 'Choosing is never required. Tap a card to see more.',
          style: context.text.bodySmall?.copyWith(color: fm.textMuted),
          textAlign: TextAlign.center,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }
}

class _StatusLine extends StatelessWidget {
  const _StatusLine({super.key, required this.icon, required this.text});
  final IconData? icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Semantics(
      liveRegion: true,
      child: Column(
        children: [
          SizedBox(
            height: 30,
            child: icon == null
                ? SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: fm.accent))
                : Icon(icon, color: fm.accent2, size: 28),
          ),
          const SizedBox(height: 8),
          Text(text, textAlign: TextAlign.center, style: context.text.bodyMedium),
        ],
      ),
    );
  }
}

class _LimitSheet extends StatelessWidget {
  const _LimitSheet();

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(FmSpace.lg, 0, FmSpace.lg, FmSpace.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("That's today's selections", style: context.text.headlineSmall),
            const SizedBox(height: FmSpace.xs),
            Text(
              'Daily selections keep FairMatch intentional and fair for everyone. They refresh tomorrow. '
              'You can still pass, browse profiles, chat with matches, and choose back anyone who already chose you.',
              style: context.text.bodyMedium?.copyWith(color: fm.textMuted),
            ),
            const SizedBox(height: FmSpace.lg),
            FmButton(label: 'Got it', onPressed: () => Navigator.pop(context)),
            const SizedBox(height: FmSpace.sm),
            Center(
              child: TextButton(
                onPressed: () {
                  Navigator.pop(context);
                  context.push('/subscription');
                },
                child: const Text('Plus offers 15 selections a day'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
