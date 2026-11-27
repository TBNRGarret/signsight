import 'package:flutter_test/flutter_test.dart';
import 'package:signsight_user/driving_presentation.dart';
import 'package:signsight_user/driving_tracker.dart';
import 'package:signsight_user/models.dart';

void main() {
  const route = [GeoPoint(0, 0), GeoPoint(0, .01), GeoPoint(.01, .01)];
  test('progress splits a bent route and distances signs along the route', () {
    final progress = projectRoute(route, const GeoPoint(.005, .01))!;
    expect(progress.distanceAlong, closeTo(1667.9, 1));
    expect(progress.remainingMeters, closeTo(556, 1));
    expect(progress.completed.last.latitude, closeTo(.005, .000001));
    expect(progress.remaining.first.latitude, closeTo(.005, .000001));
    expect(progress.onRoute(8), true);
    final signs = [
      Sign('passed', 'P.102', 'Passed', route.first, distance: 1000),
      Sign('next', 'P.127', 'Next', route.last, distance: 1900),
      Sign('later', 'P.127', 'Later', route.last, distance: 2100),
      Sign('missing', 'P.127', 'No distance', route.last),
      Sign('invalid', 'P.127', 'Invalid', route.last, distance: double.nan),
      Sign(
        'removed',
        'P.127',
        'Removed',
        route.last,
        distance: 1800,
        status: 'removed',
      ),
    ];
    final next = progress.upcoming(signs)!;
    expect(next.sign.id, 'next');
    expect(next.meters, closeTo(232.1, 1));
    expect(progress.upcoming(signs, maxAhead: 100), isNull);
    final geo = routeProgressGeoJson(progress)['features'] as List;
    expect(geo.map((f) => f['properties']['part']), ['completed', 'remaining']);
  });
  test(
    'projection handles zero segments, dateline and crossing continuity',
    () {
      expect(projectRoute([], const GeoPoint(0, 0)), isNull);
      expect(projectRoute([route.first, route.first], route.first), isNull);
      final date = projectRoute(const [
        GeoPoint(0, 179.99),
        GeoPoint(0, -179.99),
      ], const GeoPoint(0, 180))!;
      expect(date.distanceAlong, closeTo(1112, 1));
      expect(date.crossTrackMeters, lessThan(1));
      final loop = [
        route.first,
        route[1],
        route[2],
        const GeoPoint(.01, 0),
        route.first,
        const GeoPoint(-.01, 0),
      ];
      expect(projectRoute(loop, route.first)!.distanceAlong, 0);
      expect(
        projectRoute(loop, route.first, previousDistance: 4400)!.distanceAlong,
        greaterThan(4400),
      );
      expect(
        projectRoute(route, const GeoPoint(.005, .015))!.onRoute(8),
        false,
      );
    },
  );
  test(
    'camera dampens rotation across north and zooms out at driving speeds',
    () {
      final motion = DrivingCameraMotion();
      final time = DateTime.utc(2026, 11, 27);
      final first = motion.update(
        LocationFix(route.first, time, bearing: 359, speed: 5),
      );
      final next = motion.update(
        LocationFix(
          const GeoPoint(0, .0001),
          time.add(const Duration(seconds: 1)),
          bearing: 1,
          speed: 30,
        ),
      );
      expect(next.bearing > 350 || next.bearing < 10, true);
      expect(next.zoom, lessThan(first.zoom));
      expect(next.zoom, greaterThanOrEqualTo(15.9));
      final stopped = motion.update(
        LocationFix(
          route.first,
          time.add(const Duration(seconds: 2)),
          bearing: 180,
          speed: 0,
        ),
      );
      expect(stopped.bearing, next.bearing);
      final north = motion.update(
        LocationFix(
          route.first,
          time.add(const Duration(seconds: 3)),
          bearing: 90,
          speed: 10,
        ),
        headingUp: false,
      );
      expect(north.bearing, 0);
      expect(north.tilt, 0);
      motion.reset();
      final reset = motion.update(
        LocationFix(
          route.last,
          time.add(const Duration(seconds: 4)),
          bearing: 90,
          speed: 10,
        ),
      );
      expect(reset.bearing, 90);
      expect(reset.target.distanceTo(route.last), greaterThan(10));
    },
  );
}
