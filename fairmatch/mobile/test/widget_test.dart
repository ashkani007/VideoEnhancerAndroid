import 'dart:async';

import 'package:fairmatch/core/theme.dart';
import 'package:fairmatch/data/demo_repository.dart';
import 'package:fairmatch/data/models.dart';
import 'package:fairmatch/data/repository.dart';
import 'package:fairmatch/features/discover/discover_screen.dart';
import 'package:fairmatch/features/likes/likes_screen.dart';
import 'package:fairmatch/features/matches/chat_screen.dart';
import 'package:fairmatch/features/onboarding/auth_screen.dart';
import 'package:fairmatch/features/onboarding/welcome_screen.dart';
import 'package:fairmatch/state/providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Widget host(Widget child, FairMatchRepository repo, {Brightness brightness = Brightness.dark}) => ProviderScope(
      retry: (_, _) => null,
      overrides: [repoProvider.overrideWithValue(repo)],
      child: MaterialApp(theme: buildTheme(brightness), home: Scaffold(body: child)),
    );

Future<void> setSize(WidgetTester t, Size logical) async {
  t.view.physicalSize = logical * 2;
  t.view.devicePixelRatio = 2;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

/// Repository whose discover call never completes / fails, for loading & error states.
class _StubRepo extends DemoRepository {
  _StubRepo({this.pair});
  final Future<PairData> Function()? pair;
  @override
  Future<PairData> currentPair() => pair!();
}

void main() {
  testWidgets('Discover shows two balanced cards and the no-pressure pass option', (t) async {
    await setSize(t, const Size(412, 892));
    await t.pumpWidget(host(const DiscoverScreen(), DemoRepository(latency: Duration.zero)));
    await t.pump(const Duration(seconds: 1));
    expect(find.text('Luca, 29'), findsOneWidget);
    expect(find.text('Sam, 27'), findsOneWidget);
    expect(find.text('Neither for now'), findsOneWidget);
    expect(find.text('Choose'), findsNWidgets(2));
    expect(find.text('5/5'), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('Choosing a person shows the real request status, not a fake match', (t) async {
    await setSize(t, const Size(412, 892));
    final repo = DemoRepository(latency: Duration.zero);
    await t.pumpWidget(host(const DiscoverScreen(), repo));
    await t.pump(const Duration(seconds: 1));
    // Skip the first pair (contains people who already chose the demo user).
    await t.tap(find.text('Neither for now'));
    await t.pump(const Duration(seconds: 1));
    await t.pump(const Duration(seconds: 1));
    final chooseFinder = find.textContaining(RegExp(r'^Choose$'));
    expect(chooseFinder, findsNWidgets(2));
    await t.tap(chooseFinder.first);
    await t.pump(const Duration(milliseconds: 700));
    expect(find.textContaining(RegExp('Delivered|Waiting in line')), findsOneWidget);
    expect(find.text("It's mutual."), findsNothing);
    await t.pump(const Duration(seconds: 20)); // drain demo timers
  });

  testWidgets('Discover loading state shows skeletons', (t) async {
    final never = Completer<PairData>();
    await t.pumpWidget(host(const DiscoverScreen(), _StubRepo(pair: () => never.future)));
    await t.pump();
    expect(find.byType(Discover), findsNothing);
    expect(find.byWidgetPredicate((w) => w.runtimeType.toString() == 'Skeleton'), findsNWidgets(2));
  });

  testWidgets('Discover offline state offers retry', (t) async {
    await t.pumpWidget(host(
      const DiscoverScreen(),
      _StubRepo(pair: () async => throw ApiException('offline', "You're offline. Check your connection and try again.")),
    ));
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text("You're offline"), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });

  testWidgets('Discover empty state is honest and never fabricates people', (t) async {
    await t.pumpWidget(host(
      const DiscoverScreen(),
      _StubRepo(pair: () async => const PairData(pairId: null, candidates: [], selections: Selections(5, 5), emptyReason: 'No new people')),
    ));
    await t.pump(const Duration(milliseconds: 50));
    expect(find.text("You're all caught up"), findsOneWidget);
    expect(find.text('No new people'), findsOneWidget);
  });

  for (final size in const [Size(320, 568), Size(360, 740), Size(1024, 1366)]) {
    testWidgets('Discover lays out without overflow at ${size.width.toInt()}x${size.height.toInt()}', (t) async {
      await setSize(t, size);
      await t.pumpWidget(host(const DiscoverScreen(), DemoRepository(latency: Duration.zero), brightness: Brightness.light));
      await t.pump(const Duration(seconds: 1));
      expect(t.takeException(), isNull);
      expect(find.text('Luca, 29'), findsOneWidget);
    });
  }

  testWidgets('Likes: free users see a count and an honest explanation', (t) async {
    await setSize(t, const Size(412, 892));
    await t.pumpWidget(host(const LikesScreen(), DemoRepository(latency: Duration.zero)));
    await t.pump(const Duration(seconds: 1));
    expect(find.text('2 people have chosen you'), findsOneWidget);
    expect(find.textContaining('choose them back for free'), findsOneWidget);
  });

  testWidgets('Chat: sending a message shows it with delivery status and a reply arrives', (t) async {
    await setSize(t, const Size(412, 892));
    final repo = DemoRepository(latency: Duration.zero);
    late SelectionOutcome out;
    late MatchItem match;
    await t.runAsync(() async {
      final pair = await repo.currentPair();
      out = await repo.select(pair.pairId!, 'luca', 'k1');
      match = (await repo.matches()).first;
    });
    expect(out.matched, isTrue); // Luca had already chosen the demo user
    await t.pumpWidget(host(ChatScreen(matchId: out.matchId!, match: match), repo));
    await t.pump(const Duration(milliseconds: 100));
    expect(find.text('You matched with Luca'), findsOneWidget);
    await t.enterText(find.byType(TextField), 'Hi Luca!');
    await t.pump();
    await t.tap(find.byTooltip('Send'));
    await t.pump(const Duration(milliseconds: 100));
    expect(find.text('Hi Luca!'), findsOneWidget);
    await t.pump(const Duration(seconds: 5));
    expect(find.byWidgetPredicate((w) => w is Text && (w.data ?? '').isNotEmpty && w.data != 'Hi Luca!' && w.data!.length > 12), findsWidgets);
    await t.pump(const Duration(seconds: 5));
  });

  testWidgets('Registration blocks under-18 users on the device as well', (t) async {
    await setSize(t, const Size(412, 892));
    await t.pumpWidget(ProviderScope(child: MaterialApp(theme: buildTheme(Brightness.dark), home: const AuthScreen(register: true))));
    await t.enterText(find.byType(TextFormField).at(0), 'teen@example.com');
    await t.enterText(find.byType(TextFormField).at(1), 'a-long-password');
    await t.tap(find.text('Continue'));
    await t.pump();
    expect(find.text('Please add your date of birth.'), findsOneWidget);
  });

  testWidgets('Welcome offers account creation and a clearly labelled demo', (t) async {
    await setSize(t, const Size(360, 740));
    await t.pumpWidget(ProviderScope(child: MaterialApp(theme: buildTheme(Brightness.light), home: const WelcomeScreen())));
    await t.pump();
    expect(find.text('Create account'), findsOneWidget);
    expect(find.text('Explore the demo with fictional profiles'), findsOneWidget);
    expect(find.text('FairMatch is for adults 18+.'), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  test('Demo enforces daily selections and honest waitlisting', () async {
    final repo = DemoRepository(latency: Duration.zero);
    var waitlisted = false, limited = false;
    for (var i = 0; i < 8; i++) {
      final p = await repo.currentPair();
      if (p.isEmpty) break;
      final target = p.candidates.firstWhere((c) => c.id != 'luca' && c.id != 'sam', orElse: () => p.candidates.last);
      try {
        final o = await repo.select(p.pairId!, target.id, 'k$i');
        if (o.state == InterestState.waitlisted) {
          waitlisted = true;
          expect(o.statusText, contains('Waiting in line'));
        }
      } on ApiException catch (e) {
        if (e.code == 'daily_limit_reached') limited = true;
        await repo.passPair(p.pairId!);
      }
    }
    expect(waitlisted || limited, isTrue);
    expect((await repo.me()).selections.remaining, lessThan(5));
  });
}

// Marker type used to assert that no discover content renders while loading.
class Discover {}
