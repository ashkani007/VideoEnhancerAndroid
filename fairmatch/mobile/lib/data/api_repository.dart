import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import 'models.dart';
import 'repository.dart';

/// Talks to the FastAPI backend. Tokens live in the platform keystore (flutter_secure_storage).
class ApiRepository implements FairMatchRepository {
  ApiRepository(this.baseUrl, {http.Client? client, FlutterSecureStorage? storage})
      : _http = client ?? http.Client(),
        _storage = storage ?? const FlutterSecureStorage();

  final String baseUrl;
  final http.Client _http;
  final FlutterSecureStorage _storage;
  String? _access, _refresh;
  Future<bool>? _refreshing;

  WebSocketChannel? _ws;
  StreamSubscription? _wsSub;
  Timer? _reconnect, _ping;
  int _backoff = 1;
  final _events = StreamController<RealtimeEvent>.broadcast();

  @override
  bool get isDemo => false;

  @override
  Stream<RealtimeEvent> get events => _events.stream;

  // ------------------------------------------------------------ transport
  Future<dynamic> _req(String method, String path,
      {Object? body, Map<String, String>? headers, bool auth = true, bool retried = false}) async {
    final uri = Uri.parse('$baseUrl$path');
    final h = {'Content-Type': 'application/json', 'Accept': 'application/json', ...?headers};
    if (auth && _access != null) h['Authorization'] = 'Bearer $_access';
    http.Response r;
    try {
      final req = http.Request(method, uri)..headers.addAll(h);
      if (body != null) req.body = jsonEncode(body);
      r = await http.Response.fromStream(await _http.send(req).timeout(const Duration(seconds: 20)));
    } on TimeoutException {
      throw ApiException('offline', 'The server took too long to respond.');
    } on http.ClientException {
      throw ApiException('offline', "You're offline or FairMatch can't be reached. Try again in a moment.");
    }
    if (r.statusCode == 401 && auth && !retried && _refresh != null) {
      if (await _refreshTokens()) return _req(method, path, body: body, headers: headers, auth: auth, retried: true);
    }
    if (r.statusCode >= 400) throw _error(r);
    if (r.statusCode == 204 || r.body.isEmpty) return null;
    return jsonDecode(utf8.decode(r.bodyBytes));
  }

  ApiException _error(http.Response r) {
    try {
      final d = jsonDecode(utf8.decode(r.bodyBytes))['detail'];
      if (d is Map) return ApiException(d['code']?.toString() ?? 'error', d['message']?.toString() ?? 'Something went wrong', status: r.statusCode);
    } catch (_) {}
    return ApiException('error', 'Something went wrong (${r.statusCode})', status: r.statusCode);
  }

  Future<bool> _refreshTokens() => _refreshing ??= () async {
        try {
          final res = await _req('POST', '/auth/refresh', body: {'refresh_token': _refresh}, auth: false, retried: true);
          await _store(res as Map<String, dynamic>);
          return true;
        } catch (_) {
          await _clear();
          return false;
        } finally {
          _refreshing = null;
        }
      }();

  Future<void> _store(Map<String, dynamic> tokens) async {
    _access = tokens['access_token'] as String;
    _refresh = tokens['refresh_token'] as String;
    await _storage.write(key: 'fm_refresh', value: _refresh);
  }

  Future<void> _clear() async {
    _access = _refresh = null;
    await _storage.delete(key: 'fm_refresh');
    _closeSocket();
  }

  // ------------------------------------------------------------ realtime
  void _openSocket() {
    _closeSocket();
    final wsUrl = baseUrl.replaceFirst(RegExp('^http'), 'ws');
    try {
      _ws = WebSocketChannel.connect(Uri.parse('$wsUrl/ws'));
      _ws!.sink.add(jsonEncode({'type': 'auth', 'token': _access}));
      _wsSub = _ws!.stream.listen(_onWs, onDone: _scheduleReconnect, onError: (_) => _scheduleReconnect());
      _ping = Timer.periodic(const Duration(seconds: 25), (_) => _ws?.sink.add(jsonEncode({'type': 'ping'})));
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _onWs(dynamic raw) {
    final m = jsonDecode(raw as String) as Map<String, dynamic>;
    switch (m['type']) {
      case 'ready':
        _backoff = 1;
      case 'message':
        _events.add(MessageEvent(ChatMessage.fromJson(Map<String, dynamic>.from(m['message'] as Map))));
      case 'typing':
        _events.add(TypingEvent(m['match_id'].toString()));
      case 'read':
        _events.add(ReadEvent(m['match_id'].toString(), (m['up_to_id'] as num).toInt()));
      case 'match':
        _events.add(MatchEvent(m['match_id'].toString()));
      case 'interest_received':
        _events.add(const InterestReceivedEvent());
      case 'match_closed':
        _events.add(MatchClosedEvent(m['match_id'].toString()));
    }
  }

  void _scheduleReconnect() {
    _closeSocket();
    if (_access == null) return;
    _reconnect = Timer(Duration(seconds: _backoff), () async {
      _backoff = (_backoff * 2).clamp(1, 60);
      if (_refresh != null) await _refreshTokens(); // socket auth uses a fresh access token
      if (_access != null) _openSocket();
    });
  }

  void _closeSocket() {
    _reconnect?.cancel();
    _ping?.cancel();
    _wsSub?.cancel();
    _ws?.sink.close();
    _ws = null;
  }

  // ------------------------------------------------------------ auth
  @override
  Future<void> register({required String email, required String password, required DateTime dateOfBirth}) async {
    final res = await _req('POST', '/auth/register', auth: false, body: {
      'email': email,
      'password': password,
      'date_of_birth': dateOfBirth.toIso8601String().substring(0, 10),
      'accept_terms': true,
      'accept_privacy': true,
    });
    await _store(res as Map<String, dynamic>);
    _openSocket();
  }

  @override
  Future<void> login(String email, String password) async {
    final res = await _req('POST', '/auth/login', auth: false, body: {'email': email, 'password': password});
    await _store(res as Map<String, dynamic>);
    _openSocket();
  }

  @override
  Future<bool> restoreSession() async {
    _refresh = await _storage.read(key: 'fm_refresh');
    if (_refresh == null) return false;
    final ok = await _refreshTokens();
    if (ok) _openSocket();
    return ok;
  }

  @override
  Future<void> logout() async {
    try {
      if (_refresh != null) await _req('POST', '/auth/logout', body: {'refresh_token': _refresh});
    } catch (_) {}
    await _clear();
  }

  // ------------------------------------------------------------ me
  @override
  Future<Me> me() async => Me.fromJson(await _req('GET', '/me') as Map<String, dynamic>);

  @override
  Future<Me> updateProfile(Map<String, dynamic> patch) async =>
      Me.fromJson(await _req('PATCH', '/me/profile', body: patch) as Map<String, dynamic>);

  @override
  Future<void> uploadPhoto(List<int> bytes, String filename) async {
    final req = http.MultipartRequest('POST', Uri.parse('$baseUrl/me/photos'))
      ..headers['Authorization'] = 'Bearer $_access'
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final r = await http.Response.fromStream(await _http.send(req));
    if (r.statusCode >= 400) throw _error(r);
  }

  @override
  Future<void> deletePhoto(String photoId) async => _req('DELETE', '/me/photos/$photoId');

  @override
  Future<Map<String, dynamic>> exportData() async => await _req('GET', '/me/export') as Map<String, dynamic>;

  @override
  Future<void> deleteAccount() async {
    await _req('DELETE', '/me');
    await _clear();
  }

  // ------------------------------------------------------------ discover
  @override
  Future<PairData> currentPair() async => PairData.fromJson(await _req('GET', '/discover/pair') as Map<String, dynamic>);

  @override
  Future<SelectionOutcome> select(String pairId, String candidateId, String idempotencyKey) async => SelectionOutcome.fromJson(
      await _req('POST', '/discover/select',
          body: {'pair_id': pairId, 'candidate_id': candidateId}, headers: {'Idempotency-Key': idempotencyKey}) as Map<String, dynamic>);

  @override
  Future<void> passPair(String pairId) async => _req('POST', '/discover/pass/$pairId');

  @override
  Future<ProfileCard> profile(String userId) async => ProfileCard.fromJson(await _req('GET', '/users/$userId') as Map<String, dynamic>);

  @override
  Future<LikesData> likes() async => LikesData.fromJson(await _req('GET', '/likes') as Map<String, dynamic>);

  @override
  Future<SelectionOutcome> respond(String interestId, bool accept) async {
    final r = await _req('POST', '/likes/$interestId/respond', body: {'accept': accept}) as Map<String, dynamic>;
    return SelectionOutcome(
      state: parseState(r['state'] as String?),
      statusText: '',
      matched: r['matched'] == true,
      matchId: r['match_id'] as String?,
      selections: const Selections(0, 0),
    );
  }

  @override
  Future<void> cancelInterest(String interestId) async => _req('POST', '/likes/$interestId/cancel');

  // ------------------------------------------------------------ matches
  @override
  Future<List<MatchItem>> matches() async {
    final r = await _req('GET', '/matches') as Map<String, dynamic>;
    return (r['matches'] as List).map((e) => MatchItem.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  @override
  Future<List<ChatMessage>> messages(String matchId, {int? beforeId, int? afterId}) async {
    final q = [if (beforeId != null) 'before_id=$beforeId', if (afterId != null) 'after_id=$afterId'].join('&');
    final r = await _req('GET', '/matches/$matchId/messages${q.isEmpty ? '' : '?$q'}') as Map<String, dynamic>;
    return (r['messages'] as List).map((e) => ChatMessage.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  @override
  Future<ChatMessage> sendMessage(String matchId, String body, String clientMessageId) async => ChatMessage.fromJson(
      await _req('POST', '/matches/$matchId/messages', body: {'body': body, 'client_message_id': clientMessageId}) as Map<String, dynamic>);

  @override
  Future<void> markRead(String matchId, int upToId) async => _req('POST', '/matches/$matchId/read', body: {'up_to_id': upToId});

  @override
  void sendTyping(String matchId) => _ws?.sink.add(jsonEncode({'type': 'typing', 'match_id': matchId}));

  @override
  Future<void> unmatch(String matchId) async => _req('POST', '/matches/$matchId/unmatch');

  // ------------------------------------------------------------ safety
  @override
  Future<void> block(String userId) async => _req('POST', '/safety/block', body: {'user_id': userId});

  @override
  Future<void> report(String userId, String reason, String details, {bool alsoBlock = true}) async =>
      _req('POST', '/safety/report', body: {'user_id': userId, 'reason': reason, 'details': details, 'block': alsoBlock});

  // ------------------------------------------------------------ AI
  @override
  Future<AiInsights> aiInsights(String userId) async =>
      AiInsights.fromJson(await _req('POST', '/ai/insights/$userId') as Map<String, dynamic>);

  @override
  Future<List<String>> aiRephrase(String draft) async {
    final r = await _req('POST', '/ai/rephrase', body: {'draft': draft}) as Map<String, dynamic>;
    return (r['suggestions'] as List).map((e) => e.toString()).toList();
  }

  @override
  Future<List<String>> aiReflection() async {
    final r = await _req('GET', '/ai/reflection') as Map<String, dynamic>;
    return (r['reflections'] as List).map((e) => e.toString()).toList();
  }

  // ------------------------------------------------------------ billing
  @override
  Future<List<Product>> products() async {
    final r = await _req('GET', '/billing/products', auth: false) as Map<String, dynamic>;
    return (r['products'] as List).map((e) => Product.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  @override
  Future<void> verifyPurchase(String productId, String purchaseToken) async =>
      _req('POST', '/billing/verify', body: {'product_id': productId, 'purchase_token': purchaseToken});
}
