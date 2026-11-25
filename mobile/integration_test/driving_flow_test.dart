// Native MapLibre renderer, synthetic API/GPS; never touches a personal runtime.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:integration_test/integration_test.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/device_services.dart';
import 'package:signsight_user/driving_tracker.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';

import 'user_flow_test.dart' show waitFor, reviewFrame;

class DrivingDevice extends DeviceServices {
  int cancellations = 0;
  late final fixes = StreamController<LocationFix>.broadcast(
    onCancel: () => cancellations++,
  );
  @override
  Stream<LocationFix> watchLocation() => fixes.stream;
  @override
  Future<PickedPhoto?> recoverPhoto() async => null;
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('native GPS layers, route scope, browse/recenter and end', (
    tester,
  ) async {
    MapLibrePlatform? surface;
    final factory = MapLibrePlatform.createInstance;
    MapLibrePlatform.createInstance = () => surface = factory();
    addTearDown(() => MapLibrePlatform.createInstance = factory);
    const origin = GeoPoint(10.7769, 106.7009), end = GeoPoint(10.78, 106.71);
    const destination = Place('fixture', 'Điểm đến thử nghiệm', end);
    final geometry = [origin.toJson(), end.toJson()];
    final c = AppController(
      SignSightApi(
        Uri.parse('https://example.invalid'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/navigation/route')) {
            return http.Response(
              jsonEncode({
                'geometry': geometry,
                'signs': [],
                'distance_meters': 1200,
                'duration_seconds': 180,
              }),
              200,
            );
          }
          if (r.url.path.endsWith('/route-signs')) {
            return http.Response('{"signs":[]}', 200);
          }
          return http.Response('{"items":[],"total":0}', 200);
        }),
      ),
      MemorySessionStore(),
    )..user = const UserProfile('fixture', 'native_driver', 'user');
    await c.routeTo(destination);
    final devices = DrivingDevice();
    MapScene? scene;
    await tester.pumpWidget(
      SignSightApp(
        controller: c,
        devices: devices,
        mapBuilder: (_, current) {
          scene = current;
          return SignMap(
            scene: current,
            styleString: jsonEncode({
              'version': 8,
              'sources': {},
              'layers': [
                {
                  'id': 'background',
                  'type': 'background',
                  'paint': {'background-color': '#e8eee6'},
                },
              ],
            }),
          );
        },
      ),
    );
    await tester.pump(const Duration(seconds: 2));
    await tester.tap(find.text('Bắt đầu'));
    await tester.pump();
    devices.fixes.add(
      LocationFix(origin, DateTime.now().toUtc(), accuracy: 8, bearing: 60),
    );
    await waitFor(tester, () => scene?.followUser == true);
    await tester.pump(const Duration(seconds: 2));
    const moved = GeoPoint(10.7772, 106.7015);
    devices.fixes.add(
      LocationFix(moved, DateTime.now().toUtc(), accuracy: 6, bearing: 60),
    );
    await waitFor(
      tester,
      () => scene?.userLocation?.point.latitude == moved.latitude,
    );
    await tester.pump(const Duration(seconds: 1));
    // Query the rendered layer; getStyle() may expose the original style JSON.
    List dots = [];
    for (var i = 0; i < 20 && dots.isEmpty; i++) {
      await tester.pump(const Duration(milliseconds: 250));
      dots = await surface!.queryRenderedFeaturesInRect(
        const Rect.fromLTWH(0, 0, 2000, 4000),
        ['user-location-dot'],
        null,
      );
    }
    expect(find.text('Không thể cập nhật bản đồ. Thử tải lại.'), findsNothing);
    expect(dots, isNotEmpty);
    await reviewFrame(tester, 'native-tracking');
    await tester.drag(find.byType(MapLibreMap), const Offset(70, 60));
    await waitFor(tester, () => scene?.followUser == false);
    expect(find.text('Theo dõi lại'), findsOneWidget);
    await tester.tap(find.text('Theo dõi lại'));
    await waitFor(tester, () => scene?.followUser == true);
    await c.changeMapScope(radius: 1000, corridor: 100);
    await tester.pump(const Duration(seconds: 1));
    expect(c.routeDestination?.id, destination.id);
    expect(scene!.route, hasLength(2));
    expect(find.text('Không thể cập nhật bản đồ. Thử tải lại.'), findsNothing);
    await tester.tap(find.text('Kết thúc'));
    await tester.pump(const Duration(seconds: 1));
    expect(devices.cancellations, 1);
    expect(scene!.followUser, false);
    expect(c.route, isNotNull);
    await tester.pumpWidget(const SizedBox.shrink());
    c.dispose();
    unawaited(devices.fixes.close());
  });
}
