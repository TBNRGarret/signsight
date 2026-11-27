import 'dart:math' as math;

import 'driving_tracker.dart';
import 'models.dart';

double _lon(double value) => (value + 180) % 360 - 180;

class UpcomingSign {
  const UpcomingSign(this.sign, this.meters);
  final Sign sign;
  final double meters;
}

/// Geometric projection only: never changes the device fix or proves lane use.
class RouteProgress {
  const RouteProgress(
    this.route,
    this.segment,
    this.fraction,
    this.distanceAlong,
    this.totalMeters,
    this.crossTrackMeters,
    this.projected,
  );
  final List<GeoPoint> route;
  final int segment;
  final double fraction, distanceAlong, totalMeters, crossTrackMeters;
  final GeoPoint projected;
  double get remainingMeters => math.max(0, totalMeters - distanceAlong);
  bool onRoute(double? accuracy) =>
      crossTrackMeters <= math.max(50, accuracy ?? 0);
  List<GeoPoint> get completed => [...route.take(segment + 1), projected];
  List<GeoPoint> get remaining => [projected, ...route.skip(segment + 1)];

  UpcomingSign? upcoming(List<Sign> signs, {double maxAhead = 1500}) {
    final ahead =
        signs
            .where(
              (s) =>
                  s.status == 'active' &&
                  s.distance != null &&
                  s.distance!.isFinite &&
                  s.distance! >= distanceAlong &&
                  s.distance! <= totalMeters + 1 &&
                  s.distance! - distanceAlong <= maxAhead,
            )
            .toList()
          ..sort((a, b) => a.distance!.compareTo(b.distance!));
    return ahead.isEmpty
        ? null
        : UpcomingSign(ahead.first, ahead.first.distance! - distanceAlong);
  }
}

RouteProgress? projectRoute(
  List<GeoPoint> route,
  GeoPoint point, {
  double? previousDistance,
}) {
  if (route.length < 2 || !point.valid || route.any((p) => !p.valid)) {
    return null;
  }
  final candidates = <RouteProgress>[];
  var travelled = 0.0;
  for (var i = 0; i < route.length - 1; i++) {
    final a = route[i], b = route[i + 1], length = a.distanceTo(b);
    if (length < .01) continue;
    final kx =
        math.pi /
        180 *
        6371000 *
        math.cos((a.latitude + b.latitude) / 2 * math.pi / 180);
    const ky = math.pi / 180 * 6371000;
    final dx = _lon(b.longitude - a.longitude) * kx,
        dy = (b.latitude - a.latitude) * ky;
    final px = _lon(point.longitude - a.longitude) * kx,
        py = (point.latitude - a.latitude) * ky;
    final t = ((px * dx + py * dy) / (dx * dx + dy * dy)).clamp(0.0, 1.0);
    final lateral = math.sqrt(
      math.pow(px - t * dx, 2) + math.pow(py - t * dy, 2),
    );
    final projected = GeoPoint(
      a.latitude + t * (b.latitude - a.latitude),
      _lon(a.longitude + t * _lon(b.longitude - a.longitude)),
    );
    candidates.add(
      RouteProgress(route, i, t, travelled + t * length, 0, lateral, projected),
    );
    travelled += length;
  }
  if (candidates.isEmpty) return null;
  final nearest = candidates.map((p) => p.crossTrackMeters).reduce(math.min);
  // At a crossing, retain the nearest previous branch among essentially tied
  // projections. This is continuity assistance, not map matching/rerouting.
  final tied = candidates
      .where(
        (p) =>
            p.crossTrackMeters <=
            nearest + (previousDistance == null ? .000001 : 2),
      )
      .toList();
  tied.sort(
    (a, b) => previousDistance == null
        ? a.distanceAlong.compareTo(b.distanceAlong)
        : (a.distanceAlong - previousDistance).abs().compareTo(
            (b.distanceAlong - previousDistance).abs(),
          ),
  );
  final best = tied.first;
  return RouteProgress(
    route,
    best.segment,
    best.fraction,
    best.distanceAlong,
    travelled,
    best.crossTrackMeters,
    best.projected,
  );
}

Map<String, dynamic> routeProgressGeoJson(RouteProgress? progress) => {
  'type': 'FeatureCollection',
  'features': [
    if (progress != null)
      for (final part in [
        if (progress.distanceAlong > .5) ('completed', progress.completed),
        if (progress.remainingMeters > .5) ('remaining', progress.remaining),
      ])
        {
          'type': 'Feature',
          'properties': {'part': part.$1},
          'geometry': {
            'type': 'LineString',
            'coordinates': [
              for (final p in part.$2) [p.longitude, p.latitude],
            ],
          },
        },
  ],
};

class DrivingCameraPose {
  const DrivingCameraPose(this.target, this.zoom, this.bearing, this.tilt);
  final GeoPoint target;
  final double zoom, bearing, tilt;
}

/// Smooth only camera presentation; route distance and puck retain raw GPS.
class DrivingCameraMotion {
  GeoPoint? _point;
  DateTime? _time;
  double? _bearing, _zoom;
  void reset() {
    _point = null;
    _time = null;
    _bearing = _zoom = null;
  }

  DrivingCameraPose update(LocationFix fix, {bool headingUp = true}) {
    final gap = _time == null
        ? 0
        : fix.timestamp.difference(_time!).inMilliseconds / 1000;
    final snap =
        _point == null || gap > 10 || _point!.distanceTo(fix.point) > 150;
    final alpha = (gap / 2).clamp(.35, .85);
    _point = snap
        ? fix.point
        : GeoPoint(
            _point!.latitude + alpha * (fix.point.latitude - _point!.latitude),
            _lon(
              _point!.longitude +
                  alpha * _lon(fix.point.longitude - _point!.longitude),
            ),
          );
    final speed = fix.usableSpeed;
    final direction = (speed == null || speed >= 2) ? fix.direction : null;
    if (direction != null) {
      _bearing = snap || _bearing == null
          ? direction
          : (_bearing! + .35 * _lon(direction - _bearing!) + 360) % 360;
    }
    final desiredZoom = (17.6 - (speed ?? 10) * .055).clamp(15.9, 17.6);
    _zoom = snap || _zoom == null
        ? desiredZoom
        : _zoom! + .25 * (desiredZoom - _zoom!);
    _time = fix.timestamp;
    final bearing = headingUp ? (_bearing ?? 0) : 0.0;
    // Look ahead only with a measured course; never invent a northward heading.
    final lookAhead = headingUp && _bearing != null
        ? 35 + (speed ?? 0) * 1.5
        : 0.0;
    final dy =
        lookAhead * math.cos(bearing * math.pi / 180) / 6371000 * 180 / math.pi;
    final cosLat = math
        .cos(_point!.latitude * math.pi / 180)
        .abs()
        .clamp(.01, 1);
    final dx =
        lookAhead *
        math.sin(bearing * math.pi / 180) /
        (6371000 * cosLat) *
        180 /
        math.pi;
    return DrivingCameraPose(
      GeoPoint(
        (_point!.latitude + dy).clamp(-90, 90),
        _lon(_point!.longitude + dx),
      ),
      _zoom!,
      bearing,
      headingUp ? 40 : 0,
    );
  }
}
