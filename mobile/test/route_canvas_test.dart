import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/sign_icons.dart';

import 'basemap_test.dart' show MapSurface;

class RouteController implements MapLibreMapController {
  final recordedLines = <LineOptions>[];
  final dots = <CircleOptions>[];
  final labels = <SymbolOptions>[];
  final cameras = <CameraUpdate>[];
  int lineClears = 0;
  Completer<bool>? animation;
  final firstFit = Completer<void>();
  @override
  CameraPosition? cameraPosition = const CameraPosition(
    target: LatLng(10.8, 106.8),
    zoom: 13,
  );
  @override
  final onCircleTapped = ArgumentCallbacks<Circle>();
  @override
  final onSymbolTapped = ArgumentCallbacks<Symbol>();
  @override
  dynamic noSuchMethod(Invocation call) {
    switch (call.memberName) {
      case #clearLines:
        lineClears++;
        return Future<void>.value();
      case #clearCircles:
      case #clearSymbols:
      case #setSymbolIconAllowOverlap:
      case #addImage:
        return Future<void>.value();
      case #addLine:
        final v = call.positionalArguments[0] as LineOptions;
        recordedLines.add(v);
        return Future<Line>.value(Line('${recordedLines.length}', v));
      case #addCircle:
        final v = call.positionalArguments[0] as CircleOptions;
        dots.add(v);
        return Future<Circle>.value(Circle('${dots.length}', v));
      case #addSymbol:
        final v = call.positionalArguments[0] as SymbolOptions;
        labels.add(v);
        return Future<Symbol>.value(Symbol('${labels.length}', v));
      case #animateCamera:
        cameras.add(call.positionalArguments[0] as CameraUpdate);
        if (!firstFit.isCompleted) firstFit.complete();
        return animation?.future ?? Future<bool>.value(true);
    }
    return super.noSuchMethod(call);
  }
}

void main() {
  setUp(() {
    final factory = MapLibrePlatform.createInstance;
    MapLibrePlatform.createInstance = MapSurface.new;
    addTearDown(() => MapLibrePlatform.createInstance = factory);
  });
  testWidgets(
    'scope redraw preserves route strokes and does not steal the camera',
    (tester) async {
      final native = RouteController();
      Future<void> scene(int fit) async {
        await tester.pumpWidget(
          MaterialApp(
            home: SignMap(
              scene: MapScene(
                center: const GeoPoint(10.77, 106.7),
                route: [
                  const GeoPoint(10.77, 106.7),
                  const GeoPoint(10.79, 106.72),
                ],
                routeFitRevision: fit,
              ),
            ),
          ),
        );
      }

      await tester.runAsync(() async {
        await renderRouteEndpoint('A', const Color(0xff15803d));
        await renderRouteEndpoint('B', const Color(0xffdc2626));
      });
      await scene(1);
      final map = tester.widget<MapLibreMap>(find.byType(MapLibreMap));
      map.onMapCreated!(native);
      map.onStyleLoadedCallback!();
      await tester.pumpAndSettle();
      expect(native.recordedLines, hasLength(2));
      expect(
        native.labels.map((s) => s.iconImage),
        containsAll(['route-endpoint-A', 'route-endpoint-B']),
      );
      expect(
        native.dots.map((s) => s.geometry),
        containsAll([const LatLng(10.77, 106.7), const LatLng(10.79, 106.72)]),
      );
      expect(native.cameras, hasLength(1));
      await scene(1);
      await tester.pumpAndSettle();
      expect(native.lineClears, 1);
      expect(native.recordedLines, hasLength(2));
      expect(native.cameras, hasLength(1));
      // A scope/idle rebuild occurs while an explicit fit animation is in flight.
      native.animation = Completer<bool>();
      await scene(2);
      await tester.pump();
      expect(native.cameras, hasLength(2));
      await scene(2);
      await tester.pump();
      native.animation!.complete(true);
      await tester.pumpAndSettle();
      expect(
        native.cameras,
        hasLength(2),
        reason: 'An idle rebuild must not repeat a requested camera fit',
      );
      expect(native.recordedLines, hasLength(2));
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
