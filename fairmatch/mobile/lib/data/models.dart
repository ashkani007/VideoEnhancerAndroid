// Plain data models mirroring the FairMatch API.

List<String> _strings(dynamic v) => (v as List?)?.map((e) => e.toString()).toList() ?? const [];
Map<String, String> _stringMap(dynamic v) =>
    (v as Map?)?.map((k, val) => MapEntry(k.toString(), val.toString())) ?? const {};

class Insights {
  const Insights({
    required this.available,
    required this.explanation,
    this.highlights = const [],
    this.sharedInterests = const [],
    this.sharedValues = const [],
    this.considerations = const [],
  });

  final bool available;
  final String explanation;
  final List<String> highlights, sharedInterests, sharedValues, considerations;

  factory Insights.fromJson(Map<String, dynamic> j) => Insights(
        available: j['available'] == true,
        explanation: j['explanation']?.toString() ?? '',
        highlights: _strings(j['highlights']),
        sharedInterests: _strings(j['shared_interests']),
        sharedValues: _strings(j['shared_values']),
        considerations: _strings(j['considerations']),
      );
}

class PromptAnswer {
  const PromptAnswer(this.question, this.answer);
  final String question, answer;
  factory PromptAnswer.fromJson(Map<String, dynamic> j) => PromptAnswer(j['q']?.toString() ?? '', j['a']?.toString() ?? '');
  Map<String, String> toJson() => {'q': question, 'a': answer};
}

class ProfileCard {
  const ProfileCard({
    required this.id,
    required this.firstName,
    required this.age,
    this.distance,
    this.city,
    this.gender,
    this.bio = '',
    this.photos = const [],
    this.intent,
    this.intentLabel,
    this.interests = const [],
    this.values = const [],
    this.lifestyle = const {},
    this.prompts = const [],
    this.verified = false,
    this.isDemo = false,
    this.promoted = false,
    this.insights,
  });

  final String id, firstName;
  final int age;
  final String? distance, city, gender, intent, intentLabel;
  final String bio;
  final List<String> photos, interests, values;
  final Map<String, String> lifestyle;
  final List<PromptAnswer> prompts;
  final bool verified, isDemo, promoted;
  final Insights? insights;

  factory ProfileCard.fromJson(Map<String, dynamic> j) => ProfileCard(
        id: j['id'].toString(),
        firstName: j['first_name']?.toString() ?? '',
        age: (j['age'] as num?)?.toInt() ?? 0,
        distance: j['distance'] as String?,
        city: j['city'] as String?,
        gender: j['gender'] as String?,
        bio: j['bio']?.toString() ?? '',
        photos: _strings(j['photos']),
        intent: j['relationship_intent'] as String?,
        intentLabel: j['relationship_intent_label'] as String?,
        interests: _strings(j['interests']),
        values: _strings(j['values']),
        lifestyle: _stringMap(j['lifestyle']),
        prompts: ((j['prompts'] as List?) ?? []).map((e) => PromptAnswer.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
        verified: j['verified'] == true,
        isDemo: j['is_demo'] == true,
        promoted: j['promoted'] == true,
        insights: j['insights'] is Map ? Insights.fromJson(Map<String, dynamic>.from(j['insights'] as Map)) : null,
      );
}

class Selections {
  const Selections(this.remaining, this.dailyLimit);
  final int remaining, dailyLimit;
  factory Selections.fromJson(Map<String, dynamic>? j) =>
      Selections((j?['remaining'] as num?)?.toInt() ?? 0, (j?['daily_limit'] as num?)?.toInt() ?? 0);
}

class PairData {
  const PairData({required this.pairId, required this.candidates, required this.selections, this.emptyReason});
  final String? pairId;
  final List<ProfileCard> candidates;
  final Selections selections;
  final String? emptyReason;

  bool get isEmpty => candidates.isEmpty;

  factory PairData.fromJson(Map<String, dynamic> j) => PairData(
        pairId: j['pair_id'] as String?,
        candidates: ((j['candidates'] as List?) ?? []).map((e) => ProfileCard.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
        selections: Selections.fromJson(j['selections'] as Map<String, dynamic>?),
        emptyReason: j['empty_reason'] as String?,
      );
}

/// Server state machine values for an interest request.
enum InterestState { waitlisted, pending, matched, rejected, expired, canceled, unknown }

InterestState parseState(String? s) => switch (s) {
      'WAITLISTED' => InterestState.waitlisted,
      'PENDING' => InterestState.pending,
      'MATCHED' => InterestState.matched,
      'REJECTED' => InterestState.rejected,
      'EXPIRED' => InterestState.expired,
      'CANCELED' => InterestState.canceled,
      _ => InterestState.unknown,
    };

class SelectionOutcome {
  const SelectionOutcome({required this.state, required this.statusText, required this.matched, this.matchId, required this.selections});
  final InterestState state;
  final String statusText;
  final bool matched;
  final String? matchId;
  final Selections selections;

  factory SelectionOutcome.fromJson(Map<String, dynamic> j) => SelectionOutcome(
        state: parseState(j['state'] as String?),
        statusText: j['status_text']?.toString() ?? '',
        matched: j['matched'] == true,
        matchId: j['match_id'] as String?,
        selections: Selections.fromJson(j['selections'] as Map<String, dynamic>?),
      );
}

class InterestItem {
  const InterestItem({required this.id, required this.state, required this.statusText, this.profile, this.expiresAt, required this.createdAt});
  final String id;
  final InterestState state;
  final String statusText;
  final ProfileCard? profile;
  final DateTime? expiresAt;
  final DateTime createdAt;

  factory InterestItem.fromJson(Map<String, dynamic> j) => InterestItem(
        id: j['id'].toString(),
        state: parseState(j['state'] as String?),
        statusText: j['status_text']?.toString() ?? '',
        profile: j['profile'] is Map ? ProfileCard.fromJson(Map<String, dynamic>.from(j['profile'] as Map)) : null,
        expiresAt: j['expires_at'] != null ? DateTime.tryParse(j['expires_at'].toString()) : null,
        createdAt: DateTime.tryParse(j['created_at']?.toString() ?? '') ?? DateTime.now(),
      );
}

class LikesData {
  const LikesData({required this.incomingCount, required this.canSeeIncoming, required this.incoming, required this.outgoing, this.note});
  final int incomingCount;
  final bool canSeeIncoming;
  final List<InterestItem> incoming, outgoing;
  final String? note;

  factory LikesData.fromJson(Map<String, dynamic> j) => LikesData(
        incomingCount: (j['incoming_count'] as num?)?.toInt() ?? 0,
        canSeeIncoming: j['can_see_incoming'] == true,
        incoming: ((j['incoming'] as List?) ?? []).map((e) => InterestItem.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
        outgoing: ((j['outgoing'] as List?) ?? []).map((e) => InterestItem.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
        note: j['incoming_note'] as String?,
      );
}

enum DeliveryStatus { sending, sent, delivered, read, received, failed }

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.matchId,
    required this.senderId,
    required this.clientMessageId,
    required this.body,
    required this.createdAt,
    required this.status,
  });

  final int id; // negative for local, unsent messages
  final String matchId, clientMessageId, body;
  final String? senderId;
  final DateTime createdAt;
  final DeliveryStatus status;

  ChatMessage copyWith({int? id, DeliveryStatus? status}) => ChatMessage(
        id: id ?? this.id,
        matchId: matchId,
        senderId: senderId,
        clientMessageId: clientMessageId,
        body: body,
        createdAt: createdAt,
        status: status ?? this.status,
      );

  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
        id: (j['id'] as num).toInt(),
        matchId: j['match_id'].toString(),
        senderId: j['sender_id'] as String?,
        clientMessageId: j['client_message_id']?.toString() ?? '',
        body: j['body']?.toString() ?? '',
        createdAt: DateTime.tryParse(j['created_at']?.toString() ?? '')?.toLocal() ?? DateTime.now(),
        status: switch (j['status']) {
          'read' => DeliveryStatus.read,
          'delivered' => DeliveryStatus.delivered,
          'received' => DeliveryStatus.received,
          _ => DeliveryStatus.sent,
        },
      );
}

class MatchItem {
  const MatchItem({required this.matchId, required this.profile, this.lastMessage, this.unread = 0, required this.createdAt});
  final String matchId;
  final ProfileCard profile;
  final ChatMessage? lastMessage;
  final int unread;
  final DateTime createdAt;

  factory MatchItem.fromJson(Map<String, dynamic> j) => MatchItem(
        matchId: j['match_id'].toString(),
        profile: ProfileCard.fromJson(Map<String, dynamic>.from(j['profile'] as Map)),
        lastMessage: j['last_message'] is Map ? ChatMessage.fromJson(Map<String, dynamic>.from(j['last_message'] as Map)) : null,
        unread: (j['unread_count'] as num?)?.toInt() ?? 0,
        createdAt: DateTime.tryParse(j['created_at']?.toString() ?? '') ?? DateTime.now(),
      );
}

class Entitlements {
  const Entitlements({
    required this.tier,
    required this.dailySelections,
    required this.seeIncomingLikes,
    required this.advancedFilters,
    required this.profileAnalytics,
    required this.aiAssistant,
  });

  final String tier;
  final int dailySelections;
  final bool seeIncomingLikes, advancedFilters, profileAnalytics, aiAssistant;

  static const free = Entitlements(
      tier: 'free', dailySelections: 5, seeIncomingLikes: false, advancedFilters: false, profileAnalytics: false, aiAssistant: false);

  String get label => switch (tier) { 'plus' => 'Plus', 'premium_ai' => 'Premium AI', _ => 'Free' };

  factory Entitlements.fromJson(Map<String, dynamic> j) => Entitlements(
        tier: j['tier']?.toString() ?? 'free',
        dailySelections: (j['daily_positive_selections'] as num?)?.toInt() ?? 5,
        seeIncomingLikes: j['see_incoming_likes'] == true,
        advancedFilters: j['advanced_filters'] == true,
        profileAnalytics: j['profile_analytics'] == true,
        aiAssistant: j['ai_assistant'] == true,
      );
}

class MyProfile {
  MyProfile({
    this.firstName = '',
    this.bio = '',
    this.gender,
    this.showGender = true,
    this.interestedIn = const [],
    this.intent,
    this.interests = const [],
    this.values = const [],
    this.lifestyle = const {},
    this.communication = const {},
    this.dealbreakers = const {},
    this.prompts = const [],
    this.city,
    this.hasLocation = false,
    this.ageMin = 18,
    this.ageMax = 99,
    this.maxDistanceKm = 50,
    this.showDistance = true,
    this.readReceipts = true,
    this.aiConsent = false,
    this.allowAiOnMyProfile = true,
    this.discoverable = true,
    this.completed = false,
    this.photos = const [],
  });

  String firstName, bio;
  String? gender, intent, city;
  bool showGender, hasLocation, showDistance, readReceipts, aiConsent, allowAiOnMyProfile, discoverable, completed;
  List<String> interestedIn, interests, values;
  Map<String, String> lifestyle, communication;
  Map<String, bool> dealbreakers;
  List<PromptAnswer> prompts;
  int ageMin, ageMax, maxDistanceKm;
  List<({String id, String url})> photos;

  double get completeness {
    final checks = [
      firstName.isNotEmpty, bio.isNotEmpty, gender != null, interestedIn.isNotEmpty, intent != null, interests.isNotEmpty,
      values.isNotEmpty, lifestyle.isNotEmpty, communication.isNotEmpty, prompts.isNotEmpty, hasLocation, photos.isNotEmpty,
    ];
    return checks.where((c) => c).length / checks.length;
  }

  factory MyProfile.fromJson(Map<String, dynamic> j) => MyProfile(
        firstName: j['first_name']?.toString() ?? '',
        bio: j['bio']?.toString() ?? '',
        gender: j['gender'] as String?,
        showGender: j['show_gender'] != false,
        interestedIn: _strings(j['interested_in']),
        intent: j['relationship_intent'] as String?,
        interests: _strings(j['interests']),
        values: _strings(j['values']),
        lifestyle: _stringMap(j['lifestyle']),
        communication: _stringMap(j['communication']),
        dealbreakers: (j['dealbreakers'] as Map?)?.map((k, v) => MapEntry(k.toString(), v == true)) ?? {},
        prompts: ((j['prompts'] as List?) ?? []).map((e) => PromptAnswer.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
        city: j['city_label'] as String?,
        hasLocation: j['has_location'] == true,
        ageMin: (j['age_min'] as num?)?.toInt() ?? 18,
        ageMax: (j['age_max'] as num?)?.toInt() ?? 99,
        maxDistanceKm: (j['max_distance_km'] as num?)?.toInt() ?? 50,
        showDistance: j['show_distance'] != false,
        readReceipts: j['read_receipts'] != false,
        aiConsent: j['ai_processing_consent'] == true,
        allowAiOnMyProfile: j['allow_ai_on_my_profile'] != false,
        discoverable: j['discoverable'] != false,
        completed: j['completed'] == true,
        photos: ((j['photos'] as List?) ?? [])
            .map((e) => (id: (e as Map)['id'].toString(), url: e['url'].toString()))
            .toList(),
      );
}

class Me {
  const Me({
    required this.id,
    required this.email,
    required this.age,
    required this.status,
    required this.verificationStatus,
    required this.isDemo,
    required this.entitlements,
    required this.selections,
    this.boostActiveUntil,
    this.profile,
  });

  final String id, email, status, verificationStatus;
  final int age;
  final bool isDemo;
  final Entitlements entitlements;
  final Selections selections;
  final DateTime? boostActiveUntil;
  final MyProfile? profile;

  factory Me.fromJson(Map<String, dynamic> j) => Me(
        id: j['id'].toString(),
        email: j['email']?.toString() ?? '',
        age: (j['age'] as num?)?.toInt() ?? 0,
        status: j['status']?.toString() ?? 'active',
        verificationStatus: j['verification_status']?.toString() ?? 'unverified',
        isDemo: j['is_demo'] == true,
        entitlements: Entitlements.fromJson(Map<String, dynamic>.from(j['entitlements'] as Map)),
        selections: Selections.fromJson(j['selections'] as Map<String, dynamic>?),
        boostActiveUntil: j['boost_active_until'] != null ? DateTime.tryParse(j['boost_active_until'].toString()) : null,
        profile: j['profile'] is Map ? MyProfile.fromJson(Map<String, dynamic>.from(j['profile'] as Map)) : null,
      );
}

class AiInsights {
  const AiInsights({
    required this.source,
    required this.summary,
    this.commonGround = const [],
    this.thingsToTalkAbout = const [],
    this.starters = const [],
    required this.disclaimer,
    this.note,
  });

  final String source, summary, disclaimer;
  final String? note;
  final List<String> commonGround, thingsToTalkAbout, starters;

  factory AiInsights.fromJson(Map<String, dynamic> j) => AiInsights(
        source: j['source']?.toString() ?? 'rules',
        summary: j['summary']?.toString() ?? '',
        commonGround: _strings(j['common_ground']),
        thingsToTalkAbout: _strings(j['things_to_talk_about']),
        starters: _strings(j['conversation_starters']),
        disclaimer: j['disclaimer']?.toString() ?? '',
        note: j['note'] as String?,
      );
}

class Product {
  const Product({required this.id, required this.kind, required this.price, required this.currency, this.tier, this.boostMinutes});
  final String id, kind, price, currency;
  final String? tier;
  final int? boostMinutes;

  factory Product.fromJson(Map<String, dynamic> j) => Product(
        id: j['id'].toString(),
        kind: j['kind']?.toString() ?? 'subscription',
        price: j['price']?.toString() ?? '',
        currency: j['currency']?.toString() ?? 'EUR',
        tier: j['tier'] as String?,
        boostMinutes: (j['boost_minutes'] as num?)?.toInt(),
      );
}

/// Realtime events pushed over the WebSocket.
sealed class RealtimeEvent {
  const RealtimeEvent();
}

class MessageEvent extends RealtimeEvent {
  const MessageEvent(this.message);
  final ChatMessage message;
}

class TypingEvent extends RealtimeEvent {
  const TypingEvent(this.matchId);
  final String matchId;
}

class ReadEvent extends RealtimeEvent {
  const ReadEvent(this.matchId, this.upToId);
  final String matchId;
  final int upToId;
}

class MatchEvent extends RealtimeEvent {
  const MatchEvent(this.matchId);
  final String matchId;
}

class InterestReceivedEvent extends RealtimeEvent {
  const InterestReceivedEvent();
}

class MatchClosedEvent extends RealtimeEvent {
  const MatchClosedEvent(this.matchId);
  final String matchId;
}

const intentLabels = {
  'long_term': 'Long-term relationship',
  'long_term_open_short': 'Long-term, open to short',
  'short_term_open_long': 'Short-term, open to long',
  'short_term': 'Something casual',
  'friendship_first': 'Friendship first',
  'figuring_out': 'Still figuring it out',
};
