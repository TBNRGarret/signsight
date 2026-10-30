import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';

AppController fixture(Future<http.Response> Function(http.Request) handler) {
  final c = AppController(
    SignSightApi(Uri.parse('https://example.com'), client: MockClient(handler)),
    MemorySessionStore(),
  )..user = const UserProfile('u', 'driver', 'user');
  c.draft =
      CaptureDraft(
          photo: const UploadedPhoto('image', 64, 64),
          bytes: Uint8List.fromList([1]),
          detections: const [
            Detection('d', 'P.102', 'Original label', .9, classId: 5),
            Detection('other', 'P.125', 'Other label', .8, classId: 3),
          ],
          selectedId: 'd',
        )
        ..previewReady = true
        ..confirmedLocation = const GeoPoint(10.7, 106.7)
        ..labelConfirmed = true;
  return c;
}

http.Response taxonomy() => http.Response(
  jsonEncode({
    'items': [
      {'new_id': 5, 'qcvn_code': 'P.102', 'name_vi': 'Original label'},
      {
        'new_id': 42,
        'qcvn_code': 'FIXTURE.42',
        'name_vi': 'Synthetic extension',
      },
    ],
  }),
  200,
);

void main() {
  test('history displays the proposed label while original detection stays available', () {
    final row = Contribution.fromJson({
      'id': 'o',
      'image_id': 'i',
      'status': 'pending',
      'proposed_class': 42,
      'proposed_qcvn_code': 'FIXTURE.42',
      'proposed_name_vi': 'Corrected label',
      'detection': {'qcvn_code': 'P.102', 'name_vi': 'Original label'},
    });
    expect(row.code, 'FIXTURE.42');
    expect(row.name, 'Corrected label');
  });
  test('correction requires a known catalog ID, reason and renewed confirmation before submission', () async {
    Map<String, dynamic>? submitted;
    final c = fixture((request) async {
      if (request.url.path.endsWith('/taxonomy')) return taxonomy();
      submitted = jsonDecode(request.body);
      return http.Response('[]', 201);
    });
    await c.loadCaptureTypes();
    c.proposeClass(42);
    expect(c.canSubmit, false);
    expect(c.draft!.labelConfirmed, false);
    c.confirmLabel(true);
    expect(c.canSubmit, false);
    c.setCorrectionReason('Corrected after checking the photo');
    c.confirmLabel(true);
    expect(c.canSubmit, true);
    final original = c.draft!.selected!;
    await c.submitContribution();
    final item = (submitted!['items'] as List).single;
    expect(item['proposed_class'], 42);
    expect(item['correction_reason'], 'Corrected after checking the photo');
    expect(original.classId, 5);
    expect(c.draft, isNull);
    c.dispose();
  });
  test(
    'correction survives draft storage but changing detection clears it',
    () async {
      final c = fixture((_) async => taxonomy());
      await c.loadCaptureTypes();
      c.proposeClass(42);
      c.setCorrectionReason('Photo reviewed');
      c.confirmLabel(true);
      final restored = CaptureDraft.fromJson(c.draft!.toJson());
      expect(restored.proposedClass, 42);
      expect(restored.correctionReason, 'Photo reviewed');
      expect(restored.selected!.classId, 5);
      c.proposeClass(999);
      expect(c.draft!.proposedClass, 42);
      c.selectDetection('other');
      expect(c.draft!.proposedClass, isNull);
      expect(c.draft!.correctionReason, '');
      expect(c.draft!.labelConfirmed, false);
      c.dispose();
    },
  );
  test(
    'catalog failure permits unchanged contributions and exposes a retry',
    () async {
      var fail = true;
      final c = fixture(
        (_) async =>
            fail ? http.Response('{"detail":"offline"}', 503) : taxonomy(),
      );
      await c.loadCaptureTypes();
      expect(c.captureTypesError, isNotNull);
      expect(c.canSubmit, true);
      fail = false;
      await c.loadCaptureTypes();
      expect(c.captureTypesError, isNull);
      expect(c.captureTypes.last.id, 42);
      c.dispose();
    },
  );
}
