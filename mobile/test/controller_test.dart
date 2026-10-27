import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';
import 'package:signsight_user/cookie_session_store.dart';

http.Response ok(Object v, [int s = 200]) => http.Response(
  jsonEncode(v),
  s,
  headers: {'content-type': 'application/json; charset=utf-8'},
);
const profile = {'id': 'u', 'username': 'driver', 'role': 'user'};
Map<String, dynamic> session([String role = 'user']) => {
  'access_token': 'native-token',
  'expires_at': '2099-01-01T00:00:00',
  'user': {...profile, 'role': role},
};
final image = Uint8List.fromList([255, 216, 255]);

class NotifyingStore extends MemorySessionStore {
  final events = StreamController<void>.broadcast();
  bool restore = true;
  @override
  Stream<void> get changes => events.stream;
  @override
  Future<bool> get mayRestore async => restore;
}

void main() {
  test(
    'native session restores and naive backend dates are treated as UTC',
    () async {
      final store = MemorySessionStore();
      await store.save(Session.fromJson(session()));
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient((r) async => ok(profile)),
        ),
        store,
      );
      await c.initialize();
      expect(c.user?.username, 'driver');
      expect(c.signedIn, true);
      expect((await store.load())!.expiresAt.isUtc, true);
    },
  );
  test(
    'offline restoration retains credentials for retry; 401 removes them',
    () async {
      final store = MemorySessionStore();
      await store.save(Session.fromJson(session()));
      var offline = true;
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient((r) async {
            if (offline) throw http.ClientException('offline');
            return ok({'detail': 'expired'}, 401);
          }),
        ),
        store,
      );
      await c.initialize();
      expect(await store.load(), isNotNull);
      expect(c.authError, isNotNull);
      offline = false;
      await c.initialize();
      expect(await store.load(), isNull);
      expect(c.user, isNull);
    },
  );
  test(
    'staff account has no user shell session or persisted credential',
    () async {
      final store = MemorySessionStore();
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient(
            (r) async => r.url.path.endsWith('logout')
                ? http.Response('', 204)
                : ok(session('admin')),
          ),
        ),
        store,
      );
      await c.login('owner', 'password');
      expect(c.user, isNull);
      expect(await store.load(), isNull);
      expect(c.authError, contains('quản trị'));
    },
  );
  test('retry detects saved photo without duplicate upload; label and pin are mandatory', () async {
    var uploads = 0, detects = 0, submits = 0;
    final c = AppController(
      SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/login')) return ok(session());
          if (r.url.path.endsWith('/images')) {
            uploads++;
            return ok({'id': 'p', 'width': 40, 'height': 30}, 201);
          }
          if (r.url.path.endsWith('/content')) {
            return http.Response.bytes(image, 200);
          }
          if (r.url.path.endsWith('/detect')) {
            detects++;
            if (detects == 1) return ok({'detail': 'Unavailable'}, 503);
            return ok({
              'detections': [
                {
                  'id': 'd',
                  'qcvn_code': 'P.102',
                  'name_vi': 'Cấm đi ngược chiều',
                  'confidence': .99,
                  'bbox': {'x1': 1, 'y1': 1, 'x2': 20, 'y2': 20},
                },
              ],
            });
          }
          if (r.url.path.endsWith('/observations') && r.method == 'POST') {
            submits++;
            expect(
              jsonDecode(r.body)['items'][0]['location_source'],
              'user_confirmed',
            );
            return ok([
              {
                'id': 'o',
                'status': 'pending',
                'image_id': 'p',
                'detection': {
                  'id': 'd',
                  'qcvn_code': 'P.102',
                  'name_vi': 'Biển',
                },
              },
            ], 201);
          }
          return ok({'items': [], 'total': 0});
        }),
      ),
      MemorySessionStore(),
    );
    await c.login('driver', 'password');
    await c.choosePhoto(image, 'photo.jpg');
    expect(uploads, 1);
    expect(c.draft?.photo?.id, 'p');
    expect(c.captureError, isNotNull);
    await c.retryDetection();
    expect(uploads, 1);
    expect(detects, 2);
    expect(c.canSubmit, false);
    c.confirmLabel(true);
    c.suggestLocation(const GeoPoint(10.7, 106.7));
    expect(c.canSubmit, false);
    c.confirmLocation(const GeoPoint(10.7, 106.7));
    expect(c.canSubmit, true);
    await c.submitContribution();
    expect(submits, 1);
    expect(c.draft, isNull);
    expect(c.captureMessage, contains('duyệt'));
  });
  test('late uploads after logout cannot restore private state', () async {
    final pending = Completer<http.Response>();
    final c = AppController(
      SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('login')) return ok(session());
          if (r.url.path.endsWith('logout')) return http.Response('', 204);
          if (r.url.path.endsWith('images')) return pending.future;
          return ok({'items': [], 'total': 0});
        }),
      ),
      MemorySessionStore(),
    );
    await c.login('driver', 'password');
    final task = c.choosePhoto(image, 'a.jpg');
    await Future<void>.delayed(Duration.zero);
    await c.logout();
    pending.complete(ok({'id': 'p', 'width': 40, 'height': 30}, 201));
    await task;
    expect(c.user, isNull);
    expect(c.draft, isNull);
    expect(c.nearbySigns, isEmpty);
  });
  test(
    'different detection does not inherit confirmed label or location',
    () async {
      final c = AppController(
        SignSightApi(Uri.parse('https://example.com')),
        MemorySessionStore(),
      );
      c.user = UserProfile.fromJson(profile);
      c.draft = CaptureDraft(
        photo: UploadedPhoto('p', 40, 30),
        bytes: image,
        detections: [
          Detection('a', 'P.102', 'A', .9),
          Detection('b', 'P.127', 'B', .8),
        ],
        selectedId: 'a',
      )..previewReady = true;
      c.confirmLabel(true);
      c.confirmLocation(const GeoPoint(10.7, 106.7));
      expect(c.canSubmit, true);
      c.selectDetection('b');
      expect(c.canSubmit, false);
      expect(c.draft!.confirmedLocation, isNull);
      expect(c.draft!.labelConfirmed, false);
    },
  );
  test(
    'expired saved credential clears a previously visible private session',
    () async {
      final store = MemorySessionStore();
      await store.save(
        Session('expired', DateTime.utc(2000), UserProfile.fromJson(profile)),
      );
      final c = AppController(
        SignSightApi(Uri.parse('https://example.com')),
        store,
      )..user = UserProfile.fromJson(profile);
      await c.initialize();
      expect(c.user, isNull);
      expect(c.authBusy, false);
      expect(await store.load(), isNull);
    },
  );
  test(
    'verifying a live session on resume does not strand pending detection',
    () async {
      final detection = Completer<http.Response>();
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient((r) async {
            if (r.url.path.endsWith('login')) return ok(session());
            if (r.url.path.endsWith('/me')) return ok(profile);
            if (r.url.path.endsWith('/images')) {
              return ok({'id': 'p', 'width': 40, 'height': 30}, 201);
            }
            if (r.url.path.endsWith('/content')) {
              return http.Response.bytes(image, 200);
            }
            if (r.url.path.endsWith('/detect')) return detection.future;
            return ok({});
          }),
        ),
        MemorySessionStore(),
      );
      await c.login('driver', 'password');
      final task = c.choosePhoto(image, 'a.jpg');
      await Future<void>.delayed(Duration.zero);
      await c.initialize();
      detection.complete(
        ok({
          'detections': [
            {
              'id': 'd',
              'qcvn_code': 'P.102',
              'name_vi': 'Biển',
              'confidence': .9,
            },
          ],
        }),
      );
      await task;
      expect(c.captureBusy, false);
      expect(c.draft!.detections.length, 1);
    },
  );
  test(
    'restoring a staff web cookie does not revoke the existing admin web login',
    () async {
      var revoked = false;
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        browser: true,
        client: MockClient((r) async {
          if (r.url.path.endsWith('logout')) {
            revoked = true;
            return http.Response('', 204);
          }
          return ok({...profile, 'role': 'admin'});
        }),
      );
      final c = AppController(api, MemorySessionStore());
      await c.initialize();
      expect(c.user, isNull);
      expect(revoked, false);
      expect(c.authBusy, false);
      expect(c.authError, contains('quản trị'));
    },
  );
  test(
    'retry fetches normalized preview before inference after content failure',
    () async {
      var previews = 0, uploads = 0, detects = 0;
      final normalized = Uint8List.fromList([1, 2, 3, 4]);
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient((r) async {
            if (r.url.path.endsWith('/login')) return ok(session());
            if (r.url.path.endsWith('/images')) {
              uploads++;
              return ok({'id': 'p', 'width': 40, 'height': 30}, 201);
            }
            if (r.url.path.endsWith('/content')) {
              previews++;
              if (previews == 1) return ok({'detail': 'offline'}, 503);
              return http.Response.bytes(normalized, 200);
            }
            if (r.url.path.endsWith('/detect')) {
              detects++;
              return ok({'detections': []});
            }
            return ok({});
          }),
        ),
        MemorySessionStore(),
      );
      await c.login('driver', 'password');
      await c.choosePhoto(image, 'photo.jpg');
      await c.retryDetection();
      expect(uploads, 1);
      expect(previews, 2);
      expect(detects, 1);
      expect(c.draft!.bytes, normalized);
    },
  );
  test('cross-tab sign out immediately removes private app state', () async {
    final store = NotifyingStore();
    final c = AppController(
      SignSightApi(Uri.parse('https://example.com'), browser: true),
      store,
    );
    c.user = UserProfile.fromJson(profile);
    c.draft = CaptureDraft(photo: UploadedPhoto('p', 40, 30), bytes: image);
    store.restore = false;
    store.events.add(null);
    await Future<void>.delayed(Duration.zero);
    expect(c.user, isNull);
    expect(c.draft, isNull);
    expect(c.authBusy, false);
    c.dispose();
    await store.events.close();
  });
  test('browser session store does not retain access tokens', () async {
    final store = CookieSessionStore();
    await store.save(Session.fromJson(session()));
    expect(await store.load(), isNull);
  });
  test('a new guest is not told that an existing session expired', () async {
    final c = AppController(
      SignSightApi(
        Uri.parse('https://example.com'),
        browser: true,
        client: MockClient(
          (r) async => ok({'detail': 'Not authenticated'}, 401),
        ),
      ),
      CookieSessionStore(),
    );
    await c.initialize();
    expect(c.signedIn, false);
    expect(c.authError, isNull);
  });
}
