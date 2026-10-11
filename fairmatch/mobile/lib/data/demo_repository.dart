import 'dart:async';
import 'dart:math';

import 'models.dart';
import 'repository.dart';

/// Fully offline DEMO MODE. Every person here is fictional and clearly labelled as such.
/// It mirrors the server's rules (daily selections, pending capacity, honest request
/// states, mutual-only matches) so the product can be experienced without a backend.
class DemoRepository implements FairMatchRepository {
  DemoRepository({Random? random, this.latency = const Duration(milliseconds: 450)}) : _rng = random ?? Random(7);

  final Random _rng;
  final Duration latency;
  final _events = StreamController<RealtimeEvent>.broadcast();
  bool _signedIn = false;
  String _tier = 'free';
  int _usedToday = 0;
  int _pairSeq = 0, _msgSeq = 1, _interestSeq = 0;
  DateTime? _boostUntil;
  PairData? _open;
  final Set<String> _seen = {};
  final Set<String> _blocked = {};
  final Map<String, _DemoInterest> _outgoing = {};
  final Map<String, List<ChatMessage>> _chats = {};
  final Map<String, MatchItem> _matches = {};

  final MyProfile _profile = MyProfile(
    firstName: 'Robin',
    bio: 'Demo account — explore FairMatch with fictional people.',
    gender: 'woman',
    interestedIn: ['man', 'nonbinary'],
    intent: 'long_term',
    interests: ['climbing', 'coffee', 'film', 'travel'],
    values: ['honesty', 'kindness', 'humour'],
    lifestyle: {'smoking': 'never', 'drinking': 'socially', 'exercise': 'often'},
    communication: {'texting': 'often', 'planning': 'flexible'},
    prompts: const [PromptAnswer('A perfect Sunday', 'Farmers market, a long walk, and cooking something new together.')],
    city: 'Amsterdam',
    hasLocation: true,
    ageMin: 22,
    ageMax: 40,
    aiConsent: true,
    completed: true,
  );

  // Fictional people. `likesYou` = already chose the demo user (match on selection).
  // `answer` = how they respond to a request after a short delay (true accept, false decline, null no reply).
  late final List<_DemoPerson> _people = [
    _DemoPerson('luca', 'Luca', 29, 'man', 'long_term', ['climbing', 'coffee', 'film', 'cooking'], ['honesty', 'family', 'humour'],
        'Software engineer who makes a mean risotto. Dog person, cat-tolerant.', 'About 5 km away', likesYou: true, verified: true),
    _DemoPerson('sam', 'Sam', 27, 'nonbinary', 'long_term', ['poetry', 'climbing', 'vinyl', 'tea'], ['kindness', 'creativity', 'honesty'],
        'Bookseller, amateur climber, professional overthinker.', 'Less than 5 km away', likesYou: true, verified: true),
    _DemoPerson('daniel', 'Daniel', 32, 'man', 'long_term', ['running', 'jazz', 'books', 'travel'], ['kindness', 'growth', 'honesty'],
        'Paediatric nurse. Sunday long runs, Monday long naps.', 'About 10 km away', answer: true, verified: true),
    _DemoPerson('kenji', 'Kenji', 30, 'man', 'long_term', ['ceramics', 'hiking', 'tea', 'languages'], ['curiosity', 'kindness', 'family'],
        'Potter. My mugs are lopsided but full of love.', 'About 15 km away', answer: null),
    _DemoPerson('river', 'River', 30, 'nonbinary', 'long_term_open_short', ['gardening', 'film', 'cooking'], ['curiosity', 'humour'],
        'Community garden coordinator. Tomatoes are a personality.', 'About 10 km away', answer: false, verified: true),
    _DemoPerson('omar', 'Omar', 27, 'man', 'long_term_open_short', ['football', 'photography', 'coffee'], ['loyalty', 'ambition'],
        'Weekend photographer, weekday optimist.', 'About 20 km away', answer: true, inboxFull: true),
    _DemoPerson('ivan', 'Ivan', 28, 'man', 'long_term', ['chess', 'museums', 'running'], ['honesty', 'growth'],
        'Chess club regular looking for a life partner, not a stalemate.', 'About 5 km away', answer: null),
    _DemoPerson('mateo', 'Mateo', 34, 'man', 'friendship_first', ['board games', 'baking', 'cycling'], ['humour', 'loyalty'],
        'Will bake you sourdough. Strong opinions about board game rules.', 'About 25 km away', answer: true),
    _DemoPerson('ari', 'Ari', 25, 'nonbinary', 'figuring_out', ['dancing', 'photography', 'travel'], ['adventure', 'independence'],
        'Dancer seeking someone to explore the city with.', 'Less than 5 km away', answer: null, verified: true),
    _DemoPerson('theo', 'Theo', 26, 'man', 'short_term_open_long', ['skating', 'festivals', 'music production'], ['creativity', 'adventure'],
        'Making beats and bad puns.', 'About 30 km away', answer: false),
  ];

  static const _prompts = [
    PromptAnswer("I'm weirdly good at", 'Remembering song lyrics from 2009.'),
    PromptAnswer('Green flag I look for', 'Kindness to waiters and patience with plants.'),
    PromptAnswer('Let\'s debate', 'Is a hot dog a sandwich?'),
    PromptAnswer('A perfect Sunday', 'Long breakfast, longer walk.'),
  ];

  static const _replies = [
    'Haha, I love that! What got you into it?',
    'Okay you have my attention 😄',
    "That's such a good question. Honestly? Probably a long walk somewhere green.",
    'Would you be up for coffee sometime this week?',
    "Tell me more — I'm curious!",
  ];

  @override
  bool get isDemo => true;

  @override
  Stream<RealtimeEvent> get events => _events.stream;

  Future<void> _wait([double factor = 1]) => Future.delayed(latency * factor);

  int get _limit => _tier == 'free' ? 5 : 15;

  Entitlements get _entitlements => switch (_tier) {
        'plus' => const Entitlements(
            tier: 'plus', dailySelections: 15, seeIncomingLikes: true, advancedFilters: true, profileAnalytics: true, aiAssistant: false),
        'premium_ai' => const Entitlements(
            tier: 'premium_ai', dailySelections: 15, seeIncomingLikes: true, advancedFilters: true, profileAnalytics: true, aiAssistant: true),
        _ => Entitlements.free,
      };

  Selections get _selections => Selections(max(0, _limit - _usedToday), _limit);

  ProfileCard _card(_DemoPerson p, {bool withInsights = true}) {
    final sharedI = p.interests.where(_profile.interests.contains).toList();
    final sharedV = p.values.where(_profile.values.contains).toList();
    final goalsAlign = p.intent == _profile.intent || p.intent == 'long_term_open_short';
    return ProfileCard(
      id: p.id,
      firstName: p.name,
      age: p.age,
      distance: p.distance,
      city: 'Amsterdam',
      gender: p.gender,
      bio: p.bio,
      intent: p.intent,
      intentLabel: intentLabels[p.intent],
      interests: p.interests,
      values: p.values,
      lifestyle: const {'smoking': 'never', 'drinking': 'socially'},
      prompts: [_prompts[p.name.length % _prompts.length], _prompts[(p.name.length + 1) % _prompts.length]],
      verified: p.verified,
      isDemo: true,
      insights: !withInsights
          ? null
          : (sharedI.isEmpty && sharedV.isEmpty && !goalsAlign)
              ? const Insights(
                  available: false,
                  explanation: 'Not enough shared profile information yet to say much about compatibility.',
                )
              : Insights(
                  available: true,
                  explanation: 'Based only on what you both chose to share. This is not a prediction of relationship success.',
                  highlights: [
                    if (goalsAlign) 'Looking for a similar kind of relationship',
                    if (sharedV.isNotEmpty) 'Shares values you care about',
                  ],
                  sharedInterests: sharedI,
                  sharedValues: sharedV,
                  considerations: [if (!goalsAlign) 'You may be looking for different kinds of relationships'],
                ),
    );
  }

  _DemoPerson _person(String id) => _people.firstWhere((p) => p.id == id);

  // ------------------------------------------------------------ auth
  @override
  Future<void> register({required String email, required String password, required DateTime dateOfBirth}) async {
    await _wait();
    _signedIn = true;
  }

  @override
  Future<void> login(String email, String password) async {
    await _wait();
    _signedIn = true;
  }

  @override
  Future<bool> restoreSession() async => _signedIn;

  @override
  Future<void> logout() async => _signedIn = false;

  // ------------------------------------------------------------ me
  @override
  Future<Me> me() async {
    await _wait(0.3);
    return Me(
      id: 'demo-me',
      email: 'demo@demo.fairmatch.app',
      age: 28,
      status: 'active',
      verificationStatus: 'verified',
      isDemo: true,
      entitlements: _entitlements,
      selections: _selections,
      boostActiveUntil: _boostUntil != null && _boostUntil!.isAfter(DateTime.now()) ? _boostUntil : null,
      profile: _profile..completed = true,
    );
  }

  @override
  Future<Me> updateProfile(Map<String, dynamic> patch) async {
    await _wait(0.5);
    final p = _profile;
    patch.forEach((k, v) {
      switch (k) {
        case 'first_name':
          p.firstName = v as String;
        case 'bio':
          p.bio = v as String;
        case 'gender':
          p.gender = v as String;
        case 'interested_in':
          p.interestedIn = List<String>.from(v as List);
        case 'relationship_intent':
          p.intent = v as String;
        case 'interests':
          p.interests = List<String>.from(v as List);
        case 'values':
          p.values = List<String>.from(v as List);
        case 'lifestyle':
          p.lifestyle = Map<String, String>.from(v as Map);
        case 'communication':
          p.communication = Map<String, String>.from(v as Map);
        case 'dealbreakers':
          p.dealbreakers = Map<String, bool>.from(v as Map);
        case 'age_min':
          p.ageMin = v as int;
        case 'age_max':
          p.ageMax = v as int;
        case 'max_distance_km':
          p.maxDistanceKm = v as int;
        case 'show_distance':
          p.showDistance = v as bool;
        case 'read_receipts':
          p.readReceipts = v as bool;
        case 'ai_processing_consent':
          p.aiConsent = v as bool;
        case 'allow_ai_on_my_profile':
          p.allowAiOnMyProfile = v as bool;
        case 'discoverable':
          p.discoverable = v as bool;
        case 'show_gender':
          p.showGender = v as bool;
        case 'city_label':
          p.city = v as String?;
        case 'latitude':
          p.hasLocation = true;
        case 'prompts':
          p.prompts = (v as List).map((e) => PromptAnswer.fromJson(Map<String, dynamic>.from(e as Map))).toList();
      }
    });
    return me();
  }

  @override
  Future<void> uploadPhoto(List<int> bytes, String filename) async => _wait();

  @override
  Future<void> deletePhoto(String photoId) async => _wait();

  @override
  Future<Map<String, dynamic>> exportData() async => {
        'note': 'Demo mode export — contains only fictional demo data.',
        'profile': {'first_name': _profile.firstName, 'interests': _profile.interests},
        'matches': _matches.keys.toList(),
      };

  @override
  Future<void> deleteAccount() async => _signedIn = false;

  // ------------------------------------------------------------ discover
  List<_DemoPerson> get _available => _people
      .where((p) => !_seen.contains(p.id) && !_blocked.contains(p.id) && !_outgoing.values.any((i) => i.personId == p.id))
      .where((p) => _profile.interestedIn.contains(p.gender) || _profile.interestedIn.contains('everyone'))
      .toList();

  @override
  Future<PairData> currentPair() async {
    await _wait();
    if (_open != null) return _open!;
    final pool = _available;
    if (pool.isEmpty) {
      return PairData(
        pairId: null,
        candidates: const [],
        selections: _selections,
        emptyReason: "You've seen every fictional demo profile. In the real app, new people appear as they join — "
            'we never show made-up profiles to real members.',
      );
    }
    // People who already chose you always get a slot (same rule as the server).
    pool.sort((a, b) => (b.likesYou ? 1 : 0) - (a.likesYou ? 1 : 0));
    final first = pool.first;
    final rest = pool.skip(1).toList()..shuffle(_rng);
    final picks = [first, if (rest.isNotEmpty) rest.first];
    _pairSeq++;
    _open = PairData(pairId: 'demo-pair-$_pairSeq', candidates: picks.map(_card).toList(), selections: _selections);
    return _open!;
  }

  @override
  Future<SelectionOutcome> select(String pairId, String candidateId, String idempotencyKey) async {
    await _wait(1.4);
    final open = _open;
    if (open == null || open.pairId != pairId) throw ApiException('pair_closed', 'This pair has already been resolved');
    final p = _person(candidateId);
    if (!p.likesYou && _usedToday >= _limit) {
      throw ApiException('daily_limit_reached', "You've used today's selections. They refresh tomorrow.");
    }
    for (final c in open.candidates) {
      _seen.add(c.id);
    }
    _open = null;
    if (p.likesYou) {
      final m = _createMatch(p);
      return SelectionOutcome(state: InterestState.matched, statusText: 'Matched', matched: true, matchId: m, selections: _selections);
    }
    _usedToday++;
    final id = 'demo-interest-${++_interestSeq}';
    final state = p.inboxFull ? InterestState.waitlisted : InterestState.pending;
    _outgoing[id] = _DemoInterest(id, p.id, state, DateTime.now());
    if (p.answer != null) {
      Timer(const Duration(seconds: 6), () {
        final it = _outgoing[id];
        if (it == null || it.state == InterestState.canceled) return;
        if (it.state == InterestState.waitlisted) {
          it.state = InterestState.pending; // capacity freed -> delivered
          Timer(const Duration(seconds: 6), () => _resolve(it, p));
        } else {
          _resolve(it, p);
        }
      });
    }
    return SelectionOutcome(
      state: state,
      statusText: state == InterestState.pending
          ? 'Delivered — waiting for their answer'
          : "Waiting in line — they'll see it when they have room",
      matched: false,
      selections: _selections,
    );
  }

  void _resolve(_DemoInterest it, _DemoPerson p) {
    if (it.state != InterestState.pending) return;
    if (p.answer == true) {
      it.state = InterestState.matched;
      final m = _createMatch(p);
      _events.add(MatchEvent(m));
    } else {
      it.state = InterestState.rejected;
    }
  }

  String _createMatch(_DemoPerson p) {
    final id = 'demo-match-${p.id}';
    _matches[id] = MatchItem(matchId: id, profile: _card(p, withInsights: false), createdAt: DateTime.now());
    _chats[id] = [];
    return id;
  }

  @override
  Future<void> passPair(String pairId) async {
    await _wait(0.6);
    for (final c in _open?.candidates ?? const <ProfileCard>[]) {
      _seen.add(c.id);
    }
    _open = null;
  }

  @override
  Future<ProfileCard> profile(String userId) async {
    await _wait(0.4);
    return _card(_person(userId));
  }

  // ------------------------------------------------------------ likes
  @override
  Future<LikesData> likes() async {
    await _wait();
    final incoming = _people.where((p) => p.likesYou && !_seen.contains(p.id) && !_matches.containsKey('demo-match-${p.id}')).toList();
    final ent = _entitlements;
    return LikesData(
      incomingCount: incoming.length,
      canSeeIncoming: ent.seeIncomingLikes,
      incoming: ent.seeIncomingLikes
          ? incoming
              .map((p) => InterestItem(
                    id: 'in-${p.id}',
                    state: InterestState.pending,
                    statusText: 'Delivered',
                    profile: _card(p),
                    createdAt: DateTime.now().subtract(const Duration(hours: 3)),
                    expiresAt: DateTime.now().add(const Duration(hours: 45)),
                  ))
              .toList()
          : const [],
      outgoing: _outgoing.values.toList().reversed
          .map((i) => InterestItem(
                id: i.id,
                state: i.state,
                statusText: _copy(i.state),
                profile: _card(_person(i.personId), withInsights: false),
                createdAt: i.createdAt,
                expiresAt: i.createdAt.add(const Duration(hours: 48)),
              ))
          .toList(),
      note: incoming.isNotEmpty && !ent.seeIncomingLikes
          ? 'People who chose you are shown in your Discover pairs first, so you can choose them back for free. '
              'Plus lets you see and answer them here directly.'
          : null,
    );
  }

  String _copy(InterestState s) => switch (s) {
        InterestState.waitlisted => "Waiting in line — they'll see it when they have room",
        InterestState.pending => 'Delivered — waiting for their answer',
        InterestState.matched => 'Matched',
        InterestState.rejected => 'Not this time',
        InterestState.expired => 'Expired',
        InterestState.canceled => 'Canceled',
        _ => '',
      };

  @override
  Future<SelectionOutcome> respond(String interestId, bool accept) async {
    await _wait();
    final p = _person(interestId.replaceFirst('in-', ''));
    _seen.add(p.id);
    if (_open?.candidates.any((c) => c.id == p.id) ?? false) _open = null;
    if (!accept) return SelectionOutcome(state: InterestState.rejected, statusText: '', matched: false, selections: _selections);
    final m = _createMatch(p);
    return SelectionOutcome(state: InterestState.matched, statusText: '', matched: true, matchId: m, selections: _selections);
  }

  @override
  Future<void> cancelInterest(String interestId) async {
    await _wait(0.5);
    final it = _outgoing[interestId];
    if (it == null || (it.state != InterestState.pending && it.state != InterestState.waitlisted)) {
      throw ApiException('not_cancelable', 'This request can no longer be canceled');
    }
    it.state = InterestState.canceled;
  }

  // ------------------------------------------------------------ matches & chat
  @override
  Future<List<MatchItem>> matches() async {
    await _wait(0.6);
    final list = _matches.values.map((m) {
      final msgs = _chats[m.matchId] ?? [];
      return MatchItem(
        matchId: m.matchId,
        profile: m.profile,
        createdAt: m.createdAt,
        lastMessage: msgs.isEmpty ? null : msgs.last,
        unread: msgs.where((x) => x.senderId != 'demo-me' && x.status == DeliveryStatus.received).length,
      );
    }).toList();
    list.sort((a, b) => (b.lastMessage?.createdAt ?? b.createdAt).compareTo(a.lastMessage?.createdAt ?? a.createdAt));
    return list;
  }

  @override
  Future<List<ChatMessage>> messages(String matchId, {int? beforeId, int? afterId}) async {
    await _wait(0.4);
    final all = _chats[matchId] ?? [];
    if (afterId != null) return all.where((m) => m.id > afterId).toList();
    if (beforeId != null) return all.where((m) => m.id < beforeId).toList();
    return List.of(all);
  }

  @override
  Future<ChatMessage> sendMessage(String matchId, String body, String clientMessageId) async {
    await _wait(0.5);
    final list = _chats.putIfAbsent(matchId, () => []);
    final existing = list.where((m) => m.clientMessageId == clientMessageId);
    if (existing.isNotEmpty) return existing.first;
    final msg = ChatMessage(
      id: _msgSeq++,
      matchId: matchId,
      senderId: 'demo-me',
      clientMessageId: clientMessageId,
      body: body,
      createdAt: DateTime.now(),
      status: DeliveryStatus.delivered,
    );
    list.add(msg);
    // Fictional partner reads and replies so the real-time UI can be experienced.
    Timer(const Duration(milliseconds: 1600), () {
      final i = list.indexWhere((m) => m.id == msg.id);
      if (i >= 0) list[i] = msg.copyWith(status: DeliveryStatus.read);
      _events.add(ReadEvent(matchId, msg.id));
      _events.add(TypingEvent(matchId));
    });
    Timer(const Duration(milliseconds: 4200), () {
      final reply = ChatMessage(
        id: _msgSeq++,
        matchId: matchId,
        senderId: matchId.replaceFirst('demo-match-', ''),
        clientMessageId: 'demo-reply-$_msgSeq',
        body: _replies[_rng.nextInt(_replies.length)],
        createdAt: DateTime.now(),
        status: DeliveryStatus.received,
      );
      list.add(reply);
      _events.add(MessageEvent(reply));
    });
    return msg;
  }

  @override
  Future<void> markRead(String matchId, int upToId) async {}

  @override
  void sendTyping(String matchId) {}

  @override
  Future<void> unmatch(String matchId) async {
    await _wait(0.5);
    _matches.remove(matchId);
    _chats.remove(matchId);
  }

  // ------------------------------------------------------------ safety
  @override
  Future<void> block(String userId) async {
    await _wait(0.5);
    _blocked.add(userId);
    _matches.remove('demo-match-$userId');
    if (_open?.candidates.any((c) => c.id == userId) ?? false) _open = null;
  }

  @override
  Future<void> report(String userId, String reason, String details, {bool alsoBlock = true}) async {
    if (alsoBlock) await block(userId);
  }

  // ------------------------------------------------------------ AI
  @override
  Future<AiInsights> aiInsights(String userId) async {
    if (!_entitlements.aiAssistant) throw ApiException('forbidden', 'The AI assistant is part of Premium AI');
    if (!_profile.aiConsent) throw ApiException('ai_consent_required', 'Turn on AI processing in Privacy settings to use the assistant');
    await _wait(2);
    final p = _person(userId);
    final shared = p.interests.where(_profile.interests.contains).toList();
    final values = p.values.where(_profile.values.contains).toList();
    return AiInsights(
      source: 'demo',
      summary: shared.isEmpty
          ? "You and ${p.name} have different hobbies, which can make for great conversations about trying something new."
          : 'You and ${p.name} both enjoy ${shared.join(' and ')}, and you seem to value ${values.isEmpty ? 'similar things' : values.join(', ')}.',
      commonGround: [
        if (shared.isNotEmpty) 'Shared interests: ${shared.join(', ')}',
        if (values.isNotEmpty) 'Shared values: ${values.join(', ')}',
        if (p.intent == _profile.intent) 'Looking for the same kind of relationship',
      ],
      thingsToTalkAbout: [if (p.intent != _profile.intent) 'What each of you is hoping to find right now'],
      starters: [
        if (shared.isNotEmpty) 'You mentioned ${shared.first} — what got you into it?',
        'Your profile says “${p.bio.split('.').first}.” — tell me more!',
        'What does a really good weekend look like for you?',
      ],
      disclaimer: 'Demo mode: example suggestions generated on-device from fictional data. Not predictions.',
    );
  }

  @override
  Future<List<String>> aiRephrase(String draft) async {
    await _wait(1.5);
    final d = draft.trim();
    return [
      if (d.isNotEmpty) '${d[0].toUpperCase()}${d.substring(1)}${d.endsWith('?') ? '' : ' — what do you think?'}',
      'Hey! $d 😊',
      'I was curious: $d',
    ];
  }

  @override
  Future<List<String>> aiReflection() async {
    await _wait(1.2);
    return [
      'You\'re looking for a long-term relationship. People with matching goals are prioritised for you.',
      'You choose often when people share values like honesty — that\'s a great signal to keep.',
      'Adding one more prompt would help others start a conversation with you.',
    ];
  }

  // ------------------------------------------------------------ billing (simulated)
  @override
  Future<List<Product>> products() async => const [
        Product(id: 'fairmatch_plus_monthly', kind: 'subscription', price: '9.99', currency: 'EUR', tier: 'plus'),
        Product(id: 'fairmatch_premium_ai_monthly', kind: 'subscription', price: '19.99', currency: 'EUR', tier: 'premium_ai'),
        Product(id: 'fairmatch_boost_30m', kind: 'consumable', price: '2.99', currency: 'EUR', boostMinutes: 30),
      ];

  @override
  Future<void> verifyPurchase(String productId, String purchaseToken) async {
    await _wait(1.2);
    if (productId == 'fairmatch_boost_30m') {
      _boostUntil = DateTime.now().add(const Duration(minutes: 30));
    } else {
      _tier = productId == 'fairmatch_plus_monthly' ? 'plus' : 'premium_ai';
    }
  }
}

class _DemoPerson {
  _DemoPerson(this.id, this.name, this.age, this.gender, this.intent, this.interests, this.values, this.bio, this.distance,
      {this.likesYou = false, this.answer, this.verified = false, this.inboxFull = false});
  final String id, name, gender, intent, bio, distance;
  final int age;
  final List<String> interests, values;
  final bool likesYou, verified, inboxFull;
  final bool? answer;
}

class _DemoInterest {
  _DemoInterest(this.id, this.personId, this.state, this.createdAt);
  final String id, personId;
  InterestState state;
  final DateTime createdAt;
}
