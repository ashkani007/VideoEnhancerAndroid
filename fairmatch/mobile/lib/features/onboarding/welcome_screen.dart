import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app.dart';
import '../../core/theme.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

class WelcomeScreen extends ConsumerStatefulWidget {
  const WelcomeScreen({super.key});

  @override
  ConsumerState<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends ConsumerState<WelcomeScreen> {
  final _pages = PageController();
  int _page = 0;
  bool _startingDemo = false;

  static const _slides = [
    ('Two people.\nOne honest choice.', 'No endless swiping. Each time, FairMatch shows you two people picked for real compatibility.'),
    ('Mutual, always.', "A match happens only when you both choose each other. We'll never pretend otherwise."),
    ('Fair by design.', 'Everyone eligible gets a fair chance to be seen — not just the most popular profiles.'),
  ];

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Scaffold(
      body: AmbientBackground(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(FmSpace.lg),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const FairMatchLogo(size: 26),
                const SizedBox(width: 10),
                Text('FairMatch', style: context.text.titleLarge),
              ]),
              // The hero scales down on short screens instead of overflowing.
              const Expanded(child: Center(child: FittedBox(child: _HeroPair()))),
              SizedBox(
                height: 156,
                child: PageView.builder(
                  controller: _pages,
                  itemCount: _slides.length,
                  onPageChanged: (i) => setState(() => _page = i),
                  itemBuilder: (_, i) => SingleChildScrollView(
                    physics: const NeverScrollableScrollPhysics(),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(_slides[i].$1, style: context.text.displaySmall),
                      const SizedBox(height: FmSpace.sm),
                      Text(_slides[i].$2, style: context.text.bodyLarge?.copyWith(color: fm.textMuted)),
                    ]),
                  ),
                ),
              ),
              Row(children: [
                for (var i = 0; i < _slides.length; i++)
                  AnimatedContainer(
                    duration: FmMotion.of(context, FmMotion.medium),
                    margin: const EdgeInsets.only(right: 6),
                    width: i == _page ? 22 : 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: i == _page ? fm.accent : fm.textMuted.withValues(alpha: 0.35),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
              ]),
              const SizedBox(height: FmSpace.lg),
              FmButton(label: 'Create account', onPressed: () => context.push('/auth?mode=register')),
              const SizedBox(height: FmSpace.sm),
              FmButton(label: 'I already have an account', secondary: true, onPressed: () => context.push('/auth?mode=login')),
              const SizedBox(height: FmSpace.xs),
              Center(
                child: TextButton.icon(
                  onPressed: _startingDemo
                      ? null
                      : () async {
                          setState(() => _startingDemo = true);
                          await ref.read(sessionProvider.notifier).startDemo();
                        },
                  icon: const Icon(Icons.play_circle_outline_rounded),
                  label: const Text('Explore the demo with fictional profiles'),
                ),
              ),
              Center(child: Text('FairMatch is for adults 18+.', style: context.text.bodySmall)),
            ]),
          ),
        ),
      ),
    );
  }
}

class _HeroPair extends StatelessWidget {
  const _HeroPair();

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    Widget card(String name, double angle, Offset offset) => Transform.translate(
          offset: offset,
          child: Transform.rotate(
            angle: angle,
            child: Container(
              width: 128,
              height: 184,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(FmRadius.lg),
                boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.35), blurRadius: 30, offset: const Offset(0, 14))],
              ),
              child: Portrait(name: name),
            ),
          ),
        );
    return SizedBox(
      height: 230,
      width: 300,
      child: Stack(alignment: Alignment.center, children: [
        card('Noor', -0.12, const Offset(-62, 6)),
        card('Kai', 0.12, const Offset(62, 6)),
        Container(
          width: 52,
          height: 52,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: fm.brandGradient,
            boxShadow: [BoxShadow(color: fm.accent2.withValues(alpha: 0.5), blurRadius: 24)],
          ),
          child: const Icon(Icons.favorite_rounded, color: Colors.white),
        ),
      ]),
    );
  }
}
