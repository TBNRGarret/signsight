import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:signsight_user/driving_tracker.dart';
import 'package:signsight_user/models.dart';

void main() {
  testWidgets(
    'temporary GPS loss retains the subscription and recovers on the next fix',
    (tester) async {
      var cancellations = 0;
      final stream = StreamController<LocationFix>(
        onCancel: () => cancellations++,
      );
      final tracker = DrivingTracker(() => stream.stream);
      final started = tracker.start();
      stream.addError(const PositionUpdateException('temporarily unavailable'));
      await tester.pump();
      expect(tracker.driving, true);
      expect(tracker.busy, true);
      expect(cancellations, 0);
      stream.add(
        LocationFix(
          const GeoPoint(10.77, 106.7),
          DateTime.now().toUtc(),
          accuracy: 8,
        ),
      );
      await tester.pump();
      expect(await started, true);
      stream.addError(const PositionUpdateException('temporarily unavailable'));
      await tester.pump();
      expect(tracker.fresh, false);
      expect(tracker.fix, isNotNull);
      expect(cancellations, 0);
      stream.add(
        LocationFix(
          const GeoPoint(10.771, 106.701),
          DateTime.now().toUtc(),
          accuracy: 6,
        ),
      );
      await tester.pump();
      expect(tracker.fresh, true);
      expect(tracker.error, isNull);
      expect(tracker.fix!.point.latitude, 10.771);
      tracker.dispose();
      unawaited(stream.close());
    },
  );
  testWidgets(
    'GPS moves independently of camera follow; pause/resume/stop cancel streams',
    (tester) async {
      var time = DateTime.utc(2026, 11, 25);
      final streams = <StreamController<LocationFix>>[];
      var cancellations = 0;
      final tracker = DrivingTracker(() {
        final stream = StreamController<LocationFix>(
          onCancel: () => cancellations++,
        );
        streams.add(stream);
        return stream.stream;
      }, now: () => time);
      final start = tracker.start();
      expect(tracker.busy, true);
      streams.last.add(
        LocationFix(
          const GeoPoint(10.77, 106.70),
          time,
          accuracy: 8,
          bearing: 45,
        ),
      );
      await tester.pump();
      expect(await start, true);
      expect(tracker.driving, true);
      expect(tracker.following, true);
      tracker.browse();
      time = time.add(const Duration(seconds: 2));
      streams.last.add(
        LocationFix(const GeoPoint(10.771, 106.701), time, accuracy: 9),
      );
      await tester.pump();
      expect(tracker.fix!.point.latitude, 10.771);
      expect(tracker.following, false);
      tracker.follow();
      expect(tracker.following, true);
      tracker.pause();
      await tester.pump();
      expect(tracker.paused, true);
      expect(tracker.driving, true);
      expect(cancellations, 1);
      expect(tracker.fresh, false);
      final resume = tracker.resume();
      expect(streams.length, 2);
      time = time.add(const Duration(seconds: 1));
      streams.last.add(
        LocationFix(const GeoPoint(10.772, 106.702), time, accuracy: 8),
      );
      await tester.pump();
      expect(await resume, true);
      expect(tracker.fresh, true);
      tracker.stop();
      await tester.pump();
      expect(tracker.driving, false);
      expect(tracker.fresh, false);
      expect(cancellations, 2);
      tracker.dispose();
      for (final stream in streams) {
        unawaited(stream.close());
      }
    },
    timeout: const Timeout(Duration(seconds: 15)),
  );

  testWidgets(
    'old inaccurate out-of-order fixes never drive the camera; stale GPS remains visible',
    (tester) async {
      var time = DateTime.utc(2026, 11, 25);
      final stream = StreamController<LocationFix>();
      final tracker = DrivingTracker(() => stream.stream, now: () => time);
      final start = tracker.start();
      stream.add(
        LocationFix(
          const GeoPoint(10, 106),
          time.subtract(const Duration(minutes: 1)),
          accuracy: 5,
        ),
      );
      stream.add(LocationFix(const GeoPoint(10, 106), time, accuracy: 400));
      stream.add(LocationFix(const GeoPoint(100, 106), time, accuracy: 5));
      await tester.pump();
      expect(tracker.fix, isNull);
      expect(tracker.busy, true);
      stream.add(LocationFix(const GeoPoint(10.77, 106.7), time, accuracy: 5));
      await tester.pump();
      expect(await start, true);
      stream.add(
        LocationFix(
          const GeoPoint(10.8, 106.8),
          time.subtract(const Duration(seconds: 1)),
          accuracy: 5,
        ),
      );
      await tester.pump();
      expect(tracker.fix!.point.latitude, 10.77);
      time = time.add(const Duration(seconds: 16));
      await tester.pump(const Duration(seconds: 16));
      expect(tracker.fresh, false);
      expect(tracker.fix, isNotNull);
      tracker.dispose();
      unawaited(stream.close());
    },
  );

  testWidgets('permission failure and first-fix timeout allow a clean retry', (
    tester,
  ) async {
    var attempts = 0;
    final tracker = DrivingTracker(
      () => ++attempts == 1
          ? Stream<LocationFix>.error(StateError('Location denied'))
          : const Stream<LocationFix>.empty(),
    );
    final denied = tracker.start();
    await tester.pump();
    expect(await denied, false);
    expect(tracker.error, isNotNull);
    expect(tracker.busy, false);
    final empty = tracker.start();
    await tester.pump();
    expect(await empty, false);
    expect(tracker.driving, false);
    tracker.dispose();
    final pending = StreamController<LocationFix>();
    final waiting = DrivingTracker(
      () => pending.stream,
      firstFixTimeout: const Duration(seconds: 2),
    );
    final timeout = waiting.start();
    await tester.pump(const Duration(seconds: 3));
    expect(await timeout, false);
    expect(waiting.busy, false);
    expect(waiting.error, isNotNull);
    waiting.dispose();
    unawaited(pending.close());
  });

  testWidgets('stopping while waiting ignores late fixes and resolves start', (
    tester,
  ) async {
    final source = StreamController<LocationFix>();
    final tracker = DrivingTracker(() => source.stream);
    final pending = tracker.start();
    tracker.stop();
    source.add(
      LocationFix(
        const GeoPoint(10.77, 106.7),
        DateTime.now().toUtc(),
        accuracy: 5,
      ),
    );
    await tester.pump();
    expect(await pending, false);
    expect(tracker.fix, isNull);
    expect(tracker.driving, false);
    tracker.dispose();
    unawaited(source.close());
  });
}
