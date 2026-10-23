import 'dart:async';

import 'package:flutter/material.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import 'models.dart';

class MapScene {
  const MapScene({
    required this.center,
    this.signs = const [],
    this.route = const [],
    this.pin,
    this.onTap,
    this.onIdle,
    this.onSign,
  });
  final GeoPoint center;
  final List<Sign> signs;
  final List<GeoPoint> route;
  final GeoPoint? pin;
  final ValueChanged<GeoPoint>? onTap, onIdle;
  final ValueChanged<Sign>? onSign;
}

typedef MapBuilder = Widget Function(BuildContext context, MapScene scene);
Widget buildSignMap(BuildContext context, MapScene scene) =>
    SignMap(scene: scene);

class SignMap extends StatefulWidget {
  const SignMap({super.key, required this.scene});
  final MapScene scene;
  @override
  State<SignMap> createState() => _SignMapState();
}

class _SignMapState extends State<SignMap> {
  MapLibreMapController? _controller;
  bool _loaded = false;
  String? _error;
  int _generation = 0, _instance = 0;
  Timer? _timeout;
  Future<void> _pending = Future.value();
  LatLng point(GeoPoint p) => LatLng(p.latitude, p.longitude);
  @override
  void initState() {
    super.initState();
    _startTimer();
  }

  void _startTimer() {
    _timeout?.cancel();
    _timeout = Timer(const Duration(seconds: 18), () {
      if (mounted && !_loaded) {
        setState(
          () => _error = 'Chưa tải được bản đồ. Kiểm tra kết nối rồi thử lại.',
        );
      }
    });
  }

  @override
  void didUpdateWidget(covariant SignMap old) {
    super.didUpdateWidget(old);
    final current = _controller?.cameraPosition?.target;
    final wanted = widget.scene.center;
    if (current != null &&
        ((current.latitude - wanted.latitude).abs() > 0.00001 ||
            (current.longitude - wanted.longitude).abs() > 0.00001)) {
      unawaited(
        _controller!.animateCamera(CameraUpdate.newLatLng(point(wanted))),
      );
    }
    _sync();
  }

  void _sync() {
    final controller = _controller;
    if (!_loaded || controller == null) return;
    final generation = ++_generation;
    final scene = widget.scene;
    _pending = _pending.catchError((_) {}).then((_) async {
      if (!mounted || generation != _generation || controller != _controller) {
        return;
      }
      try {
        await controller.clearCircles();
        await controller.clearLines();
        if (scene.route.length > 1) {
          await controller.addLine(
            LineOptions(
              geometry: scene.route.map(point).toList(),
              lineColor: '#2563eb',
              lineWidth: 5,
            ),
          );
        }
        for (final sign in scene.signs) {
          if (!mounted || generation != _generation) return;
          await controller.addCircle(
            CircleOptions(
              geometry: point(sign.point),
              circleRadius: 9,
              circleColor: sign.needsConfirmation ? '#d97706' : '#2563eb',
              circleStrokeColor: '#ffffff',
              circleStrokeWidth: 2,
            ),
            {'id': sign.id},
          );
        }
        if (scene.pin != null) {
          await controller.addCircle(
            CircleOptions(
              geometry: point(scene.pin!),
              circleRadius: 10,
              circleColor: '#ef4444',
              circleStrokeColor: '#ffffff',
              circleStrokeWidth: 3,
            ),
          );
        }
      } catch (_) {
        if (mounted && generation == _generation) {
          setState(() => _error = 'Không thể cập nhật bản đồ. Thử tải lại.');
        }
      }
    });
  }

  @override
  void dispose() {
    _timeout?.cancel();
    _generation++;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Stack(
    fit: StackFit.expand,
    children: [
      MapLibreMap(
        key: ValueKey(_instance),
        styleString: 'https://tiles.openfreemap.org/styles/liberty',
        initialCameraPosition: CameraPosition(
          target: point(widget.scene.center),
          zoom: 15,
        ),
        trackCameraPosition: true,
        onMapCreated: (controller) {
          _controller = controller;
          controller.onCircleTapped.add((circle) {
            final id = circle.data?['id'];
            final sign = widget.scene.signs
                .where((s) => s.id == id)
                .firstOrNull;
            if (sign != null) widget.scene.onSign?.call(sign);
          });
        },
        onStyleLoadedCallback: () {
          _loaded = true;
          _timeout?.cancel();
          if (mounted) setState(() => _error = null);
          _sync();
        },
        onMapClick: (_, position) => widget.scene.onTap?.call(
          GeoPoint(position.latitude, position.longitude),
        ),
        onCameraIdle: () {
          final p = _controller?.cameraPosition?.target;
          if (p != null) {
            widget.scene.onIdle?.call(GeoPoint(p.latitude, p.longitude));
          }
        },
      ),
      if (_error != null)
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 300),
            child: Material(
              elevation: 4,
              borderRadius: BorderRadius.circular(16),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 8),
                    FilledButton.icon(
                      onPressed: () {
                        setState(() {
                          _loaded = false;
                          _controller = null;
                          _error = null;
                          _instance++;
                        });
                        _startTimer();
                      },
                      icon: const Icon(Icons.refresh),
                      label: const Text('Thử tải lại'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
    ],
  );
}
