import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:signsight_user/driving_tracker.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/location_puck.dart';
import 'package:signsight_user/sign_icons.dart';

import 'basemap_test.dart' show MapSurface;
import 'route_canvas_test.dart' show RouteController;

class LocationController extends RouteController {
  final sources = <Map<String, dynamic>>[];
  int additions = 0;
  @override
  dynamic noSuchMethod(Invocation call) {
    switch (call.memberName) {
      case #addGeoJsonSource:
        additions++;
        sources.add(call.positionalArguments[1] as Map<String, dynamic>);
        return Future<void>.value();
      case #setGeoJsonSource:
        sources.add(call.positionalArguments[1] as Map<String, dynamic>);
        return Future<void>.value();
      case #addFillLayer:
      case #addCircleLayer:
        return Future<void>.value();
    }
    return super.noSuchMethod(call);
  }
}

void main() {
  test('puck has actual accuracy geometry, direction and stale appearance', () {
    final fix = LocationFix(
      const GeoPoint(10.77, 106.7),
      DateTime.now().toUtc(),
      accuracy: 20,
      bearing: 90,
    );
    final features = locationGeoJson(fix, stale: false)['features'] as List;
    expect(features, hasLength(3));
    final position = features.firstWhere(
      (f) => f['properties']['kind'] == 'position',
    );
    expect(position['geometry']['coordinates'], [106.7, 10.77]);
    final accuracy = features.firstWhere(
      (f) => f['properties']['kind'] == 'accuracy',
    );
    final corner =
        (accuracy['geometry']['coordinates'] as List).first.first as List;
    expect(
      fix.point.distanceTo(
        GeoPoint((corner[1] as num).toDouble(), (corner[0] as num).toDouble()),
      ),
      closeTo(20, .1),
    );
    final stale = locationGeoJson(fix, stale: true)['features'] as List;
    expect(stale.any((f) => f['properties']['kind'] == 'heading'), false);
    expect(
      stale.first['properties']['color'],
      isNot(position['properties']['color']),
    );
    expect(locationGeoJson(null, stale: true)['features'], isEmpty);
  });

  testWidgets(
    'GPS updates its source and follow camera without rebuilding route or sign annotations',
    (tester) async {
      final factory = MapLibrePlatform.createInstance;
      MapLibrePlatform.createInstance = MapSurface.new;
      addTearDown(() => MapLibrePlatform.createInstance = factory);
      final native = LocationController();
      var dragged = 0;
      const route = [GeoPoint(10.77, 106.7), GeoPoint(10.79, 106.72)];
      Future<void> scene(
        double lat, {
        bool follow = true,
        bool stale = false,
      }) => tester.pumpWidget(
        MaterialApp(
          home: SignMap(
            scene: MapScene(
              center: route.first,
              route: route,
              routeFitRevision: 1,
              userLocation: LocationFix(
                GeoPoint(lat, 106.7),
                DateTime.now().toUtc(),
                accuracy: 8,
                bearing: 45,
              ),
              userLocationStale: stale,
              followUser: follow,
              onUserGesture: () => dragged++,
            ),
          ),
        ),
      );
      await tester.runAsync(() async {
        await renderRouteEndpoint('A', const Color(0xff15803d));
        await renderRouteEndpoint('B', const Color(0xffdc2626));
      });
      await scene(10.77);
      final map = tester.widget<MapLibreMap>(find.byType(MapLibreMap));
      map.onMapCreated!(native);
      map.onStyleLoadedCallback!();
      await tester.pumpAndSettle();
      final annotations = native.labels.length;
      expect(native.additions, 1);
      expect(native.cameras, hasLength(1));
      expect(native.lineClears, 1);
      await scene(10.771);
      await tester.pumpAndSettle();
      expect(native.additions, 1);
      expect(native.sources.length, greaterThan(1));
      expect(native.labels, hasLength(annotations));
      expect(native.lineClears, 1);
      expect(native.cameras, hasLength(2));
      await scene(10.772, follow: false);
      await tester.pumpAndSettle();
      expect(native.cameras, hasLength(2));
      await scene(10.773, stale: true);
      await tester.pumpAndSettle();
      expect(native.cameras, hasLength(2));
      await scene(10.774);
      await tester.pumpAndSettle();
      await tester.drag(
        find
            .ancestor(
              of: find.byType(MapLibreMap),
              matching: find.byType(Listener),
            )
            .first,
        const Offset(80, 0),
      );
      await tester.pumpAndSettle();
      expect(dragged, 1);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
