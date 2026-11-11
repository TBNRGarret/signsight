import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/draft_store.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/native_draft_io.dart';
import 'package:signsight_user/session_store.dart';

import 'controller_test.dart' show ok, image, profile, session;

class RecoveryServer {
  final uploads = <http.Request>[];
  final submissions = <http.Request>[];
  bool loseUpload = false, loseSubmission = false;
  Completer<http.Response>? delayedSubmission;
  Future<http.Response> call(http.Request r) async {
    if (r.url.path.endsWith('/login')) return ok(session());
    if (r.url.path.endsWith('/auth/me')) return ok(profile);
    if (r.url.path.endsWith('/logout')) return http.Response('', 204);
    if (r.url.path.endsWith('/images')) {
      uploads.add(r);
      if (loseUpload) {
        loseUpload = false;
        throw http.ClientException('Response lost after commit');
      }
      return ok({'id': 'photo', 'width': 40, 'height': 30}, 201);
    }
    if (r.url.path.endsWith('/content')) return http.Response.bytes(image, 200);
    if (r.url.path.endsWith('/detect')) {
      return ok({
        'detections': [
          {
            'id': 'detected',
            'predicted_class': 0,
            'qcvn_code': 'P.102',
            'name_vi': 'No entry',
            'confidence': .99,
          },
        ],
      });
    }
    if (r.url.path.endsWith('/observations') && r.method == 'POST') {
      submissions.add(r);
      if (loseSubmission) {
        loseSubmission = false;
        throw http.ClientException('Response lost after commit');
      }
      if (delayedSubmission != null) return delayedSubmission!.future;
      return ok([], 201);
    }
    return ok({'items': [], 'total': 0});
  }
}

AppController controller(
  RecoveryServer server,
  MemorySessionStore sessions,
  DraftStore drafts,
) => AppController(
  SignSightApi(
    Uri.parse('https://example.com'),
    client: MockClient(server.call),
  ),
  sessions,
  drafts: drafts,
);

Future<void> prepare(AppController c) async {
  await c.login('driver', 'password');
  await c.choosePhoto(image, 'photo.jpg');
  c.confirmLabel(true);
  c.confirmLocation(const GeoPoint(10.78, 106.70));
}

class FullDraftStore extends MemoryDraftStore {
  @override
  Future<void> save(String owner, Map<String, dynamic> draft) async =>
      throw StateError('disk full');
}

void main() {
  testWidgets(
    'uncertain submission exposes one recovery action and locks edits',
    (tester) async {
      final server = RecoveryServer()..loseSubmission = true;
      final c = controller(server, MemorySessionStore(), MemoryDraftStore());
      await prepare(c);
      await c.submitContribution();
      c.draft!.bytes = base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lpQAAAAASUVORK5CYII=',
      );
      await tester.pumpWidget(
        SignSightApp(
          controller: c,
          mapBuilder: (_, _) => const SizedBox.expand(),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Đóng góp'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.byType(CheckboxListTile), 200);
      final checkbox = tester.widget<CheckboxListTile>(
        find.byType(CheckboxListTile),
      );
      expect(checkbox.onChanged, isNull);
      await tester.scrollUntilVisible(find.text('Kiểm tra kết quả gửi'), 200);
      expect(find.text('Kiểm tra kết quả gửi'), findsOneWidget);
      expect(find.text('Thử nhận diện lại'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    },
  );
  test(
    'lost upload response retries the same persisted key after restart',
    () async {
      final server = RecoveryServer()..loseUpload = true;
      final sessions = MemorySessionStore();
      final directory = await Directory.systemTemp.createTemp(
        'signsight-retry-upload-',
      );
      addTearDown(() => directory.delete(recursive: true));
      final drafts = FileDraftStore(
        'https://example.com',
        directory: directory,
      );
      final first = controller(server, sessions, drafts);
      await first.login('driver', 'password');
      await first.choosePhoto(image, 'photo.jpg');
      await first.flushDraft();
      expect(first.draft?.photo, isNull);
      final key = server.uploads.single.headers['Idempotency-Key'];
      expect(key, isNotEmpty);
      expect((await drafts.load('u'))?['upload_request_key'], key);
      first.dispose();
      final second = controller(
        server,
        sessions,
        FileDraftStore('https://example.com', directory: directory),
      );
      await second.initialize();
      await second.retryDetection();
      expect(server.uploads.last.headers['Idempotency-Key'], key);
      expect(second.draft?.photo?.id, 'photo');
      expect(second.draft?.selected?.id, 'detected');
      await second.flushDraft();
      second.dispose();
    },
  );

  test(
    'lost submit response restores and retries exact key and intent',
    () async {
      final server = RecoveryServer()..loseSubmission = true;
      final sessions = MemorySessionStore();
      final directory = await Directory.systemTemp.createTemp(
        'signsight-retry-submit-',
      );
      addTearDown(() => directory.delete(recursive: true));
      final drafts = FileDraftStore(
        'https://example.com',
        directory: directory,
      );
      final first = controller(server, sessions, drafts);
      await prepare(first);
      await first.submitContribution();
      await first.flushDraft();
      expect(first.draft, isNotNull);
      final request = server.submissions.single;
      final key = request.headers['Idempotency-Key'];
      expect(key, isNotEmpty);
      expect(first.captureError, contains('Chưa xác nhận'));
      // Unknown completion locks the original intent until retry or explicit discard.
      first.confirmLocation(const GeoPoint(11, 107));
      first.confirmLabel(false);
      await first.retryDetection();
      await first.flushDraft();
      first.dispose();
      final second = controller(
        server,
        sessions,
        FileDraftStore('https://example.com', directory: directory),
      );
      await second.initialize();
      expect(second.canSubmit, true);
      await second.submitContribution();
      expect(server.submissions.last.headers['Idempotency-Key'], key);
      expect(server.submissions.last.body, request.body);
      expect(second.draft, isNull);
      await second.flushDraft();
      expect(await drafts.load('u'), isNull);
      second.dispose();
    },
  );

  test(
    'failed durable save prevents upload rather than sending an unrecorded key',
    () async {
      final server = RecoveryServer();
      final c = controller(server, MemorySessionStore(), FullDraftStore());
      await c.login('driver', 'password');
      await c.choosePhoto(image, 'photo.jpg');
      expect(server.uploads, isEmpty);
      expect(c.captureError, contains('lưu'));
      c.dispose();
    },
  );

  test(
    'new photo has a new key and legacy drafts gain a durable key before retry',
    () async {
      final server = RecoveryServer();
      final sessions = MemorySessionStore(), drafts = MemoryDraftStore();
      final c = controller(server, sessions, drafts);
      await prepare(c);
      final firstKey = server.uploads.single.headers['Idempotency-Key'];
      expect(firstKey, isNotEmpty);
      c.discardDraft();
      await c.choosePhoto(image, 'other.jpg');
      expect(server.uploads.last.headers['Idempotency-Key'], isNot(firstKey));
      await c.flushDraft();
      final old = c.draft!.toJson()..remove('upload_request_key');
      old['photo'] = null;
      c.dispose();
      await drafts.save('u', old);
      final restored = controller(server, sessions, drafts);
      await restored.initialize();
      await restored.retryDetection();
      final newKey = server.uploads.last.headers['Idempotency-Key'];
      expect(newKey, isNotEmpty);
      expect((await drafts.load('u'))?['upload_request_key'], newKey);
      restored.dispose();
    },
  );

  test('old successful response cannot clear the new account draft', () async {
    final server = RecoveryServer()
      ..delayedSubmission = Completer<http.Response>();
    final c = controller(server, MemorySessionStore(), MemoryDraftStore());
    await prepare(c);
    final pending = c.submitContribution();
    while (server.submissions.isEmpty) {
      await Future<void>.delayed(Duration.zero);
    }
    await c.logout();
    await c.login('driver', 'password');
    await c.choosePhoto(image, 'new.jpg');
    final newDraft = c.draft;
    server.delayedSubmission!.complete(ok([], 201));
    await pending;
    expect(identical(c.draft, newDraft), true);
    c.dispose();
  });
}
