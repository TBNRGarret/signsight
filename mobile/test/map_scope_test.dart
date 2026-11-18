import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';

const near = Sign('near', 'P.102', 'Near', GeoPoint(10.777, 106.701));
const along = Sign('along', 'P.102', 'Along route', GeoPoint(10.8, 106.701));
const far = Sign('far', 'P.102', 'Far off route', GeoPoint(11, 107));

void main() {
  testWidgets(
    'markers keep nearby OR route, deduplicate and omit far selected signs',
    (tester) async {
      final c =
          AppController(
              SignSightApi(
                Uri.parse('https://example.invalid'),
                client: MockClient(
                  (_) async => http.Response('{"items":[],"total":0}', 200),
                ),
              ),
              MemorySessionStore(),
            )
            ..user = const UserProfile('u', 'driver', 'user')
            ..nearbySigns = [near, along]
            ..route = const DrivingRoute(
              [GeoPoint(10.777, 106.701), GeoPoint(10.8, 106.701)],
              [near, along],
              3000,
              300,
            )
            ..selectedSign = far;
      MapScene? rendered;
      await tester.pumpWidget(
        SignSightApp(
          controller: c,
          mapBuilder: (_, scene) {
            rendered = scene;
            return const SizedBox.expand();
          },
        ),
      );
      await tester.pumpAndSettle();
      expect(
        rendered!.signs.map((s) => s.id),
        unorderedEquals(['near', 'along']),
      );
      expect(rendered!.selectedSignId, isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    },
  );

  testWidgets(
    'a route does not hide nearby signs that are outside its corridor',
    (tester) async {
      final c =
          AppController(
              SignSightApi(Uri.parse('https://example.invalid')),
              MemorySessionStore(),
            )
            ..user = const UserProfile('u', 'driver', 'user')
            ..nearbySigns = [near]
            ..route = const DrivingRoute(
              [GeoPoint(10.78, 106.71), GeoPoint(10.8, 106.71)],
              [along],
              3000,
              300,
            );
      MapScene? rendered;
      await tester.pumpWidget(
        SignSightApp(
          controller: c,
          mapBuilder: (_, scene) {
            rendered = scene;
            return const SizedBox.expand();
          },
        ),
      );
      await tester.pumpAndSettle();
      expect(
        rendered!.signs.map((s) => s.id),
        unorderedEquals(['near', 'along']),
      );
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    },
  );

  testWidgets(
    'without a route, far stale data and a selected sign cannot bypass the radius',
    (tester) async {
      final c =
          AppController(
              SignSightApi(Uri.parse('https://example.invalid')),
              MemorySessionStore(),
            )
            ..user = const UserProfile('u', 'driver', 'user')
            ..nearbySigns = [near, far]
            ..selectedSign = far;
      MapScene? rendered;
      await tester.pumpWidget(
        SignSightApp(
          controller: c,
          mapBuilder: (_, scene) {
            rendered = scene;
            return const SizedBox.expand();
          },
        ),
      );
      await tester.pumpAndSettle();
      expect(rendered!.signs.map((s) => s.id), ['near']);
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    },
  );
}
