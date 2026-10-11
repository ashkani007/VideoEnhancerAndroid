import 'models.dart';

/// Thrown for any failed backend call; [code] mirrors the API error code.
class ApiException implements Exception {
  ApiException(this.code, this.message, {this.status});
  final String code, message;
  final int? status;
  bool get isOffline => code == 'offline';
  @override
  String toString() => message;
}

/// Single contract implemented by the real HTTP backend and by the offline demo.
abstract class FairMatchRepository {
  bool get isDemo;

  // Auth
  Future<void> register({required String email, required String password, required DateTime dateOfBirth});
  Future<void> login(String email, String password);
  Future<bool> restoreSession();
  Future<void> logout();

  // Me / profile
  Future<Me> me();
  Future<Me> updateProfile(Map<String, dynamic> patch);
  Future<void> uploadPhoto(List<int> bytes, String filename);
  Future<void> deletePhoto(String photoId);
  Future<Map<String, dynamic>> exportData();
  Future<void> deleteAccount();

  // Discover
  Future<PairData> currentPair();
  Future<SelectionOutcome> select(String pairId, String candidateId, String idempotencyKey);
  Future<void> passPair(String pairId);
  Future<ProfileCard> profile(String userId);

  // Likes
  Future<LikesData> likes();
  Future<SelectionOutcome> respond(String interestId, bool accept);
  Future<void> cancelInterest(String interestId);

  // Matches & messaging
  Future<List<MatchItem>> matches();
  Future<List<ChatMessage>> messages(String matchId, {int? beforeId, int? afterId});
  Future<ChatMessage> sendMessage(String matchId, String body, String clientMessageId);
  Future<void> markRead(String matchId, int upToId);
  void sendTyping(String matchId);
  Future<void> unmatch(String matchId);
  Stream<RealtimeEvent> get events;

  // Safety
  Future<void> block(String userId);
  Future<void> report(String userId, String reason, String details, {bool alsoBlock = true});

  // AI
  Future<AiInsights> aiInsights(String userId);
  Future<List<String>> aiRephrase(String draft);
  Future<List<String>> aiReflection();

  // Billing
  Future<List<Product>> products();
  Future<void> verifyPurchase(String productId, String purchaseToken);
}
