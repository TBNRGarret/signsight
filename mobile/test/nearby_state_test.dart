import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';

Future<void> settle() async {
  for (var i = 0; i < 10; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

class NearbyHarness {
  final requests = <http.Request>[];
  final replies = <Completer<http.Response>>[];
  final search = Completer<http.Response>();
  final route = Completer<http.Response>();
  late final AppController c;

  NearbyHarness() {
    c = AppController(
      SignSightApi(
        Uri.parse('https://example.invalid'),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/auth/logout')) {
            return http.Response('', 204);
          }
          if (r.url.path.endsWith('/places/search')) return search.future;
          if (r.url.path.endsWith('/navigation/route')) return route.future;
          requests.add(r);
          final reply = Completer<http.Response>();
          replies.add(reply);
          return reply.future;
        }),
      ),
      MemorySessionStore(),
    )..user = const UserProfile('first', 'driver', 'user');
    addTearDown(() {
      c.dispose();
      for (final reply in [...replies, search, route]) {
        if (!reply.isCompleted) {
          reply.complete(http.Response('{"items":[],"total":0}', 200));
        }
      }
    });
  }

  void complete(int index, List<String> ids, {int? total, int status = 200}) {
    final query = requests[index].url.queryParameters;
    replies[index].complete(
      http.Response(
        jsonEncode(
          status == 200
              ? {
                  'items': [
                    for (final id in ids)
                      {
                        'sign': {
                          'id': id,
                          'qcvn_code': 'P.102',
                          'name_vi': 'Synthetic sign',
                          'latitude': double.parse(query['latitude']!),
                          'longitude': double.parse(query['longitude']!),
                          'status': 'active',
                          'verification_status': 'current',
                        },
                        'distance_meters': 0,
                      },
                  ],
                  'total': total ?? ids.length,
                }
              : {'detail': 'Old area unavailable'},
        ),
        status,
      ),
    );
  }
}

void main() {
  test(
    'nearby started during routing cannot overwrite its eventual error',
    () async {
      final h = NearbyHarness(), c = h.c;
      final route = c.routeTo(const Place('p', 'Place', GeoPoint(11, 107)));
      final nearby = c.refreshNearby();
      await settle();
      h.route.complete(http.Response('{"detail":"Routing unavailable"}', 503));
      await route;
      h.complete(0, [], status: 503);
      await nearby;
      expect(c.mapError, 'Routing unavailable');
    },
  );
  test('queued nearby does not erase a newer search failure', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby();
    await settle();
    c.moveCenter(const GeoPoint(11, 107));
    final next = c.refreshNearby();
    final search = c.search('Nguyen Hue');
    h.search.complete(http.Response('{"detail":"Search unavailable"}', 503));
    await search;
    expect(c.mapError, 'Search unavailable');
    h.complete(0, ['old']);
    await settle();
    expect(c.mapError, 'Search unavailable');
    h.complete(1, ['new']);
    await Future.wait([first, next]);
    expect(c.mapError, 'Search unavailable');
  });

  test(
    'a late nearby failure cannot overwrite a newer routing failure',
    () async {
      final h = NearbyHarness(), c = h.c;
      final nearby = c.refreshNearby();
      await settle();
      final route = c.routeTo(const Place('p', 'Place', GeoPoint(11, 107)));
      h.route.complete(http.Response('{"detail":"Routing unavailable"}', 503));
      await route;
      h.complete(0, [], status: 503);
      await nearby;
      expect(c.mapError, 'Routing unavailable');
    },
  );

  test('a queued area is replaced when the center moves again without another refresh', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby();
    await settle();
    c.moveCenter(const GeoPoint(11, 107));
    final queued = c.refreshNearby();
    c.moveCenter(const GeoPoint(12, 108));
    h.complete(0, ['old']);
    await settle();
    expect(h.requests[1].url.queryParameters['latitude'], '12.0');
    h.complete(1, ['latest']);
    await Future.wait([first, queued]);
    expect(h.requests, hasLength(2));
  });

  test('slow nearby A never replaces B and the newest pan is fetched automatically', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby();
    await settle();
    c.moveCenter(const GeoPoint(11, 107));
    final next = c.refreshNearby();
    expect(h.requests, hasLength(1));
    h.complete(0, ['old']);
    await settle();
    expect(c.nearbySigns, isEmpty);
    expect(h.requests, hasLength(2));
    expect(h.requests[1].url.queryParameters['latitude'], '11.0');
    expect(c.mapBusy, isTrue);
    h.complete(1, ['new']);
    await Future.wait([first, next]);
    expect(c.nearbySigns.single.id, 'new');
    expect(c.mapBusy, isFalse);
  });

  test('rapid pans and radius changes coalesce to the latest query', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby();
    await settle();
    c.moveCenter(const GeoPoint(11, 107));
    final b = c.refreshNearby();
    c.moveCenter(const GeoPoint(12, 108));
    c.radius = 1000;
    final last = c.refreshNearby();
    h.complete(0, ['old']);
    await settle();
    expect(h.requests, hasLength(2));
    expect(h.requests[1].url.queryParameters, containsPair('latitude', '12.0'));
    expect(
      h.requests[1].url.queryParameters,
      containsPair('radius_meters', '1000'),
    );
    h.complete(1, ['last']);
    await Future.wait([first, b, last]);
    expect(c.nearbySigns.single.id, 'last');
  });

  test('an old-area error is discarded while the current area loads', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby();
    await settle();
    c.moveCenter(const GeoPoint(11, 107));
    final next = c.refreshNearby();
    h.complete(0, [], status: 503);
    await settle();
    expect(c.mapError, isNull);
    expect(h.requests, hasLength(2));
    h.complete(1, ['new']);
    await Future.wait([first, next]);
    expect(c.mapError, isNull);
  });

  test('identical refreshes share one request and pagination stays in its loaded area', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby(), same = c.refreshNearby();
    await settle();
    expect(h.requests, hasLength(1));
    h.complete(0, ['a', 'b'], total: 4);
    await Future.wait([first, same]);
    final more = c.refreshNearby(more: true);
    await settle();
    expect(h.requests[1].url.queryParameters['offset'], '2');
    c.moveCenter(const GeoPoint(11, 107));
    final fresh = c.refreshNearby(more: true);
    expect(c.nearbySigns, isEmpty);
    h.complete(1, ['old-page'], total: 4);
    await settle();
    expect(h.requests, hasLength(3));
    expect(h.requests[2].url.queryParameters['offset'], '0');
    h.complete(2, ['new-area']);
    await Future.wait([more, fresh]);
    expect(c.nearbySigns.map((s) => s.id), ['new-area']);
  });

  test('same-area load more appends exactly once', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby();
    await settle();
    h.complete(0, ['a'], total: 2);
    await first;
    final more = c.refreshNearby(more: true),
        duplicate = c.refreshNearby(more: true);
    await settle();
    expect(h.requests, hasLength(2));
    h.complete(1, ['b'], total: 2);
    await Future.wait([more, duplicate]);
    expect(c.nearbySigns.map((s) => s.id), ['a', 'b']);
  });

  test(
    'nearby completion does not clear foreground search ownership',
    () async {
      final h = NearbyHarness(), c = h.c;
      final nearby = c.refreshNearby();
      await settle();
      final search = c.search('Nguyen Hue');
      h.complete(0, ['nearby']);
      await nearby;
      expect(c.mapBusy, isTrue);
      h.search.complete(
        http.Response(
          '{"items":[{"id":"p","name":"Place","latitude":11,"longitude":107}]}',
          200,
        ),
      );
      await search;
      expect(c.places.single.id, 'p');
      expect(c.nearbySigns.single.id, 'nearby');
      expect(c.mapBusy, isFalse);
    },
  );

  test('a nearby request during routing cannot cancel the route', () async {
    final h = NearbyHarness(), c = h.c;
    final route = c.routeTo(const Place('p', 'Place', GeoPoint(11, 107)));
    final nearby = c.refreshNearby();
    await settle();
    expect(h.requests, hasLength(1));
    h.complete(0, ['nearby']);
    await nearby;
    expect(c.mapBusy, isTrue);
    h.route.complete(
      http.Response(
        '{"geometry":[{"latitude":11,"longitude":107}],"signs":[],"distance_meters":100,"duration_seconds":30}',
        200,
      ),
    );
    await route;
    expect(c.route, isNotNull);
    expect(c.mapBusy, isFalse);
  });

  test('logout drops queued requests and old completion cannot change the new account busy state', () async {
    final h = NearbyHarness(), c = h.c;
    final old = c.refreshNearby();
    await settle();
    c.moveCenter(const GeoPoint(11, 107));
    final queued = c.refreshNearby();
    await c.logout();
    c.user = const UserProfile('second', 'new-driver', 'user');
    final fresh = c.refreshNearby();
    await settle();
    expect(h.requests, hasLength(2));
    h.complete(0, ['private-old']);
    await Future.wait([old, queued]);
    expect(c.nearbySigns, isEmpty);
    expect(c.mapBusy, isTrue);
    expect(h.requests, hasLength(2));
    h.complete(1, ['new-account']);
    await fresh;
    expect(c.nearbySigns.single.id, 'new-account');
    expect(c.mapBusy, isFalse);
  });

  test('a current-area failure settles and allows an explicit retry', () async {
    final h = NearbyHarness(), c = h.c;
    final first = c.refreshNearby();
    await settle();
    h.complete(0, [], status: 503);
    await first;
    expect(c.mapError, isNotNull);
    expect(c.mapBusy, isFalse);
    final retry = c.refreshNearby();
    await settle();
    h.complete(1, ['retried']);
    await retry;
    expect(c.mapError, isNull);
    expect(c.nearbySigns.single.id, 'retried');
  });
}
