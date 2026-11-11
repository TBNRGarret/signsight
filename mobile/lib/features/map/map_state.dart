part of '../../controller.dart';

class _NearbyQuery {
  const _NearbyQuery(
    this.center,
    this.radius,
    this.offset,
    this.foregroundVersion,
  );
  final GeoPoint center;
  final int radius, offset;
  // Work started during search/routing must not own foreground error feedback.
  final int? foregroundVersion;

  bool matches(GeoPoint point, int meters) =>
      center.latitude == point.latitude &&
      center.longitude == point.longitude &&
      radius == meters;

  bool sameRequest(_NearbyQuery other) =>
      matches(other.center, other.radius) &&
      offset == other.offset &&
      foregroundVersion == other.foregroundVersion;
}

class _NearbyJob {
  _NearbyJob(this.authVersion, this.query);
  final int authVersion;
  final done = Completer<void>();
  _NearbyQuery query;
  _NearbyQuery? queued;
}

class _MapState {
  String? mapError;
  bool mapBusy = false;
  GeoPoint center = const GeoPoint(10.7769, 106.7009);
  List<Sign> nearbySigns = [];
  int nearbyTotal = 0;
  int radius = 500;
  List<Place> places = [];
  DrivingRoute? route;
  Sign? selectedSign;
  int corridor = 50;
  _NearbyJob? nearbyJob;
  _NearbyQuery? loadedNearby;
}

extension _MapActions on AppController {
  Future<void> _actionRefreshNearby({bool more = false}) {
    if (!signedIn) return Future.value();
    final loaded = _mapState.loadedNearby;
    final sameArea = loaded?.matches(center, radius) == true;
    final query = _NearbyQuery(
      center,
      radius,
      more && sameArea ? nearbySigns.length : 0,
      _mapState.mapBusy ? null : _mapVersion,
    );
    if (!sameArea) {
      nearbySigns = [];
      nearbyTotal = 0;
      _mapState.loadedNearby = null;
    }
    final running = _mapState.nearbyJob;
    if (running != null) {
      running.queued = query.sameRequest(running.query) ? null : query;
      _notify();
      return running.done.future;
    }
    final job = _NearbyJob(_authVersion, query);
    _mapState.nearbyJob = job;
    unawaited(_runNearby(job));
    return job.done.future;
  }

  bool _ownsNearby(_NearbyJob job) =>
      _current(job.authVersion) && identical(_mapState.nearbyJob, job);

  Future<void> _runNearby(_NearbyJob job) async {
    try {
      while (_ownsNearby(job)) {
        final query = job.query;
        if (query.foregroundVersion == _mapVersion) mapError = null;
        _notify();
        try {
          final page = await api.nearby(
            query.center.latitude,
            query.center.longitude,
            radius: query.radius,
            offset: query.offset,
          );
          if (_ownsNearby(job) && query.matches(center, radius)) {
            if (query.offset == 0) {
              nearbySigns = page.items;
            } else if (_mapState.loadedNearby?.matches(center, radius) ==
                    true &&
                nearbySigns.length == query.offset) {
              nearbySigns = [...nearbySigns, ...page.items];
            } else {
              job.queued = _NearbyQuery(
                center,
                radius,
                0,
                query.foregroundVersion,
              );
            }
            nearbyTotal = page.total;
            _mapState.loadedNearby = query;
          }
        } catch (error) {
          if (_ownsNearby(job) &&
              (query.matches(center, radius) &&
                      query.foregroundVersion == _mapVersion ||
                  error is ApiFailure && error.status == 401)) {
            await _failure(error, job.authVersion, (m) => mapError = m);
          }
        }
        if (!_ownsNearby(job)) break;
        final next =
            (job.queued?.matches(center, radius) == true ? job.queued : null) ??
            (query.matches(center, radius)
                ? null
                : _NearbyQuery(center, radius, 0, query.foregroundVersion));
        job.queued = null;
        if (next == null) break;
        job.query = next;
      }
    } finally {
      if (identical(_mapState.nearbyJob, job)) {
        _mapState.nearbyJob = null;
        _notify();
      }
      job.done.complete();
    }
  }

  void _actionMoveCenter(GeoPoint point) {
    if (point.valid) {
      if (point.latitude != center.latitude ||
          point.longitude != center.longitude) {
        nearbySigns = [];
        nearbyTotal = 0;
        _mapState.loadedNearby = null;
      }
      center = point;
      _notify();
    }
  }

  Future<void> _actionSearch(String query) async {
    if (!signedIn) return;
    final cleaned = query.trim();
    if (cleaned.length < 3) {
      mapError = 'Nhập ít nhất 3 ký tự.';
      _notify();
      return;
    }
    final version = _authVersion, operation = ++_mapVersion;
    mapBusy = true;
    mapError = null;
    places = [];
    _notify();
    try {
      final results = await api.search(cleaned);
      if (_current(version) && operation == _mapVersion) {
        places = results;
        if (results.isEmpty) {
          mapError = 'Chưa tìm thấy địa điểm. Thử thêm tên đường hoặc quận.';
        }
      }
    } catch (error) {
      if (operation == _mapVersion) {
        await _failure(error, version, (m) => mapError = m);
      }
    } finally {
      if (_current(version) && operation == _mapVersion) {
        mapBusy = false;
        _notify();
      }
    }
  }

  Future<void> _actionRouteTo(Place place) async {
    if (!signedIn) return;
    final version = _authVersion, operation = ++_mapVersion;
    mapBusy = true;
    mapError = null;
    places = [];
    route = null;
    _notify();
    try {
      final result = await api.route(center, place.point, buffer: corridor);
      if (_current(version) && operation == _mapVersion) route = result;
    } catch (error) {
      if (operation == _mapVersion) {
        await _failure(error, version, (m) => mapError = m);
      }
    } finally {
      if (_current(version) && operation == _mapVersion) {
        mapBusy = false;
        _notify();
      }
    }
  }

  void _actionClearRoute() {
    _mapVersion++;
    route = null;
    places = [];
    mapBusy = false;
    _notify();
  }

  void _actionSelectSign(Sign? sign) {
    selectedSign = sign;
    _notify();
  }

  Future<void> _actionOpenSign(String id) async {
    final version = _authVersion;
    try {
      final sign = await api.sign(id);
      if (_current(version)) {
        center = sign.point;
        selectedSign = sign;
        _notify();
      }
    } catch (error) {
      await _failure(error, version, (m) => mapError = m);
    }
  }
}
