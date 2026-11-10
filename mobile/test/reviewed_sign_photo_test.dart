import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/reviewed_sign_photo.dart';

void main() {
  test(
    'selected photo uses only the first local reviewed evidence path',
    () async {
      final calls = <String>[];
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          calls.add(r.url.path);
          expect(r.headers['Authorization'], 'Bearer fixture');
          return r.url.path.endsWith('/signs/s')
              ? http.Response(
                  jsonEncode({
                    'evidence': [
                      {'content_url': '/api/v1/images/one/content'},
                      {'content_url': '/api/v1/images/two/content'},
                    ],
                  }),
                  200,
                )
              : http.Response.bytes([1, 2, 3], 200);
        }),
      )..useToken('fixture');
      expect(await api.signPhoto('s'), [1, 2, 3]);
      expect(calls, ['/api/v1/signs/s', '/api/v1/images/one/content']);
    },
  );
  test('foreign evidence URLs are rejected and auth changes stop a stale content request', () async {
    final calls = <String>[];
    final pending = Completer<http.Response>();
    final api = SignSightApi(
      Uri.parse('https://example.com'),
      client: MockClient((r) async {
        calls.add(r.url.path);
        return pending.future;
      }),
    )..useToken('first');
    final result = api.signPhoto('s');
    api.useToken('second');
    pending.complete(
      http.Response(
        jsonEncode({
          'evidence': [
            {'content_url': '/api/v1/images/one/content'},
          ],
        }),
        200,
      ),
    );
    expect(await result, isNull);
    expect(calls.length, 1);
    final foreign = SignSightApi(
      Uri.parse('https://example.com'),
      client: MockClient(
        (r) async => http.Response(
          jsonEncode({
            'evidence': [
              {'content_url': 'https://outside.invalid/p'},
            ],
          }),
          200,
        ),
      ),
    );
    await expectLater(foreign.signPhoto('s'), throwsA(isA<FormatException>()));
  });
  testWidgets(
    'selected photo retries failures and preserves an explicit empty state',
    (tester) async {
      var fail = true, empty = false;
      final png = File('assets/signs/speed_limit_50.png').readAsBytesSync();
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          if (fail) return http.Response('{"detail":"offline"}', 503);
          if (r.url.path.endsWith('/signs/s')) {
            return http.Response(
              jsonEncode({
                'evidence': empty
                    ? []
                    : [
                        {'content_url': '/api/v1/images/one/content'},
                      ],
              }),
              200,
            );
          }
          return http.Response.bytes(png, 200);
        }),
      );
      Widget show(String session) => MaterialApp(
        home: Scaffold(
          body: ReviewedSignPhoto(api: api, signId: 's', sessionKey: session),
        ),
      );
      await tester.pumpWidget(show('first'));
      await tester.pumpAndSettle();
      expect(find.text('Thử lại'), findsOneWidget);
      fail = false;
      await tester.tap(find.text('Thử lại'));
      await tester.pumpAndSettle();
      expect(find.byType(Image), findsOneWidget);
      empty = true;
      await tester.pumpWidget(show('other'));
      await tester.pumpAndSettle();
      expect(find.text('Chưa có ảnh đã duyệt.'), findsOneWidget);
      expect(find.byType(Image), findsNothing);
    },
  );
  testWidgets(
    'a new selection immediately hides the previous photo while loading',
    (tester) async {
      final pending = Completer<http.Response>();
      final png = File('assets/signs/speed_limit_50.png').readAsBytesSync();
      final api = SignSightApi(
        Uri.parse('https://example.com'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/signs/second')) return pending.future;
          return r.url.path.contains('/signs/')
              ? http.Response(
                  jsonEncode({
                    'evidence': [
                      {'content_url': '/api/v1/images/one/content'},
                    ],
                  }),
                  200,
                )
              : http.Response.bytes(png, 200);
        }),
      );
      Widget show(String id) => MaterialApp(
        home: Scaffold(
          body: ReviewedSignPhoto(api: api, signId: id, sessionKey: 'u'),
        ),
      );
      await tester.pumpWidget(show('first'));
      await tester.pumpAndSettle();
      expect(find.byType(Image), findsOneWidget);
      await tester.pumpWidget(show('second'));
      await tester.pump();
      expect(find.byType(Image), findsNothing);
      pending.complete(http.Response('{"evidence":[]}', 200));
      await tester.pumpAndSettle();
      expect(find.text('Chưa có ảnh đã duyệt.'), findsOneWidget);
    },
  );
}
