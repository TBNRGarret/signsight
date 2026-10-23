import 'dart:convert';

import 'package:web/web.dart' as web;

import 'models.dart';
import 'session_store.dart';

// Only a non-secret notification is shared with the existing web pages.
// Access tokens and passwords are never written to browser storage.
class CookieSessionStore extends SessionStore {
  static const key = 'signsight.auth-state';
  @override
  Future<Session?> load() async => null;
  String? _state() {
    try {
      final raw = web.window.localStorage.getItem(key);
      return raw == null ? null : (jsonDecode(raw) as Map)['state'] as String?;
    } catch (_) {
      return null;
    }
  }

  void _publish(String state) {
    try {
      web.window.localStorage.setItem(
        key,
        jsonEncode({
          'state': state,
          'nonce': DateTime.now().microsecondsSinceEpoch.toString(),
        }),
      );
    } catch (_) {
      /* Cookie sessions work even when storage is disabled. */
    }
  }

  @override
  Future<bool> get mayRestore async => _state() != 'out';
  @override
  Stream<void> get changes => web.EventStreamProviders.storageEvent
      .forTarget(web.window)
      .where((e) => e.key == key)
      .map((_) {});
  @override
  Future<void> save(Session session) async => _publish('in');
  @override
  Future<void> clear() async => _publish('out');
}
