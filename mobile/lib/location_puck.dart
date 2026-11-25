import 'dart:math' as math;

import 'driving_tracker.dart';
import 'models.dart';

/// Geographic accuracy geometry stays correct as the map zoom changes.
Map<String, dynamic> locationGeoJson(LocationFix? fix, {required bool stale}) {
  final features = <Map<String, dynamic>>[];
  if (fix != null && fix.point.valid) {
    final color = stale ? '#64748b' : '#2563eb';
    Map<String, dynamic> feature(String kind, Map<String, dynamic> geometry) =>
        {
          'type': 'Feature',
          'properties': {'kind': kind, 'color': color},
          'geometry': geometry,
        };
    final origin = [fix.point.longitude, fix.point.latitude];
    features.add(feature('position', {'type': 'Point', 'coordinates': origin}));
    if (fix.accuracy != null && fix.accuracy!.isFinite && fix.accuracy! > 0) {
      final ring = [
        for (var i = 0; i <= 48; i++)
          _destination(fix.point, fix.accuracy!, i * 360 / 48),
      ];
      features.add(
        feature('accuracy', {
          'type': 'Polygon',
          'coordinates': [ring],
        }),
      );
    }
    if (!stale && fix.direction != null) {
      final heading = [
        origin,
        _destination(fix.point, 30, fix.direction! - 24),
        _destination(fix.point, 38, fix.direction!),
        _destination(fix.point, 30, fix.direction! + 24),
        origin,
      ];
      features.add(
        feature('heading', {
          'type': 'Polygon',
          'coordinates': [heading],
        }),
      );
    }
  }
  return {'type': 'FeatureCollection', 'features': features};
}

List<double> _destination(GeoPoint origin, double meters, double bearing) {
  final lat = origin.latitude * math.pi / 180,
      lon = origin.longitude * math.pi / 180;
  final angle = meters / 6371000, heading = bearing * math.pi / 180;
  final latitude = math.asin(
    math.sin(lat) * math.cos(angle) +
        math.cos(lat) * math.sin(angle) * math.cos(heading),
  );
  final longitude =
      lon +
      math.atan2(
        math.sin(heading) * math.sin(angle) * math.cos(lat),
        math.cos(angle) - math.sin(lat) * math.sin(latitude),
      );
  return [longitude * 180 / math.pi, latitude * 180 / math.pi];
}
