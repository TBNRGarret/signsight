import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/session_store.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  for (final width in [360.0, 430.0, 1000.0]) {
    testWidgets(
      'compact user navigation at width $width keeps map visible without admin panels',
      (tester) async {
        tester.view.physicalSize = Size(width, 800);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final c = AppController(
          SignSightApi(Uri.parse('https://example.com')),
          MemorySessionStore(),
        );
        await tester.pumpWidget(
          SignSightApp(
            controller: c,
            mapBuilder: (context, scene) =>
                const ColoredBox(key: Key('map'), color: Colors.blueGrey),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('map')), findsOneWidget);
        expect(find.text('Quản trị'), findsNothing);
        expect(find.byType(NavigationBar), findsOneWidget);
        expect(find.byType(Card), findsNothing);
        expect(
          tester.getSize(find.byKey(const Key('map'))).height,
          greaterThan(450),
        );
        await tester.tap(find.text('Đóng góp').last);
        await tester.pumpAndSettle();
        expect(find.text('Đăng nhập để đóng góp'), findsOneWidget);
        expect(find.text('Duyệt đóng góp'), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );
  }
  testWidgets(
    'a record opened from history has a marker before nearby reloads',
    (tester) async {
      final c = AppController(
        SignSightApi(
          Uri.parse('https://example.com'),
          client: MockClient(
            (r) async => http.Response('{"items":[],"total":0}', 200),
          ),
        ),
        MemorySessionStore(),
      );
      c.user = const UserProfile('u', 'driver', 'user');
      MapScene? rendered;
      await tester.pumpWidget(
        SignSightApp(
          controller: c,
          mapBuilder: (context, scene) {
            rendered = scene;
            return const ColoredBox(color: Colors.blueGrey);
          },
        ),
      );
      c.selectSign(
        const Sign(
          'approved',
          'P.102',
          'Cấm đi ngược chiều',
          GeoPoint(10.8, 106.8),
        ),
      );
      await tester.pumpAndSettle();
      expect(rendered!.signs.map((s) => s.id), contains('approved'));
    },
  );
}
