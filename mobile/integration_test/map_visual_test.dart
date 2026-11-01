// Real public basemap; all account, sign and route data stays synthetic/in-memory.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/device_services.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';

import 'user_flow_test.dart' show reviewFrame;

MapLibrePlatform? surface;

class NoDeviceCapture extends DeviceServices {
  @override
  Future<PickedPhoto?> recoverPhoto() async => null;
}

Future<void> settleTiles(WidgetTester tester) async {
  await tester.runAsync(
    () => Future<void>.delayed(const Duration(seconds: 12)),
  );
  await tester.pump(const Duration(seconds: 1));
  final raw = await surface?.getStyle();
  if (raw != null) {
    final style = jsonDecode(raw) as Map<String, dynamic>;
    final layers = (style['layers'] as List).cast<Map<String, dynamic>>();
    final label = layers
        .where((l) => l['id'] == 'highway-name-major')
        .firstOrNull;
    final features = await surface!.queryRenderedFeaturesInRect(
      const Rect.fromLTWH(0, 0, 1000, 2000),
      ['highway-name-major'],
      null,
    );
    debugPrint(
      'BASEMAP_DIAGNOSTIC:${jsonEncode({'glyphs': style['glyphs'], 'label': label, 'renderedRoadNames': features.length})}',
    );
  }
  expect(
    find.text('Chưa tải được bản đồ. Kiểm tra kết nối rồi thử lại.'),
    findsNothing,
  );
  expect(find.text('Không thể cập nhật bản đồ. Thử tải lại.'), findsNothing);
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'real vector basemap, live theme changes and evidence selection',
    (tester) async {
      const user = UserProfile('visual-user', 'map_visual_fixture', 'user');
      final factory = MapLibrePlatform.createInstance;
      MapLibrePlatform.createInstance = () => surface = factory();
      addTearDown(() => MapLibrePlatform.createInstance = factory);
      const sign = Sign(
        'visual-sign',
        'P.102',
        'Cấm đi ngược chiều',
        GeoPoint(10.7766, 106.7014),
      );
      final store = MemorySessionStore();
      await store.save(
        Session(
          'synthetic-token',
          DateTime.now().toUtc().add(const Duration(hours: 1)),
          user,
        ),
      );
      final api = SignSightApi(
        Uri.parse('https://example.invalid'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/auth/me')) {
            return http.Response(
              jsonEncode(user.toJson()),
              200,
              headers: {'content-type': 'application/json'},
            );
          }
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'sign': {
                    'id': sign.id,
                    'qcvn_code': sign.code,
                    'name_vi': sign.name,
                    ...sign.point.toJson(),
                    'status': 'active',
                    'verification_status': 'current',
                  },
                  'distance_meters': 40,
                },
              ],
              'total': 1,
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }),
      );
      final c = AppController(api, store)
        ..user = user
        ..nearbySigns = [sign]
        ..nearbyTotal = 1;
      await c.refreshNearby();
      expect(c.mapError, isNull);
      var baseline = true;
      Widget mapBuilder(BuildContext context, MapScene scene) => SignMap(
        scene: scene,
        styleString: baseline
            ? 'https://tiles.openfreemap.org/styles/liberty'
            : null,
      );
      SignSightApp app() => SignSightApp(
        controller: c,
        devices: NoDeviceCapture(),
        mapBuilder: mapBuilder,
      );
      await tester.pumpWidget(app());
      await settleTiles(tester);
      await reviewFrame(tester, 'map-baseline-day');
      final host = tester.state(find.byType(MapLibreMap));
      baseline = false;
      await tester.pumpWidget(app());
      await settleTiles(tester);
      expect(tester.state(find.byType(MapLibreMap)), same(host));
      expect(
        tester.widget<MapLibreMap>(find.byType(MapLibreMap)).styleString,
        'assets/maps/signsight-day.json',
      );
      await reviewFrame(tester, 'map-streets-day');
      c.selectSign(sign);
      await tester.pump(const Duration(seconds: 1));
      expect(find.text('Báo cáo / xác nhận'), findsOneWidget);
      await reviewFrame(tester, 'map-selected-day');
      c.selectSign(null);
      c.moveCenter(const GeoPoint(10.7740, 106.7102));
      await tester.pump(const Duration(seconds: 1));
      await settleTiles(tester);
      await reviewFrame(tester, 'map-river-day');
      await tester.tap(find.byTooltip('Tài khoản'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tối'));
      await tester.pump(const Duration(seconds: 1));
      await settleTiles(tester);
      expect(tester.state(find.byType(MapLibreMap)), same(host));
      expect(
        tester.widget<MapLibreMap>(find.byType(MapLibreMap)).styleString,
        'assets/maps/signsight-night.json',
      );
      await reviewFrame(tester, 'map-river-night');
      c.selectSign(sign);
      await tester.pump(const Duration(seconds: 1));
      await settleTiles(tester);
      await reviewFrame(tester, 'map-selected-night');
      debugPrint('SIGNSIGHT_VISUAL_PROFILE:dark-large');
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(seconds: 4)),
      );
      await tester.pump(const Duration(seconds: 1));
      await reviewFrame(tester, 'map-night-large');
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    },
  );
}
