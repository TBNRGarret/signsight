import 'dart:convert';

import 'package:flutter/services.dart';

import 'dart:ui' as ui;

import 'package:flutter/painting.dart';

/// Explicit visual aliases, shared with web. No database/code migration occurs.
class SignIconCatalog {
  SignIconCatalog._(this._aliases);
  final Map<String, String> _aliases;
  static Future<SignIconCatalog>? _loaded;
  static String _normalize(String value) =>
      value.replaceAll(RegExp(r'[.\s]'), '').toUpperCase();

  static Future<SignIconCatalog> load() => _loaded ??= _load();
  static Future<SignIconCatalog> _load() async {
    final data = jsonDecode(
      await rootBundle.loadString('assets/signs/catalog.json'),
    ) as Map<String, dynamic>;
    final aliases = <String, String>{};
    for (final row in data['entries'] as List) {
      for (final alias in row['aliases'] as List) {
        aliases[_normalize(alias as String)] = row['key'] as String;
      }
    }
    return SignIconCatalog._(aliases);
  }

  String resolve(String code, {String name = ''}) {
    final normalized = _normalize(code),
        label = name.trim().replaceAll(RegExp(r'\s+'), ' ').toLowerCase();
    if (normalized == 'R301E') {
      return [
            'đi vòng sang bên phải',
            'hướng đi phải theo: đi vòng sang bên phải',
            'keep right',
          ].contains(label)
          ? 'keep_right'
          : 'unknown';
    }
    if (normalized == 'W245A') {
      return ['đi chậm', 'slow down', 'slow_down'].contains(label)
          ? 'slow_down'
          : 'unknown';
    }
    return _aliases[normalized] ?? 'unknown';
  }
}

/// Returns an approved local PNG, with a neutral fallback for unknown classes.
Future<Uint8List> renderSignIcon(String code, {String name = ''}) async {
  final key = (await SignIconCatalog.load()).resolve(code, name: name);
  final bytes = await rootBundle.load('assets/signs/$key.png');
  return bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes);
}

/// A separate status overlay; the underlying road sign image stays unchanged.
Future<Uint8List> renderConfirmationBadge() async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  canvas.drawCircle(
    const Offset(10, 10),
    10,
    Paint()..color = const Color(0xffffc85b),
  );
  final text = TextPainter(
    text: const TextSpan(
      text: '!',
      style: TextStyle(
        color: Color(0xff422f00),
        fontSize: 14,
        fontWeight: FontWeight.w700,
      ),
    ),
    textDirection: TextDirection.ltr,
  )..layout();
  text.paint(canvas, Offset(10 - text.width / 2, 10 - text.height / 2));
  final picture = recorder.endRecording(),
      image = await picture.toImage(20, 20);
  final bytes = (await image.toByteData(format: ui.ImageByteFormat.png))!;
  image.dispose();
  picture.dispose();
  return bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes);
}

/// Route labels are local bitmaps, so A/B do not require remote map glyphs.
final _routeEndpointImages = <String, Uint8List>{};
Future<Uint8List> renderRouteEndpoint(String label, Color color) async {
  final key = '$label:${color.toARGB32()}';
  final cached = _routeEndpointImages[key];
  if (cached != null) return cached;
  final bytes = await _renderRouteEndpoint(label, color);
  _routeEndpointImages[key] = bytes;
  return bytes;
}

Future<Uint8List> _renderRouteEndpoint(String label, Color color) async {
  final recorder = ui.PictureRecorder();
  // Use one recorder for the complete marker, including its contrast ring.
  final markerCanvas = Canvas(recorder);
  markerCanvas.drawCircle(
    const Offset(16, 16),
    16,
    Paint()..color = const Color(0xffffffff),
  );
  markerCanvas.drawCircle(const Offset(16, 16), 13, Paint()..color = color);
  final text = TextPainter(
    text: TextSpan(
      text: label,
      style: const TextStyle(
        color: Color(0xffffffff),
        fontSize: 18,
        fontWeight: FontWeight.w700,
      ),
    ),
    textDirection: TextDirection.ltr,
  )..layout();
  text.paint(markerCanvas, Offset(16 - text.width / 2, 16 - text.height / 2));
  final picture = recorder.endRecording(),
      image = await picture.toImage(32, 32);
  final bytes = (await image.toByteData(format: ui.ImageByteFormat.png))!;
  image.dispose();
  picture.dispose();
  text.dispose();
  return bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes);
}
