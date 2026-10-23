import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/models.dart';

void main() {
  test('native bearer is never sent by browser cookie transport', () async {
    final seen = <http.Request>[];
    final client = MockClient((r) async {
      seen.add(r);
      return http.Response('{"id":"u","username":"driver","role":"user"}', 200);
    });
    final native = SignSightApi(
      Uri.parse('https://example.com'),
      client: client,
    )..useToken('secret');
    await native.profile();
    expect(seen.last.headers['Authorization'], 'Bearer secret');
    final browser = SignSightApi(
      Uri.parse('https://example.com'),
      client: client,
      browser: true,
    )..useToken('secret');
    await browser.profile();
    expect(seen.last.headers.containsKey('Authorization'), false);
    expect(seen.last.headers['X-SignSight-Web'], '1');
  });
  test(
    'nearby parses nested sign and preserves server pagination total',
    () async {
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          expect(r.url.queryParameters['offset'], '25');
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'sign': {
                    'id': 's',
                    'qcvn_code': 'P.127 (50)',
                    'name_vi': 'Speed',
                    'latitude': 10.7,
                    'longitude': 106.7,
                  },
                  'distance_meters': 12,
                },
              ],
              'total': 80,
            }),
            200,
          );
        }),
      );
      final page = await api.nearby(10.7, 106.7, offset: 25);
      expect(page.items.single.id, 's');
      expect(page.total, 80);
      expect(page.items.single.distance, 12);
    },
  );
  test(
    'multipart upload sets image mime and media requests remain authenticated',
    () async {
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          expect(r.headers['Authorization'], 'Bearer native');
          if (r.url.path.endsWith('/content')) {
            return http.Response.bytes([1, 2, 3], 200);
          }
          expect(r.headers['content-type'], startsWith('multipart/form-data'));
          expect(
            utf8.decode(r.bodyBytes, allowMalformed: true),
            contains('image/jpeg'),
          );
          return http.Response('{"id":"p","width":40,"height":30}', 201);
        }),
      )..useToken('native');
      await api.upload(Uint8List.fromList([255, 216, 255, 224]), 'photo.jpg');
      expect(await api.photoContent('p'), [1, 2, 3]);
    },
  );
  test(
    'validation errors preserve status without echoing input values',
    () async {
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient(
          (r) async => http.Response(
            '{"detail":[{"msg":"Bad input","input":"secret"}]}',
            422,
          ),
        ),
      );
      try {
        await api.login('driver', 'secret');
        fail('expected error');
      } on ApiFailure catch (e) {
        expect(e.status, 422);
        expect(e.message, contains('Bad input'));
        expect(e.message, isNot(contains('secret')));
      }
    },
  );
  test('routing uses the backend navigation prefix and preserves complete geometry', () async {
    final api = SignSightApi(
      Uri.parse('https://example.com'),
      client: MockClient((r) async {
        expect(r.url.path, '/api/v1/navigation/route');
        return http.Response(
          '{"geometry":[{"latitude":10.7,"longitude":106.7},{"latitude":10.8,"longitude":106.8}],"signs":[],"distance_meters":1200,"duration_seconds":300}',
          200,
        );
      }),
    );
    final route = await api.route(
      const GeoPoint(10.7, 106.7),
      const GeoPoint(10.8, 106.8),
    );
    expect(route.geometry.length, 2);
    expect(route.distance, 1200);
  });
}
