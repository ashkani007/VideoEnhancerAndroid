import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/theme.dart';
import 'data/models.dart';
import 'features/ai/ai_screen.dart';
import 'features/discover/discover_screen.dart';
import 'features/discover/profile_detail_screen.dart';
import 'features/likes/likes_screen.dart';
import 'features/matches/chat_screen.dart';
import 'features/matches/matches_screen.dart';
import 'features/onboarding/auth_screen.dart';
import 'features/onboarding/onboarding_flow.dart';
import 'features/onboarding/welcome_screen.dart';
import 'features/profile/edit_profile_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/profile/settings_screens.dart';
import 'features/profile/subscription_screen.dart';
import 'features/shell/app_shell.dart';
import 'state/providers.dart';

class _RouterRefresh extends ChangeNotifier {
  void ping() => notifyListeners();
}

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefresh();
  ref.listen(sessionProvider, (_, _) => refresh.ping());
  ref.onDispose(refresh.dispose);

  CustomTransitionPage<void> fade(Widget child, GoRouterState s) => CustomTransitionPage(
        key: s.pageKey,
        child: child,
        transitionDuration: FmMotion.medium,
        transitionsBuilder: (ctx, a, _, c) => FadeTransition(
          opacity: CurvedAnimation(parent: a, curve: FmMotion.curve),
          child: SlideTransition(
            position: Tween(begin: const Offset(0, 0.03), end: Offset.zero).animate(CurvedAnimation(parent: a, curve: FmMotion.curve)),
            child: c,
          ),
        ),
      );

  return GoRouter(
    initialLocation: '/',
    refreshListenable: refresh,
    redirect: (ctx, s) {
      final status = ref.read(sessionProvider).status;
      final loc = s.matchedLocation;
      final publicRoutes = {'/welcome', '/auth'};
      switch (status) {
        case AuthStatus.unknown:
          return loc == '/' ? null : '/';
        case AuthStatus.signedOut:
          return publicRoutes.contains(loc) ? null : '/welcome';
        case AuthStatus.needsOnboarding:
          return loc == '/onboarding' ? null : '/onboarding';
        case AuthStatus.signedIn:
          return (loc == '/' || publicRoutes.contains(loc) || loc == '/onboarding') ? '/discover' : null;
      }
    },
    routes: [
      GoRoute(path: '/', builder: (_, _) => const SplashScreen()),
      GoRoute(path: '/welcome', pageBuilder: (_, s) => fade(const WelcomeScreen(), s)),
      GoRoute(path: '/auth', pageBuilder: (_, s) => fade(AuthScreen(register: s.uri.queryParameters['mode'] != 'login'), s)),
      GoRoute(path: '/onboarding', pageBuilder: (_, s) => fade(const OnboardingFlow(), s)),
      StatefulShellRoute.indexedStack(
        builder: (ctx, s, shell) => AppShell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/discover', builder: (_, _) => const DiscoverScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/likes', builder: (_, _) => const LikesScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/matches', builder: (_, _) => const MatchesScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/ai', builder: (_, _) => const AiScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/profile', builder: (_, _) => const ProfileScreen())]),
        ],
      ),
      GoRoute(
        path: '/view',
        pageBuilder: (_, s) {
          final args = s.extra as ProfileDetailArgs;
          return fade(ProfileDetailScreen(args: args), s);
        },
      ),
      GoRoute(
        path: '/chat/:matchId',
        pageBuilder: (_, s) => fade(ChatScreen(matchId: s.pathParameters['matchId']!, match: s.extra as MatchItem?), s),
      ),
      GoRoute(path: '/subscription', pageBuilder: (_, s) => fade(const SubscriptionScreen(), s)),
      GoRoute(path: '/edit-profile', pageBuilder: (_, s) => fade(const EditProfileScreen(), s)),
      GoRoute(path: '/privacy', pageBuilder: (_, s) => fade(const PrivacyScreen(), s)),
      GoRoute(path: '/preferences', pageBuilder: (_, s) => fade(const PreferencesScreen(), s)),
      GoRoute(path: '/safety', pageBuilder: (_, s) => fade(const SafetyCenterScreen(), s)),
    ],
  );
});

class FairMatchApp extends ConsumerWidget {
  const FairMatchApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'FairMatch',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: ref.watch(themeModeProvider),
      routerConfig: ref.watch(routerProvider),
    );
  }
}

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const FairMatchLogo(size: 64),
            const SizedBox(height: FmSpace.md),
            Text('FairMatch', style: context.text.headlineMedium),
          ]),
        ),
      );
}

/// Two interlocking rings — two choices, one connection.
class FairMatchLogo extends StatelessWidget {
  const FairMatchLogo({super.key, this.size = 40});
  final double size;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Semantics(
      label: 'FairMatch logo',
      child: SizedBox(
        width: size * 1.5,
        height: size,
        child: Stack(children: [
          Positioned(left: 0, child: _Ring(size: size, color: fm.accent)),
          Positioned(right: 0, child: _Ring(size: size, color: fm.accent2)),
        ]),
      ),
    );
  }
}

class _Ring extends StatelessWidget {
  const _Ring({required this.size, required this.color});
  final double size;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: color, width: size * 0.14),
          boxShadow: [BoxShadow(color: color.withValues(alpha: 0.45), blurRadius: size * 0.4)],
        ),
      );
}
