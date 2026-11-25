import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import 'models.dart';

/// A device fix, distinct from the map camera and a contribution's sign pin.
class LocationFix {
  const LocationFix(this.point, this.timestamp, {this.accuracy, this.bearing});
  final GeoPoint point;
  final DateTime timestamp;
  final double? accuracy, bearing;

  bool usableAt(DateTime now) {
    final age = now.toUtc().difference(timestamp.toUtc());
    return point.valid &&
        age >= const Duration(seconds: -5) &&
        age < const Duration(seconds: 15) &&
        (accuracy == null ||
            (accuracy!.isFinite && accuracy! >= 0 && accuracy! <= 80));
  }

  double? get direction =>
      bearing != null && bearing!.isFinite && bearing! >= 0 && bearing! < 360
      ? bearing
      : null;
}

/// Foreground-only GPS lifecycle. Map gestures change following, never the fix.
class DrivingTracker extends ChangeNotifier {
  DrivingTracker(
    this.watch, {
    DateTime Function()? now,
    this.firstFixTimeout = const Duration(seconds: 15),
  }) : now = now ?? DateTime.now;
  final Stream<LocationFix> Function() watch;
  final DateTime Function() now;
  final Duration firstFixTimeout;
  StreamSubscription<LocationFix>? _subscription;
  Timer? _firstTimer, _staleTimer;
  Completer<bool>? _first;
  int _operation = 0, followRevision = 0;
  bool _disposed = false, _live = false, _hasStarted = false;
  bool driving = false, following = false, paused = false, busy = false;
  LocationFix? fix;
  String? error;
  bool get fresh =>
      _live && !paused && error == null && fix?.usableAt(now()) == true;

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _cancel() {
    ++_operation;
    unawaited(_subscription?.cancel());
    _subscription = null;
    _firstTimer?.cancel();
    _staleTimer?.cancel();
    if (_first?.isCompleted == false) _first!.complete(false);
    _first = null;
  }

  Future<bool> start() {
    if (_disposed) return Future.value(false);
    if (driving && busy) return _first!.future;
    driving = true;
    _hasStarted = false;
    following = true;
    paused = false;
    followRevision++;
    return _connect();
  }

  Future<bool> _connect() {
    _cancel();
    final operation = _operation;
    final first = Completer<bool>();
    _first = first;
    busy = true;
    _live = false;
    error = null;
    _firstTimer = Timer(firstFixTimeout, () {
      if (operation == _operation) {
        _failed('Chưa nhận được GPS đủ chính xác. Thử lại ở nơi thoáng hơn.');
      }
    });
    try {
      _subscription = watch().listen(
        (value) {
          if (_disposed ||
              operation != _operation ||
              !value.usableAt(now()) ||
              (fix != null && value.timestamp.isBefore(fix!.timestamp))) {
            return;
          }
          fix = value;
          _hasStarted = true;
          _live = true;
          error = null;
          busy = false;
          _firstTimer?.cancel();
          if (!first.isCompleted) first.complete(true);
          _scheduleStale();
          _notify();
        },
        onError: (Object e) {
          if (operation == _operation) {
            if (e is PositionUpdateException || e is TimeoutException) {
              _live = false;
              error = 'GPS tạm thời gián đoạn. Đang chờ vị trí mới.';
              _notify();
              return;
            }
            _failed(
              e is StateError
                  ? e.message.toString()
                  : 'Không nhận được GPS. Kiểm tra quyền vị trí rồi thử lại.',
            );
          }
        },
        onDone: () {
          if (operation == _operation) {
            _failed('GPS đã ngừng cập nhật. Bấm thử lại để tiếp tục.');
          }
        },
      );
    } catch (e) {
      _failed(
        e is StateError
            ? e.message.toString()
            : 'Không mở được GPS. Kiểm tra quyền vị trí.',
      );
    }
    _notify();
    return first.future;
  }

  void _failed(String message) {
    final wasWaiting = busy;
    _cancel();
    _live = false;
    busy = false;
    error = message;
    if (wasWaiting) {
      driving = false;
      following = false;
    }
    _notify();
  }

  void _scheduleStale() {
    _staleTimer?.cancel();
    final remaining =
        const Duration(seconds: 15) -
        now().toUtc().difference(fix!.timestamp.toUtc());
    _staleTimer = Timer(
      remaining.isNegative ? Duration.zero : remaining,
      _notify,
    );
  }

  void preview(LocationFix value) {
    if (_disposed || driving || !value.usableAt(now())) return;
    fix = value;
    _live = true;
    error = null;
    _scheduleStale();
    _notify();
  }

  void browse() {
    if (following) {
      following = false;
      _notify();
    }
  }

  void follow() {
    if (!driving) return;
    following = true;
    followRevision++;
    _notify();
  }

  void pause() {
    if (!driving || paused) return;
    if (!_hasStarted) {
      stop();
      return;
    }
    _cancel();
    paused = true;
    busy = false;
    _live = false;
    _notify();
  }

  Future<bool> resume() {
    if (!driving || _disposed) return Future.value(false);
    paused = false;
    return _connect();
  }

  void stop({bool clearLocation = false}) {
    _cancel();
    driving = following = paused = busy = _live = false;
    if (clearLocation) fix = null;
    error = null;
    _notify();
  }

  @override
  void dispose() {
    _disposed = true;
    _cancel();
    super.dispose();
  }
}
