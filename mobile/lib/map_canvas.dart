import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import 'models.dart';
import 'sign_icons.dart';
import 'driving_tracker.dart';
import 'location_puck.dart';

class MapScene {
  const MapScene({
    required this.center,
    this.signs = const [],
    this.route = const [],
    this.pin,
    this.onTap,
    this.onIdle,
    this.onSign,
    this.pinOnly = false,
    this.selectedSignId,
    this.routeFitRevision = 0,
    this.userLocation,
    this.userLocationStale = false,
    this.followUser = false,
    this.followRevision = 0,
    this.onUserGesture,
  });
  final GeoPoint center;
  final List<Sign> signs;
  final List<GeoPoint> route;
  final GeoPoint? pin;
  final ValueChanged<GeoPoint>? onTap, onIdle;
  final ValueChanged<Sign>? onSign;
  final bool pinOnly;
  final String? selectedSignId;
  final int routeFitRevision;
  final LocationFix? userLocation;
  final bool userLocationStale, followUser;
  final int followRevision;
  final VoidCallback? onUserGesture;
}

typedef MapBuilder = Widget Function(BuildContext context, MapScene scene);
Widget buildSignMap(BuildContext context, MapScene scene) =>
    SignMap(scene: scene);

class SignMap extends StatefulWidget {
  const SignMap({super.key, required this.scene, this.styleString});
  final MapScene scene;

  /// Optional explicit style for fixtures or callers; otherwise follows theme.
  final String? styleString;
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
  final _icons = <String>{};
  bool _pinSourceAdded = false;
  String _style = '';
  List<GeoPoint>? _drawnRoute;
  int? _lastFitRevision;
  Future<void> _locationPending = Future.value();
  bool _locationSourceAdded = false;
  int _locationRevision = 0;
  String? _locationSignature;
  Offset? _pointerOrigin;
  bool _gestureSent = false;
  bool _samePoint(GeoPoint a, GeoPoint b) =>
      a.latitude == b.latitude && a.longitude == b.longitude;
  bool _sameRoute(List<GeoPoint>? a, List<GeoPoint> b) =>
      a != null &&
      a.length == b.length &&
      Iterable<int>.generate(b.length).every((i) => _samePoint(a[i], b[i]));
  LatLng point(GeoPoint p) => LatLng(p.latitude, p.longitude);
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _updateStyle();
  }

  void _updateStyle() {
    final next =
        widget.styleString ??
        (Theme.of(context).brightness == Brightness.dark
            ? 'assets/maps/signsight-night.json'
            : 'assets/maps/signsight-day.json');
    if (next == _style) return;
    _style = next;
    _loaded = false;
    _error = null;
    _generation++;
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
    _updateStyle();
    final current = _controller?.cameraPosition?.target;
    final wanted = widget.scene.center;
    if (!widget.scene.followUser &&
        current != null &&
        !_samePoint(old.scene.center, wanted) &&
        ((current.latitude - wanted.latitude).abs() > 0.00001 ||
            (current.longitude - wanted.longitude).abs() > 0.00001)) {
      unawaited(
        _controller!
            .animateCamera(CameraUpdate.newLatLng(point(wanted)))
            .catchError((_) {
              if (mounted) {
                setState(
                  () => _error = 'Không thể cập nhật bản đồ. Thử tải lại.',
                );
              }
              return false;
            }),
      );
    }
    final previous = old.scene, next = widget.scene;
    final sameSigns =
        previous.signs.length == next.signs.length &&
        Iterable<int>.generate(next.signs.length)
            .every((i) => identical(previous.signs[i], next.signs[i]));
    final samePin =
        previous.pin == null && next.pin == null ||
        previous.pin != null &&
            next.pin != null &&
            _samePoint(previous.pin!, next.pin!);
    if (!sameSigns ||
        !samePin ||
        previous.selectedSignId != next.selectedSignId ||
        previous.pinOnly != next.pinOnly ||
        !_sameRoute(previous.route, next.route) ||
        previous.routeFitRevision != next.routeFitRevision) {
      _sync();
    }
    _syncLocation();
  }

  void _syncLocation() {
    final controller = _controller;
    if (!_loaded || controller == null || widget.scene.pinOnly) return;
    final scene = widget.scene;
    if (scene.userLocation == null && !_locationSourceAdded) return;
    final data = locationGeoJson(
      scene.userLocation,
      stale: scene.userLocationStale,
    );
    final signature = jsonEncode([
      data,
      scene.followUser,
      scene.followRevision,
    ]);
    if (signature == _locationSignature) return;
    final revision = ++_locationRevision, style = _style;
    bool valid() =>
        mounted && _loaded && controller == _controller && style == _style;
    _locationPending = _locationPending.catchError((_) {}).then((_) async {
      if (!valid() || revision != _locationRevision) return;
      try {
        if (!_locationSourceAdded) {
          await controller.addGeoJsonSource('user-location', data);
          if (!valid()) return;
          await controller.addFillLayer(
            'user-location',
            'user-location-accuracy',
            const FillLayerProperties(
              fillColor: ['get', 'color'],
              fillOpacity: .14,
            ),
            filter: [
              '==',
              ['get', 'kind'],
              'accuracy',
            ],
          );
          if (!valid()) return;
          await controller.addFillLayer(
            'user-location',
            'user-location-heading',
            const FillLayerProperties(fillColor: '#2563eb', fillOpacity: .45),
            filter: [
              '==',
              ['get', 'kind'],
              'heading',
            ],
          );
          if (!valid()) return;
          await controller.addCircleLayer(
            'user-location',
            'user-location-dot',
            const CircleLayerProperties(
              circleColor: ['get', 'color'],
              circleRadius: 8,
              circleStrokeColor: '#ffffff',
              circleStrokeWidth: 3,
            ),
            filter: [
              '==',
              ['get', 'kind'],
              'position',
            ],
          );
          if (!valid()) return;
          _locationSourceAdded = true;
        } else {
          await controller.setGeoJsonSource('user-location', data);
          if (!valid()) return;
        }
        _locationSignature = signature;
        if (revision == _locationRevision &&
            scene.followUser &&
            !scene.userLocationStale &&
            widget.scene.followUser &&
            scene.userLocation != null) {
          await controller.animateCamera(
            CameraUpdate.newCameraPosition(
              CameraPosition(
                target: point(scene.userLocation!.point),
                zoom: 17,
                tilt: 40,
                bearing:
                    scene.userLocation!.direction ??
                    controller.cameraPosition?.bearing ??
                    0,
              ),
            ),
            duration: const Duration(milliseconds: 600),
          );
        }
      } catch (_) {
        if (valid()) {
          setState(() => _error = 'Không thể cập nhật bản đồ. Thử tải lại.');
        }
      }
    });
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
        if (scene.pinOnly) {
          final data = <String, dynamic>{
            'type': 'FeatureCollection',
            'features': [
              if (scene.pin != null)
                {
                  'type': 'Feature',
                  'geometry': {
                    'type': 'Point',
                    'coordinates': [scene.pin!.longitude, scene.pin!.latitude],
                  },
                  'properties': <String, dynamic>{},
                },
            ],
          };
          if (!_pinSourceAdded) {
            await controller.addGeoJsonSource('sign-pin', data);
            if (!mounted || controller != _controller) return;
            await controller.addCircleLayer(
              'sign-pin',
              'sign-pin-dot',
              const CircleLayerProperties(
                circleRadius: 10,
                circleColor: '#ef4444',
                circleStrokeColor: '#ffffff',
                circleStrokeWidth: 3,
              ),
            );
            _pinSourceAdded = true;
          } else {
            await controller.setGeoJsonSource('sign-pin', data);
          }
          return;
        }
        await controller.clearCircles();
        await controller.clearSymbols();
        await controller.setSymbolIconAllowOverlap(true);
        final catalog = await SignIconCatalog.load();
        if (!mounted || generation != _generation || !_loaded) return;
        final selectedColor =
            '#${Theme.of(context).colorScheme.primary.toARGB32().toRadixString(16).padLeft(8, '0').substring(2)}';
        if (!_sameRoute(_drawnRoute, scene.route)) {
          _drawnRoute = null;
          await controller.clearLines();
          if (!mounted || generation != _generation || !_loaded) return;
          if (scene.route.length > 1) {
            final path = scene.route.map(point).toList();
            await controller.addLine(
              LineOptions(geometry: path, lineColor: '#ffffff', lineWidth: 11),
            );
            if (!mounted || generation != _generation || !_loaded) return;
            await controller.addLine(
              LineOptions(geometry: path, lineColor: '#2563eb', lineWidth: 7),
            );
            if (!mounted || generation != _generation || !_loaded) return;
          }
          _drawnRoute = List.of(scene.route);
        }
        if (scene.route.length > 1) {
          for (final endpoint in [
            (scene.route.first, '#15803d', 'A'),
            (scene.route.last, '#dc2626', 'B'),
          ]) {
            await controller.addCircle(
              CircleOptions(
                geometry: point(endpoint.$1),
                circleRadius: 9,
                circleColor: endpoint.$2,
                circleStrokeColor: '#ffffff',
                circleStrokeWidth: 3,
              ),
            );
            final marker = 'route-endpoint-${endpoint.$3}';
            if (!_icons.contains(marker)) {
              await controller.addImage(
                marker,
                await renderRouteEndpoint(
                  endpoint.$3,
                  Color(
                    0xff000000 | int.parse(endpoint.$2.substring(1), radix: 16),
                  ),
                ),
              );
              if (!mounted || generation != _generation || !_loaded) return;
              _icons.add(marker);
            }
            await controller.addSymbol(
              SymbolOptions(
                geometry: point(endpoint.$1),
                iconImage: marker,
                iconSize: 1,
              ),
            );
            if (!mounted || generation != _generation || !_loaded) return;
          }
        }
        for (final sign in scene.signs) {
          if (!mounted || generation != _generation) return;
          await controller.addCircle(
            CircleOptions(
              geometry: point(sign.point),
              circleRadius: 24,
              circleColor: '#ffffff',
              circleStrokeColor: sign.id == scene.selectedSignId
                  ? selectedColor
                  : '#d4ddd1',
              circleStrokeWidth: sign.id == scene.selectedSignId ? 3 : 1.5,
            ),
            {'id': sign.id},
          );
          final key = 'sign:${catalog.resolve(sign.code, name: sign.name)}';
          if (!_icons.contains(key)) {
            await controller.addImage(
              key,
              await renderSignIcon(sign.code, name: sign.name),
            );
            if (!mounted || generation != _generation || !_loaded) return;
            _icons.add(key);
          }
          await controller.addSymbol(
            SymbolOptions(
              geometry: point(sign.point),
              iconImage: key,
              iconSize: .1875,
            ),
            {'id': sign.id},
          );
          if (sign.needsConfirmation) {
            const badge = 'marker-revalidation';
            if (!_icons.contains(badge)) {
              await controller.addImage(badge, await renderConfirmationBadge());
              if (!mounted || generation != _generation || !_loaded) return;
              _icons.add(badge);
            }
            await controller.addSymbol(
              SymbolOptions(
                geometry: point(sign.point),
                iconImage: badge,
                iconSize: 1,
                iconOffset: const Offset(14, -14),
              ),
              {'id': sign.id},
            );
          }
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
        if (mounted &&
            generation == _generation &&
            !scene.followUser &&
            scene.route.length > 1 &&
            _lastFitRevision != scene.routeFitRevision) {
          var minLat = scene.route.first.latitude, maxLat = minLat;
          var minLon = scene.route.first.longitude, maxLon = minLon;
          for (final p in scene.route) {
            if (p.latitude < minLat) minLat = p.latitude;
            if (p.latitude > maxLat) maxLat = p.latitude;
            if (p.longitude < minLon) minLon = p.longitude;
            if (p.longitude > maxLon) maxLon = p.longitude;
          }
          // Claim the fit before awaiting: camera idle can rebuild the scene
          // while the animation is in flight, without requesting another fit.
          _lastFitRevision = scene.routeFitRevision;
          await controller.animateCamera(
            CameraUpdate.newLatLngBounds(
              LatLngBounds(
                southwest: LatLng(minLat, minLon),
                northeast: LatLng(maxLat, maxLon),
              ),
              left: 32,
              right: 32,
              top: 100,
              bottom: (MediaQuery.sizeOf(context).height * .4 + 24)
                  .clamp(144, 360)
                  .toDouble(),
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
      Listener(
        behavior: HitTestBehavior.opaque,
        onPointerDown: (event) {
          _pointerOrigin = event.position;
          _gestureSent = false;
        },
        onPointerMove: (event) {
          if (!_gestureSent &&
              _pointerOrigin != null &&
              (event.position - _pointerOrigin!).distance > 8) {
            _gestureSent = true;
            widget.scene.onUserGesture?.call();
          }
        },
        onPointerSignal: (_) => widget.scene.onUserGesture?.call(),
        child: MapLibreMap(
          key: ValueKey(_instance),
          styleString: _style,
          // The picker needs one dot, not asynchronous annotation-manager setup.
          annotationOrder: widget.scene.pinOnly
              ? const []
              : const [
                  AnnotationType.line,
                  AnnotationType.circle,
                  AnnotationType.symbol,
                  AnnotationType.fill,
                ],
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
            controller.onSymbolTapped.add((symbol) {
              final sign = widget.scene.signs
                  .where((s) => s.id == symbol.data?['id'])
                  .firstOrNull;
              if (sign != null) widget.scene.onSign?.call(sign);
            });
          },
          onStyleLoadedCallback: () {
            if (!mounted) return;
            _loaded = true;
            _pinSourceAdded = false;
            _locationSourceAdded = false;
            _locationSignature = null;
            _locationRevision++;
            _drawnRoute = null;
            _icons.clear();
            if (!widget.scene.pinOnly) {
              unawaited(
                _controller!.setSymbolIconAllowOverlap(true).catchError((_) {
                  if (mounted) {
                    setState(
                      () => _error = 'Không thể cập nhật bản đồ. Thử tải lại.',
                    );
                  }
                }),
              );
            }
            _timeout?.cancel();
            if (mounted) setState(() => _error = null);
            _sync();
            _syncLocation();
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
                          _drawnRoute = null;
                          _lastFitRevision = null;
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
