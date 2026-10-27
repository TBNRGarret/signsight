import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';

http.Response response(Object body, [int status = 200]) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);
const signJson = {
  'id': 's',
  'qcvn_code': 'P.102',
  'name_vi': 'Cấm đi ngược chiều',
  'latitude': 10.7,
  'longitude': 106.7,
  'verification_status': 'needs_confirmation',
};
const reportJson = {
  'id': 'r',
  'record_id': 's',
  'image_id': 'p',
  'action': 'confirm_existing',
  'status': 'pending',
  'comment': 'Biển vẫn còn',
  'review_comment': null,
};

void main() {
  test(
    'feedback uses evidence reports and paginates confirmation requests',
    () async {
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          if (r.method == 'POST') {
            expect(r.url.path, '/api/v1/signs/s/reports');
            expect(jsonDecode(r.body), {
              'action': 'confirm_existing',
              'image_id': 'p',
              'comment': 'Biển vẫn còn',
            });
            return response(reportJson, 201);
          }
          expect(r.url.path, '/api/v1/me/confirmation-requests');
          expect(r.url.queryParameters['offset'], '20');
          return response({
            'items': [signJson],
            'total': 21,
          });
        }),
      );
      final report = await api.report(
        's',
        ReportAction.confirmExisting,
        'p',
        'Biển vẫn còn',
      );
      expect(report.status, 'pending');
      final page = await api.confirmations(offset: 20);
      expect(page.items.single.needsConfirmation, true);
      expect(page.total, 21);
    },
  );

  test(
    'location correction sends only the explicitly selected coordinates',
    () async {
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          expect(jsonDecode(r.body), {
            'action': 'correct_location',
            'image_id': 'p',
            'comment': 'Dời vị trí biển',
            'latitude': 10.8,
            'longitude': 106.8,
          });
          return response({...reportJson, 'action': 'correct_location'}, 201);
        }),
      );
      await api.report(
        's',
        ReportAction.correctLocation,
        'p',
        'Dời vị trí biển',
        point: const GeoPoint(10.8, 106.8),
      );
    },
  );

  test('route uses the chosen corridor rather than a fixed 50 m', () async {
    final api = SignSightApi(
      Uri.parse('https://example.com'),
      client: MockClient((r) async {
        expect(jsonDecode(r.body)['buffer_meters'], 100);
        return response({
          'geometry': [],
          'signs': [],
          'distance_meters': 0,
          'duration_seconds': 0,
        });
      }),
    );
    await api.route(
      const GeoPoint(10.7, 106.7),
      const GeoPoint(10.8, 106.8),
      buffer: 100,
    );
  });

  test(
    'late feedback response after logout cannot restore private state',
    () async {
      final pending = Completer<http.Response>();
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient((r) async {
            if (r.url.path.endsWith('logout')) return http.Response('', 204);
            return pending.future;
          }),
        ),
        MemorySessionStore(),
      )..user = const UserProfile('u', 'driver', 'user');
      final task = c.loadReports();
      await Future<void>.delayed(Duration.zero);
      await c.logout();
      pending.complete(
        response({
          'items': [reportJson],
          'total': 1,
        }),
      );
      await task;
      expect(c.reports, isEmpty);
      expect(c.feedbackBusy, false);
    },
  );
}
