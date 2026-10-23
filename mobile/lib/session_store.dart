import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

abstract class SessionStore {
  Future<Session?> load();
  Future<void> save(Session session);
  Future<void> clear();
  Future<bool> get mayRestore async => true;
  Stream<void> get changes => const Stream.empty();
}

class MemorySessionStore extends SessionStore {
  Session? value;
  @override
  Future<Session?> load() async => value;
  @override
  Future<void> save(Session session) async {
    value = session;
  }

  @override
  Future<void> clear() async {
    value = null;
  }
}

class SecureSessionStore extends SessionStore {
  SecureSessionStore({
    required String scope,
    this.storage = const FlutterSecureStorage(),
  }) : key = 'signsight.native-session:${base64Url.encode(utf8.encode(scope))}';
  final FlutterSecureStorage storage;
  final String key;
  @override
  Future<Session?> load() async {
    final raw = await storage.read(key: key);
    if (raw == null) return null;
    try {
      return Session.fromJson(jsonMap(jsonDecode(raw)));
    } catch (_) {
      await clear();
      return null;
    }
  }

  @override
  Future<void> save(Session session) =>
      storage.write(key: key, value: jsonEncode(session.toJson()));
  @override
  Future<void> clear() => storage.delete(key: key);
}
