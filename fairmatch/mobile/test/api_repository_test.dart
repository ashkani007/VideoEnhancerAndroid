import 'dart:convert';

import 'package:fairmatch/data/api_repository.dart';
import 'package:fairmatch/data/repository.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _MemoryStorage extends FlutterSecureStorage {
  _MemoryStorage();
  final data = <String, String>{};

  @override
  Future<void> write({required String key, required String? value, AppleOptions? iOptions, AndroidOptions? aOptions,
      LinuxOptions? lOptions, WebOptions? webOptions, AppleOptions? mOptions, WindowsOptions? wOptions}) async {
    if (value == null) {
      data.remove(key);
    } else {
      data[key] = value;
    }
  }

  @override
  Future<String?> read({required String key, AppleOptions? iOptions, AndroidOptions? aOptions, LinuxOptions? lOptions,
          WebOptions? webOptions, AppleOptions? mOptions, WindowsOptions? wOptions}) async =>
      data[key];

  @override
  Future<void> delete({required String key, AppleOptions? iOptions, AndroidOptions? aOptions, LinuxOptions? lOptions,
          WebOptions? webOptions, AppleOptions? mOptions, WindowsOptions? wOptions}) async =>
      data.remove(key);
}

void main() {
  test('maps API error envelopes to ApiException codes', () async {
    final client = MockClient((req) async => http.Response(
        jsonEncode({'detail': {'code': 'daily_limit_reached', 'message': 'No more today'}}), 429));
    final repo = ApiRepository('http://api.test', client: client, storage: _MemoryStorage());
    expect(
      () => repo.select('p', 'c', 'k'),
      throwsA(isA<ApiException>().having((e) => e.code, 'code', 'daily_limit_reached').having((e) => e.status, 'status', 429)),
    );
  });

  test('sends the Idempotency-Key header when selecting', () async {
    String? key;
    final client = MockClient((req) async {
      key = req.headers['Idempotency-Key'];
      return http.Response(jsonEncode({'state': 'PENDING', 'status_text': 'Delivered', 'matched': false, 'selections': {'remaining': 4, 'daily_limit': 5}}), 200);
    });
    final repo = ApiRepository('http://api.test', client: client, storage: _MemoryStorage());
    final out = await repo.select('p', 'c', 'idem-123');
    expect(key, 'idem-123');
    expect(out.matched, isFalse);
    expect(out.selections.remaining, 4);
  });

  test('refreshes an expired access token once and retries the request', () async {
    var meCalls = 0;
    final storage = _MemoryStorage()..data['fm_refresh'] = 'old-refresh';
    final client = MockClient((req) async {
      if (req.url.path == '/auth/refresh') {
        return http.Response(jsonEncode({'access_token': 'new-access', 'refresh_token': 'new-refresh', 'user_id': 'u'}), 200);
      }
      if (req.url.path == '/likes') {
        meCalls++;
        if (req.headers['Authorization'] != 'Bearer new-access') return http.Response('{"detail":{"code":"invalid_token","message":"x"}}', 401);
        return http.Response(jsonEncode({'incoming_count': 0, 'can_see_incoming': false, 'incoming': [], 'outgoing': []}), 200);
      }
      return http.Response('', 404);
    });
    final repo = ApiRepository('http://api.test', client: client, storage: storage);
    // Simulate a stale session: refresh token known, access token expired.
    await storage.write(key: 'fm_refresh', value: 'old-refresh');
    final ok = await repo.restoreSession().catchError((_) => false);
    expect(ok, isTrue);
    final likes = await repo.likes();
    expect(likes.incomingCount, 0);
    expect(storage.data['fm_refresh'], 'new-refresh');
    expect(meCalls, 1);
  });

  test('network failures surface as offline errors', () async {
    final client = MockClient((req) async => throw http.ClientException('connection refused'));
    final repo = ApiRepository('http://api.test', client: client, storage: _MemoryStorage());
    expect(() => repo.matches(), throwsA(isA<ApiException>().having((e) => e.isOffline, 'offline', isTrue)));
  });
}
