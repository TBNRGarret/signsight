import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';
import 'package:signsight_user/driving_tracker.dart';

const destination = Place('p', 'Bến Bạch Đằng', GeoPoint(10.78, 106.71));
const geometry = [GeoPoint(10.7769, 106.7009), GeoPoint(10.78, 106.71)];

class RouteHarness {
  final requests = <http.Request>[];
  final signReplies = <Completer<http.Response>>[];
  final routeReplies = <Completer<http.Response>>[];
  bool deferSigns = false, deferRoute = false;
  late final AppController c;

  RouteHarness() {
    c = AppController(
      SignSightApi(
        Uri.parse('https://example.invalid'),
        client: MockClient((r) async {
          requests.add(r);
          if (r.url.path.endsWith('/navigation/route')) {
            if (deferRoute) {
              final reply = Completer<http.Response>();
              routeReplies.add(reply);
              return reply.future;
            }
            return routeReply();
          }
          if (r.url.path.endsWith('/route-signs')) {
            if (deferSigns) {
              final reply = Completer<http.Response>();
              signReplies.add(reply);
              return reply.future;
            }
            return signsReply('updated');
          }
          if (r.url.path.endsWith('/auth/logout')) {
            return http.Response('', 204);
          }
          return http.Response('{"items":[],"total":0}', 200);
        }),
      ),
      MemorySessionStore(),
    )..user = const UserProfile('u', 'driver', 'user');
    addTearDown(() {
      c.dispose();
      for (final reply in [...signReplies, ...routeReplies]) {
        if (!reply.isCompleted) {
          reply.complete(http.Response('{"detail":"closed"}', 503));
        }
      }
    });
  }

  static Map<String, dynamic> sign(String id) => {
    'sign': {
      'id': id,
      'qcvn_code': 'P.102',
      'name_vi': 'Synthetic sign',
      'latitude': 10.78,
      'longitude': 106.71,
      'status': 'active',
      'verification_status': 'current',
    },
    'distance_along_route_meters': 100,
  };
  static http.Response signsReply(String id) => http.Response(
    jsonEncode({
      'signs': [sign(id)],
    }),
    200,
  );
  static http.Response routeReply() => http.Response(
    jsonEncode({
      'geometry': geometry.map((p) => p.toJson()).toList(),
      'signs': [sign('original')],
      'distance_meters': 1200,
      'duration_seconds': 180,
    }),
    200,
  );
}

void main() {
  test('route origin uses fresh GPS even when the map was panned', () async {
    final h = RouteHarness();
    h.c.updateUserLocation(
      LocationFix(
        const GeoPoint(10.75, 106.68),
        DateTime.now().toUtc(),
        accuracy: 6,
      ),
    );
    h.c.moveCenter(const GeoPoint(10.9, 106.9));
    await h.c.routeTo(destination);
    expect(h.c.routeOrigin!.latitude, 10.75);
    expect(h.c.center.latitude, 10.9);
    final request = h.requests.firstWhere(
      (r) => r.url.path.endsWith('/navigation/route'),
    );
    expect(jsonDecode(request.body)['origin']['latitude'], 10.75);
  });
  Future<void> settleRequests() async {
    for (var i = 0; i < 8; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('changing radius keeps route and destination without requesting another route', () async {
    final h = RouteHarness();
    await h.c.routeTo(destination);
    final original = h.c.route;
    h.requests.clear();
    await h.c.changeMapScope(radius: 1000, corridor: 50);
    expect(h.c.route, same(original));
    expect(h.c.routeDestination?.name, destination.name);
    expect(
      h.requests.where((r) => r.url.path.contains('/navigation/')),
      isEmpty,
    );
    expect(h.requests.single.url.queryParameters['radius_meters'], '1000');
  });
  test(
    'corridor uses existing geometry after a pan and keeps distance and origin',
    () async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      final original = h.c.route!;
      final origin = h.c.routeOrigin;
      h.c.moveCenter(const GeoPoint(11, 107));
      h.requests.clear();
      await h.c.changeMapScope(radius: 500, corridor: 100);
      expect(h.requests, hasLength(1));
      expect(h.requests.single.url.path, endsWith('/route-signs'));
      final body = jsonDecode(h.requests.single.body) as Map<String, dynamic>;
      expect(
        body['waypoints'],
        original.geometry.map((p) => p.toJson()).toList(),
      );
      expect(body['buffer_meters'], 100);
      expect(h.c.route!.geometry, same(original.geometry));
      expect(h.c.route!.distance, original.distance);
      expect(h.c.route!.duration, original.duration);
      expect(h.c.routeOrigin, same(origin));
      expect(h.c.routeDestination?.id, destination.id);
      expect(h.c.route!.signs.single.id, 'updated');
      expect(h.c.routeAppliedCorridor, 100);
    },
  );
  test('late corridor response cannot overwrite the latest scope', () async {
    final h = RouteHarness();
    await h.c.routeTo(destination);
    h.deferSigns = true;
    final first = h.c.changeMapScope(radius: 500, corridor: 20);
    await settleRequests();
    final last = h.c.changeMapScope(radius: 500, corridor: 100);
    await settleRequests();
    expect(h.c.route, isNotNull);
    h.signReplies[1].complete(RouteHarness.signsReply('latest'));
    await last;
    h.signReplies[0].complete(RouteHarness.signsReply('stale'));
    await first;
    expect(h.c.route!.signs.single.id, 'latest');
    expect(h.c.routeAppliedCorridor, 100);
    expect(h.c.routeSignsBusy, isFalse);
  });
  test('failed corridor refresh keeps last route with its actual applied scope and supports retry', () async {
    final h = RouteHarness();
    await h.c.routeTo(destination);
    final original = h.c.route;
    h.deferSigns = true;
    final update = h.c.changeMapScope(radius: 500, corridor: 100);
    await settleRequests();
    h.signReplies.single.complete(
      http.Response('{"detail":"Scope unavailable"}', 503),
    );
    await update;
    expect(h.c.route, same(original));
    expect(h.c.routeAppliedCorridor, 50);
    expect(h.c.routeSignsError, contains('Scope unavailable'));
    h.deferSigns = false;
    await h.c.refreshRouteSigns();
    expect(h.c.routeAppliedCorridor, 100);
    expect(h.c.routeSignsError, isNull);
  });
  test('clearing route cancels a pending sign refresh and cannot resurrect geometry', () async {
    final h = RouteHarness();
    await h.c.routeTo(destination);
    h.deferSigns = true;
    final update = h.c.changeMapScope(radius: 500, corridor: 100);
    await settleRequests();
    h.c.clearRoute();
    h.signReplies.single.complete(RouteHarness.signsReply('old'));
    await update;
    expect(h.c.route, isNull);
    expect(h.c.routeDestination, isNull);
    expect(h.c.routeSignsBusy, isFalse);
  });
  test(
    'choosing another destination discards a previous corridor refresh',
    () async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      h.deferSigns = true;
      final update = h.c.changeMapScope(radius: 500, corridor: 100);
      await settleRequests();
      await h.c.routeTo(const Place('new', 'Điểm mới', GeoPoint(11, 107)));
      h.signReplies.single.complete(RouteHarness.signsReply('old'));
      await update;
      expect(h.c.routeDestination?.id, 'new');
      expect(h.c.route!.signs.single.id, 'original');
    },
  );
  test('scope changed while initial route is loading applies to that same route when ready', () async {
    final h = RouteHarness()..deferRoute = true;
    final initial = h.c.routeTo(destination);
    await settleRequests();
    await h.c.changeMapScope(radius: 500, corridor: 100);
    h.routeReplies.single.complete(RouteHarness.routeReply());
    await initial;
    expect(h.c.routeDestination?.id, destination.id);
    expect(h.c.routeAppliedCorridor, 100);
    expect(
      h.requests.where((r) => r.url.path.endsWith('/navigation/route')),
      hasLength(1),
    );
    expect(h.c.route!.signs.single.id, 'updated');
  });
  test(
    'logout discards pending corridor results and endpoint labels',
    () async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      h.deferSigns = true;
      final update = h.c.changeMapScope(radius: 500, corridor: 100);
      await settleRequests();
      await h.c.logout();
      h.signReplies.single.complete(RouteHarness.signsReply('private'));
      await update;
      expect(h.c.route, isNull);
      expect(h.c.routeDestination, isNull);
      expect(h.c.routeOrigin, isNull);
      expect(h.c.routeSignsBusy, isFalse);
    },
  );
  test(
    'applying unchanged scope makes no request and does not clear route',
    () async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      h.requests.clear();
      await h.c.changeMapScope(radius: 500, corridor: 50);
      expect(h.requests, isEmpty);
      expect(h.c.route, isNotNull);
    },
  );
  testWidgets(
    'applying search radius/corridor preserves the displayed selected route',
    (tester) async {
      final h = RouteHarness();
      await h.c.routeTo(destination);
      final original = h.c.route!.geometry;
      MapScene? rendered;
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        SignSightApp(
          controller: h.c,
          mapBuilder: (_, scene) {
            rendered = scene;
            return const SizedBox.expand();
          },
        ),
      );
      addTearDown(() async => tester.pumpWidget(const SizedBox.shrink()));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Phạm vi tìm biển'));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<int>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('1000 m').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<int>).last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('100 m').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Áp dụng'));
      await tester.pumpAndSettle();
      expect(
        h.c.route,
        isNotNull,
        reason: 'Changing sign scope must not clear navigation',
      );
      expect(rendered!.route, same(original));
      expect(find.text('Đến Bến Bạch Đằng'), findsOneWidget);
      expect(find.text('Xem toàn tuyến'), findsOneWidget);
      final token = rendered!.routeFitRevision;
      await tester.tap(find.text('Xem toàn tuyến'));
      await tester.pumpAndSettle();
      expect(rendered!.routeFitRevision, greaterThan(token));
      expect(rendered!.route, same(original));
    },
  );
}
