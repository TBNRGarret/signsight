part of '../../controller.dart';

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
}

extension _MapActions on AppController {
  Future<void> _actionRefreshNearby({bool more = false}) async {
    if (!signedIn || mapBusy) return;
    final version = _authVersion, operation = ++_mapVersion;
    mapBusy = true;
    mapError = null;
    _notify();
    try {
      final page = await api.nearby(
        center.latitude,
        center.longitude,
        radius: radius,
        offset: more ? nearbySigns.length : 0,
      );
      if (!_current(version) || operation != _mapVersion) return;
      nearbySigns = more ? [...nearbySigns, ...page.items] : page.items;
      nearbyTotal = page.total;
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

  void _actionMoveCenter(GeoPoint point) {
    if (point.valid) {
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
