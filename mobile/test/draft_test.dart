import 'dart:typed_data';
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/draft_store.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';
import 'package:signsight_user/device_services.dart';

void main() {
  test(
    'recovered Android photo survives an offline upload for its owner',
    () async {
      final drafts = MemoryDraftStore();
      await drafts.save('picker', {'owner': 'u'});
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient(
            (_) async => throw http.ClientException('offline'),
          ),
        ),
        MemorySessionStore(),
        drafts: drafts,
      )..user = const UserProfile('u', 'driver', 'user');
      await c.recoverPhoto(
        () async => PickedPhoto(Uint8List.fromList([1, 2, 3]), 'recovered.jpg'),
      );
      await c.flushDraft();
      expect(c.draft!.name, 'recovered.jpg');
      expect(c.draft!.photo, isNull);
      expect(CaptureDraft.fromJson((await drafts.load('u'))!).bytes, [1, 2, 3]);
      expect(await drafts.load('picker'), isNull);
    },
  );
  test(
    'picker storage failure is reported and logout still clears memory',
    () async {
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient((_) async => http.Response('{}', 200)),
        ),
        MemorySessionStore(),
        drafts: FailingDraftStore(),
      )..user = const UserProfile('u', 'driver', 'user');
      var opened = false;
      await c.pickPhoto(() async {
        opened = true;
        return null;
      });
      expect(opened, false);
      expect(c.captureError, contains('nháp'));
      await c.logout();
      await c.flushDraft();
      expect(c.signedIn, false);
    },
  );
  test(
    'photo returned after logout cannot become another account draft',
    () async {
      final drafts = MemoryDraftStore();
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient((_) async => http.Response('{}', 200)),
        ),
        MemorySessionStore(),
        drafts: drafts,
      )..user = const UserProfile('u', 'driver', 'user');
      final pending = Completer<PickedPhoto?>();
      final opened = Completer<void>();
      final picking = c.pickPhoto(() {
        opened.complete();
        return pending.future;
      });
      await opened.future;
      await c.logout();
      c.user = const UserProfile('other', 'other', 'user');
      pending.complete(PickedPhoto(Uint8List.fromList([1]), 'private.jpg'));
      await picking;
      await c.flushDraft();
      expect(c.draft, isNull);
      expect(await drafts.load('picker'), isNull);
    },
  );
  test(
    'Android lost photo is recovered only for the account that opened picker',
    () async {
      final drafts = MemoryDraftStore();
      await drafts.save('picker', {'owner': 'other'});
      var reads = 0;
      final c = AppController(
        SignSightApi(Uri.parse('https://example.com')),
        MemorySessionStore(),
        drafts: drafts,
      )..user = const UserProfile('u', 'driver', 'user');
      await c.recoverPhoto(() async {
        reads++;
        return PickedPhoto(Uint8List.fromList([1]), 'a.jpg');
      });
      expect(reads, 0);
      expect(c.draft, isNull);
    },
  );
  test('offline capture is retained across restart and can retry its original photo', () async {
    final drafts = MemoryDraftStore();
    final sessions = MemorySessionStore();
    await sessions.save(
      Session('token', _future, const UserProfile('u', 'driver', 'user')),
    );
    final first = AppController(
      SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/me')) {
            return http.Response(
              '{"id":"u","username":"driver","role":"user"}',
              200,
            );
          }
          throw http.ClientException('offline');
        }),
      ),
      sessions,
      drafts: drafts,
    );
    await first.initialize();
    await first.choosePhoto(Uint8List.fromList([255, 216, 255]), 'road.jpg');
    await first.flushDraft();
    expect(first.draft, isNotNull);
    final next = AppController(
      SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/me')) {
            return http.Response(
              '{"id":"u","username":"driver","role":"user"}',
              200,
            );
          }
          if (r.url.path.endsWith('/images')) {
            return http.Response('{"id":"p","width":40,"height":30}', 201);
          }
          if (r.url.path.endsWith('/content')) {
            return http.Response.bytes([255, 216, 255], 200);
          }
          return http.Response('{"detections":[]}', 200);
        }),
      ),
      sessions,
      drafts: drafts,
    );
    await next.initialize();
    expect(next.draft!.name, 'road.jpg');
    await next.retryDetection();
    expect(next.draft!.photo!.id, 'p');
    await next.logout();
    await next.flushDraft();
    expect(await drafts.load('u'), isNull);
  });

  test('draft restore never exposes a different user photo', () async {
    final drafts = MemoryDraftStore();
    await drafts.save(
      'other',
      CaptureDraft(
        photo: null,
        bytes: Uint8List.fromList([1, 2, 3]),
        name: 'private.jpg',
      ).toJson(),
    );
    final sessions = MemorySessionStore();
    await sessions.save(
      Session('token', _future, const UserProfile('u', 'driver', 'user')),
    );
    final c = AppController(
      SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient(
          (_) async => http.Response(
            '{"id":"u","username":"driver","role":"user"}',
            200,
          ),
        ),
      ),
      sessions,
      drafts: drafts,
    );
    await c.initialize();
    expect(c.draft, isNull);
  });
}

final _future = DateTime.utc(2099);

class FailingDraftStore extends MemoryDraftStore {
  @override
  Future<void> save(String owner, Map<String, dynamic> value) async =>
      throw StateError('disk full');
  @override
  Future<void> clear(String owner) async =>
      throw StateError('disk unavailable');
}
