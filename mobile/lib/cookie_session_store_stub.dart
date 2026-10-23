import 'models.dart';
import 'session_store.dart';

// The web transport keeps its session in the server's HttpOnly cookie.
class CookieSessionStore extends SessionStore {
  @override
  Future<Session?> load() async => null;
  @override
  Future<void> save(Session session) async {}
  @override
  Future<void> clear() async {}
}
