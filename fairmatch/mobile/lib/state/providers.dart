import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/api_repository.dart';
import '../data/demo_repository.dart';
import '../data/models.dart';
import '../data/repository.dart';

/// Backend URL is injected at build time: --dart-define=FM_API_URL=https://api.example.com
const apiBaseUrl = String.fromEnvironment('FM_API_URL', defaultValue: 'http://10.0.2.2:8000');

enum AuthStatus { unknown, signedOut, needsOnboarding, signedIn }

class SessionState {
  const SessionState(this.status, {this.repo});
  final AuthStatus status;
  final FairMatchRepository? repo;
  bool get isDemo => repo?.isDemo ?? false;
}

/// Owns which repository is active (real API vs. clearly-labelled demo) and the auth status.
class SessionController extends Notifier<SessionState> {
  @override
  SessionState build() {
    Future.microtask(_restore);
    return const SessionState(AuthStatus.unknown);
  }

  Future<void> _restore() async {
    final api = ApiRepository(apiBaseUrl);
    try {
      if (await api.restoreSession()) {
        await _afterAuth(api);
        return;
      }
    } catch (_) {}
    state = SessionState(AuthStatus.signedOut, repo: api);
  }

  Future<void> _afterAuth(FairMatchRepository repo) async {
    final me = await repo.me();
    final done = me.profile?.completed ?? false;
    state = SessionState(done ? AuthStatus.signedIn : AuthStatus.needsOnboarding, repo: repo);
  }

  FairMatchRepository get _api => state.repo is ApiRepository ? state.repo! : ApiRepository(apiBaseUrl);

  Future<void> login(String email, String password) async {
    final repo = _api;
    await repo.login(email, password);
    await _afterAuth(repo);
  }

  Future<void> register(String email, String password, DateTime dob) async {
    final repo = _api;
    await repo.register(email: email, password: password, dateOfBirth: dob);
    state = SessionState(AuthStatus.needsOnboarding, repo: repo);
  }

  Future<void> startDemo() async {
    final demo = DemoRepository();
    await demo.login('demo', 'demo');
    state = SessionState(AuthStatus.signedIn, repo: demo);
  }

  void onboardingComplete() => state = SessionState(AuthStatus.signedIn, repo: state.repo);

  Future<void> logout() async {
    await state.repo?.logout();
    state = SessionState(AuthStatus.signedOut, repo: ApiRepository(apiBaseUrl));
  }
}

final sessionProvider = NotifierProvider<SessionController, SessionState>(SessionController.new);

final repoProvider = Provider<FairMatchRepository>((ref) {
  final repo = ref.watch(sessionProvider).repo;
  if (repo == null) throw StateError('No repository yet');
  return repo;
});

final meProvider = FutureProvider<Me>((ref) => ref.watch(repoProvider).me());

/// Discover: the current two-choice pair.
class PairController extends AsyncNotifier<PairData> {
  @override
  Future<PairData> build() => ref.watch(repoProvider).currentPair();

  Future<void> next() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => ref.read(repoProvider).currentPair());
  }
}

final pairProvider = AsyncNotifierProvider<PairController, PairData>(PairController.new);

final likesProvider = FutureProvider<LikesData>((ref) => ref.watch(repoProvider).likes());
final matchesProvider = FutureProvider<List<MatchItem>>((ref) => ref.watch(repoProvider).matches());
final productsProvider = FutureProvider<List<Product>>((ref) => ref.watch(repoProvider).products());

/// Realtime stream shared app-wide; refreshes lists when relevant events arrive.
final realtimeProvider = StreamProvider<RealtimeEvent>((ref) {
  final repo = ref.watch(repoProvider);
  final sub = repo.events.listen((e) {
    if (e is MatchEvent || e is MatchClosedEvent || e is MessageEvent) ref.invalidate(matchesProvider);
    if (e is MatchEvent || e is InterestReceivedEvent) ref.invalidate(likesProvider);
  });
  ref.onDispose(sub.cancel);
  return repo.events;
});

/// Theme preference persisted per device.
class ThemeModeController extends Notifier<ThemeMode> {
  static const _key = 'fm_theme_mode';

  @override
  ThemeMode build() {
    unawaited(_load());
    return ThemeMode.dark;
  }

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = prefs.getString(_key);
      if (v != null) state = ThemeMode.values.firstWhere((m) => m.name == v, orElse: () => ThemeMode.dark);
    } catch (_) {}
  }

  Future<void> set(ThemeMode mode) async {
    state = mode;
    try {
      (await SharedPreferences.getInstance()).setString(_key, mode.name);
    } catch (_) {}
  }
}

final themeModeProvider = NotifierProvider<ThemeModeController, ThemeMode>(ThemeModeController.new);
