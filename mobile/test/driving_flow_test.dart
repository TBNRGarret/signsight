import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/device_services.dart';
import 'package:signsight_user/driving_tracker.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';

import 'route_scope_test.dart' show RouteHarness, destination, geometry;

class DrivingDevices extends DeviceServices {
  int cancelled = 0;
  late final positions = StreamController<LocationFix>.broadcast(
    onCancel: () => cancelled++,
  );
  @override
  Stream<LocationFix> watchLocation() => positions.stream;
  @override
  Future<PickedPhoto?> recoverPhoto() async => null;
}

void main() {
  testWidgets(
    'driving shows route progress and only upcoming signs; off-route freezes progress',
    (tester) async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      h.c.route = DrivingRoute(
        geometry,
        [
          Sign(
            'near',
            'P.127',
            'Biển phía trước đầu tiên',
            geometry.first,
            distance: 100,
          ),
          Sign(
            'next',
            'P.102',
            'Biển phía trước tiếp theo',
            geometry.last,
            distance: 800,
          ),
        ],
        1200,
        180,
      );
      final devices = DrivingDevices();
      MapScene? scene;
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        SignSightApp(
          controller: h.c,
          devices: devices,
          mapBuilder: (_, s) {
            scene = s;
            return const SizedBox.expand();
          },
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bắt đầu'));
      await tester.pump();
      final time = DateTime.now().toUtc();
      devices.positions.add(
        LocationFix(geometry.first, time, accuracy: 5, bearing: 60, speed: 12),
      );
      await tester.pumpAndSettle();
      expect(find.text('Biển phía trước đầu tiên'), findsOneWidget);
      expect(find.byKey(const ValueKey('upcoming-sign')), findsOneWidget);
      devices.positions.add(
        LocationFix(
          GeoPoint(
            (geometry.first.latitude + geometry.last.latitude) / 2,
            (geometry.first.longitude + geometry.last.longitude) / 2,
          ),
          time.add(const Duration(seconds: 1)),
          accuracy: 5,
          bearing: 60,
          speed: 12,
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Biển phía trước đầu tiên'), findsNothing);
      expect(find.text('Biển phía trước tiếp theo'), findsOneWidget);
      expect(scene!.routeProgress!.distanceAlong, greaterThan(400));
      expect(find.textContaining('Còn khoảng'), findsOneWidget);
      await tester.tap(find.byTooltip('Bắc ở trên'));
      await tester.pumpAndSettle();
      expect(scene!.headingUp, false);
      expect(scene!.followUser, true);
      final distance = scene!.routeProgress!.distanceAlong;
      await h.c.changeMapScope(radius: 1000, corridor: 100);
      await tester.pumpAndSettle();
      expect(scene!.routeProgress!.distanceAlong, closeTo(distance, 1));
      devices.positions.add(
        LocationFix(
          const GeoPoint(10.80, 106.75),
          time.add(const Duration(seconds: 2)),
          accuracy: 5,
          speed: 12,
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Bạn đang ngoài tuyến. Chưa tính lại tuyến.'),
        findsOneWidget,
      );
      expect(find.byKey(const ValueKey('upcoming-sign')), findsNothing);
      expect(scene!.routeProgress!.distanceAlong, closeTo(distance, 1));
      expect(tester.takeException(), isNull);
      await tester.tap(find.text('Kết thúc'));
      await tester.pumpAndSettle();
      expect(scene!.routeProgress, isNull);
      expect(h.c.route, isNotNull);
      await tester.pumpWidget(const SizedBox.shrink());
      unawaited(devices.positions.close());
    },
  );
  testWidgets(
    'logout stops GPS and the next account never inherits the previous location',
    (tester) async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      final devices = DrivingDevices();
      MapScene? scene;
      await tester.pumpWidget(
        SignSightApp(
          controller: h.c,
          devices: devices,
          mapBuilder: (_, s) {
            scene = s;
            return const SizedBox.expand();
          },
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bắt đầu'));
      await tester.pump();
      devices.positions.add(
        LocationFix(geometry.first, DateTime.now().toUtc(), accuracy: 5),
      );
      await tester.pumpAndSettle();
      expect(scene!.userLocation, isNotNull);
      await h.c.logout();
      await tester.pumpAndSettle();
      expect(devices.cancelled, 1);
      expect(scene!.userLocation, isNull);
      h.c.user = const UserProfile('other', 'other_driver', 'user');
      await h.c.refreshNearby();
      await tester.pumpAndSettle();
      expect(scene!.userLocation, isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      unawaited(devices.positions.close());
    },
  );
  testWidgets(
    'permission dialog does not cancel first GPS or restart the stream',
    (tester) async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      final devices = DrivingDevices();
      await tester.pumpWidget(
        SignSightApp(
          controller: h.c,
          devices: devices,
          mapBuilder: (_, s) => const SizedBox.expand(),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bắt đầu'));
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      expect(devices.cancelled, 0);
      devices.positions.add(
        LocationFix(geometry.first, DateTime.now().toUtc(), accuracy: 5),
      );
      await tester.pumpAndSettle();
      expect(find.text('Kết thúc'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      unawaited(devices.positions.close());
    },
  );
  testWidgets(
    'preview start browse recenter scope and end retain route without widget overflow',
    (tester) async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      final devices = DrivingDevices();
      MapScene? scene;
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        SignSightApp(
          controller: h.c,
          devices: devices,
          mapBuilder: (_, s) {
            scene = s;
            return const SizedBox.expand();
          },
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Bắt đầu'), findsOneWidget);
      await tester.tap(find.text('Bắt đầu'));
      await tester.pump();
      devices.positions.add(
        LocationFix(
          geometry.first,
          DateTime.now().toUtc(),
          accuracy: 7,
          bearing: 60,
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Kết thúc'), findsOneWidget);
      expect(scene!.followUser, true);
      expect(scene!.userLocation!.point.latitude, geometry.first.latitude);
      final original = List.of(scene!.route);
      scene!.onUserGesture!();
      await tester.pumpAndSettle();
      expect(scene!.followUser, false);
      expect(find.text('Theo dõi lại'), findsOneWidget);
      await tester.tap(find.text('Theo dõi lại'));
      await tester.pumpAndSettle();
      expect(scene!.followUser, true);
      await h.c.changeMapScope(radius: 1000, corridor: 100);
      await tester.pumpAndSettle();
      expect(
        scene!.route.map((p) => p.latitude),
        original.map((p) => p.latitude),
      );
      await tester.tap(find.text('Kết thúc'));
      await tester.pumpAndSettle();
      expect(scene!.followUser, false);
      expect(h.c.route, isNotNull);
      expect(devices.cancelled, 1);
      expect(find.text('Bắt đầu'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      unawaited(devices.positions.close());
    },
  );

  testWidgets(
    'leaving foreground stops device updates; returning resumes without losing route',
    (tester) async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      final devices = DrivingDevices();
      MapScene? scene;
      await tester.pumpWidget(
        SignSightApp(
          controller: h.c,
          devices: devices,
          mapBuilder: (_, s) {
            scene = s;
            return const SizedBox.expand();
          },
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bắt đầu'));
      await tester.pump();
      devices.positions.add(
        LocationFix(geometry.first, DateTime.now().toUtc(), accuracy: 5),
      );
      await tester.pumpAndSettle();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      // Paused apps do not render frames; assert subscription cancellation here,
      // then inspect the resumed scene after the next accepted device fix.
      expect(devices.cancelled, 1);
      expect(h.c.route, isNotNull);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      devices.positions.add(
        LocationFix(geometry.first, DateTime.now().toUtc(), accuracy: 5),
      );
      await tester.pumpAndSettle();
      expect(scene!.followUser, true);
      expect(h.c.route, isNotNull);
      await tester.pumpWidget(const SizedBox.shrink());
      unawaited(devices.positions.close());
    },
  );
}
