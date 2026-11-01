import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';

class MapSurface extends MapLibrePlatform {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
  @override
  Widget buildView(
    Map<String, dynamic> creationParams,
    OnPlatformViewCreatedCallback onPlatformViewCreated,
    Set<Factory<OneSequenceGestureRecognizer>>? gestureRecognizers,
  ) => const SizedBox.expand();
}

void main() {
  setUp(() {
    final factory = MapLibrePlatform.createInstance;
    MapLibrePlatform.createInstance = MapSurface.new;
    addTearDown(() => MapLibrePlatform.createInstance = factory);
  });

  testWidgets(
    'basemap follows light and dark appearance without replacing the map host',
    (tester) async {
      Future<void> show(Brightness brightness) => tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(brightness: brightness),
          home: const SignMap(
            scene: MapScene(center: GeoPoint(10.7769, 106.7009)),
          ),
        ),
      );
      await show(Brightness.light);
      final original = tester.state(find.byType(MapLibreMap));
      expect(
        tester.widget<MapLibreMap>(find.byType(MapLibreMap)).styleString,
        'assets/maps/signsight-day.json',
      );
      await show(Brightness.dark);
      await tester.pumpAndSettle();
      expect(
        tester.widget<MapLibreMap>(find.byType(MapLibreMap)).styleString,
        'assets/maps/signsight-night.json',
      );
      expect(tester.state(find.byType(MapLibreMap)), same(original));
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets(
    'disposable or caller-supplied map style remains explicit in both themes',
    (tester) async {
      for (final brightness in Brightness.values) {
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData(brightness: brightness),
            home: const SignMap(
              scene: MapScene(center: GeoPoint(10.7, 106.7)),
              styleString: 'https://example.com/test-map.json',
            ),
          ),
        );
        expect(
          tester.widget<MapLibreMap>(find.byType(MapLibreMap)).styleString,
          'https://example.com/test-map.json',
        );
      }
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  test('bundled styles keep readable local labels, road context, and free vector sources', () {
    for (final name in ['day', 'night']) {
      final file = File('assets/maps/signsight-$name.json');
      expect(
        file.existsSync(),
        isTrue,
        reason: 'The $name basemap must ship with the app',
      );
      if (!file.existsSync()) continue;
      final style = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
      expect(style['version'], 8);
      final sources = style['sources'] as Map<String, dynamic>;
      expect(
        sources['openmaptiles']['url'],
        startsWith('https://tiles.openfreemap.org/'),
      );
      expect(sources['openmaptiles']['attribution'], contains('OpenStreetMap'));
      final layers = (style['layers'] as List).cast<Map<String, dynamic>>();
      expect(
        layers.any((l) => l['type'] == 'fill-extrusion'),
        isFalse,
        reason: 'Flat buildings keep road and sign evidence readable',
      );
      final water = layers.singleWhere((l) => l['id'] == 'water');
      final park = layers.singleWhere((l) => l['id'] == 'park');
      expect(water['paint']['fill-color'], isNot(park['paint']['fill-color']));
      final roadName = layers.singleWhere(
        (l) => l['id'] == 'highway-name-major',
      );
      expect(roadName['layout']['text-field'], [
        'coalesce',
        ['get', 'name:vi'],
        ['get', 'name'],
        ['get', 'name:latin'],
      ]);
      expect(roadName['paint']['text-halo-width'], greaterThanOrEqualTo(1.5));
    }
  });
}
