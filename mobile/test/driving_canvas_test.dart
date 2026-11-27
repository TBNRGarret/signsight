import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/driving_presentation.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/sign_icons.dart';

import 'basemap_test.dart' show MapSurface;
import 'location_canvas_test.dart' show LocationController;

class JourneyController extends LocationController {
  final updates = <Map<String, dynamic>>[];
  Completer<void>? layerGate;
  @override
  CircleManager? get circleManager => null;
  @override
  dynamic noSuchMethod(Invocation call) {
    if ((call.memberName == #addGeoJsonSource ||
            call.memberName == #setGeoJsonSource) &&
        call.positionalArguments[0] == 'journey-progress') {
      updates.add(call.positionalArguments[1] as Map<String, dynamic>);
      return Future<void>.value();
    }
    if (call.memberName == #addLineLayer) {
      return layerGate?.future ?? Future<void>.value();
    }
    return super.noSuchMethod(call);
  }
}

Future<void> settleMap(WidgetTester tester) async {
  // Asset Futures warmed outside the fake clock need one real event-loop turn.
  await tester.runAsync(
    () => Future<void>.delayed(const Duration(milliseconds: 10)),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'stopping during overlay initialization never publishes the previous journey',
    (tester) async {
      final factory = MapLibrePlatform.createInstance;
      MapLibrePlatform.createInstance = MapSurface.new;
      addTearDown(() => MapLibrePlatform.createInstance = factory);
      const route = [GeoPoint(0, 0), GeoPoint(0, .01)];
      final native = JourneyController()..layerGate = Completer<void>();
      Future<void> scene(bool active) => tester.pumpWidget(
        MaterialApp(
          home: SignMap(
            scene: MapScene(
              center: route.first,
              route: route,
              routeFitRevision: 1,
              routeProgress: active
                  ? projectRoute(route, const GeoPoint(0, .003))
                  : null,
            ),
          ),
        ),
      );
      await tester.runAsync(() async {
        await SignIconCatalog.load();
        await renderRouteEndpoint('A', const Color(0xff15803d));
        await renderRouteEndpoint('B', const Color(0xffdc2626));
      });
      await scene(true);
      final map = tester.widget<MapLibreMap>(find.byType(MapLibreMap));
      map.onMapCreated!(native);
      map.onStyleLoadedCallback!();
      await settleMap(tester);
      expect(native.updates, isNotEmpty);
      await scene(false);
      native.layerGate!.complete();
      await settleMap(tester);
      expect(
        native.updates.every((data) => (data['features'] as List).isEmpty),
        true,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  testWidgets(
    'progress updates separate route source without rebuilding signs or fitting camera',
    (tester) async {
      final factory = MapLibrePlatform.createInstance;
      MapLibrePlatform.createInstance = MapSurface.new;
      addTearDown(() => MapLibrePlatform.createInstance = factory);
      const route = [GeoPoint(0, 0), GeoPoint(0, .01)];
      final native = JourneyController();
      Future<void> scene(double? lon) => tester.pumpWidget(
        MaterialApp(
          home: SignMap(
            scene: MapScene(
              center: route.first,
              route: route,
              routeFitRevision: 1,
              routeProgress: lon == null
                  ? null
                  : projectRoute(route, GeoPoint(0, lon)),
            ),
          ),
        ),
      );
      await tester.runAsync(() async {
        await SignIconCatalog.load();
        await renderRouteEndpoint('A', const Color(0xff15803d));
        await renderRouteEndpoint('B', const Color(0xffdc2626));
      });
      await scene(null);
      final map = tester.widget<MapLibreMap>(find.byType(MapLibreMap));
      map.onMapCreated!(native);
      map.onStyleLoadedCallback!();
      await settleMap(tester);
      final cameras = native.cameras.length, labels = native.labels.length;
      await scene(.003);
      await settleMap(tester);
      expect(native.updates.last['features'], hasLength(2));
      await scene(.004);
      await settleMap(tester);
      final completed = (native.updates.last['features'] as List).first;
      expect(
        completed['geometry']['coordinates'].last[0],
        closeTo(.004, 1e-10),
      );
      expect(completed['geometry']['coordinates'].last[1], 0.0);
      expect(native.lineClears, 1);
      expect(native.labels, hasLength(labels));
      expect(native.cameras, hasLength(cameras));
      await scene(null);
      await settleMap(tester);
      expect(native.updates.last['features'], isEmpty);
      expect(native.lineClears, 1);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
