import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

/// Compact symbols for map discovery; the detail panel supplies the full class.
Future<Uint8List> renderSignIcon(String code) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  final fill = Paint()..color = Colors.white;
  final red = Paint()..color = const Color(0xffdc2626);
  final blue = Paint()..color = const Color(0xff1d4ed8);
  final ink = Paint()..color = const Color(0xff111827);
  const center = Offset(48, 48);
  void text(String label, double size, Color color) {
    final p = TextPainter(
      text: TextSpan(
        text: label,
        style: TextStyle(
          color: color,
          fontSize: size,
          fontWeight: FontWeight.w800,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout(maxWidth: 80);
    p.paint(canvas, Offset(48 - p.width / 2, 48 - p.height / 2));
  }

  canvas.drawCircle(center, 46, fill);
  if (code == 'P.122') {
    final path = Path();
    for (var i = 0; i < 8; i++) {
      final a = math.pi / 8 + i * math.pi / 4;
      final x = 48 + 42 * math.cos(a), y = 48 + 42 * math.sin(a);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path..close(), red);
    text('STOP', 23, Colors.white);
  } else if (code.startsWith('W.')) {
    final triangle = Path()
      ..moveTo(48, 7)
      ..lineTo(91, 84)
      ..lineTo(5, 84)
      ..close();
    canvas.drawPath(triangle, red);
    canvas.drawPath(
      Path()
        ..moveTo(48, 23)
        ..lineTo(77, 76)
        ..lineTo(19, 76)
        ..close(),
      Paint()..color = const Color(0xfffef08a),
    );
    if (code == 'W.227') {
      canvas.drawCircle(const Offset(47, 43), 5, ink);
      canvas.drawPath(
        Path()
          ..moveTo(47, 50)
          ..lineTo(40, 62)
          ..lineTo(31, 70)
          ..moveTo(40, 62)
          ..lineTo(49, 70)
          ..moveTo(45, 54)
          ..lineTo(58, 61)
          ..lineTo(66, 72),
        Paint()
          ..color = ink.color
          ..strokeWidth = 5
          ..style = PaintingStyle.stroke,
      );
    } else {
      text('!', 44, ink.color);
    }
  } else if (code.startsWith('R.301')) {
    canvas.drawCircle(center, 42, blue);
    final path = code == 'R.301e'
        ? (Path()
            ..moveTo(25, 23)
            ..lineTo(36, 23)
            ..lineTo(36, 49)
            ..lineTo(61, 63)
            ..lineTo(61, 49)
            ..lineTo(79, 68)
            ..lineTo(55, 79)
            ..lineTo(59, 69)
            ..lineTo(25, 50)
            ..close())
        : (Path()
            ..moveTo(42, 76)
            ..lineTo(42, 40)
            ..lineTo(29, 40)
            ..lineTo(48, 19)
            ..lineTo(67, 40)
            ..lineTo(54, 40)
            ..lineTo(54, 76)
            ..close());
    canvas.drawPath(path, fill);
  } else if (code.startsWith('P.127')) {
    canvas.drawCircle(center, 42, red);
    canvas.drawCircle(center, 32, fill);
    final digits = RegExp(r'\((\d+)\)').firstMatch(code)?.group(1) ?? '?';
    text(digits, digits.length > 2 ? 28 : 36, ink.color);
  } else if (code == 'P.102') {
    canvas.drawCircle(center, 42, red);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(20, 40, 56, 16),
        const Radius.circular(2),
      ),
      fill,
    );
  } else {
    canvas.drawCircle(center, 42, code.startsWith('P.') ? red : blue);
    canvas.drawCircle(center, 33, fill);
    if (code == 'P.125') {
      void car(double x, Paint paint) {
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromLTWH(x, 40, 19, 24),
            const Radius.circular(3),
          ),
          paint,
        );
        canvas.drawRect(Rect.fromLTWH(x + 3, 34, 13, 12), paint);
        canvas.drawRect(Rect.fromLTWH(x + 3, 39, 13, 6), fill);
      }

      car(26, red);
      car(51, ink);
    } else {
      text(code, 16, ink.color);
    }
  }
  final picture = recorder.endRecording();
  final image = await picture.toImage(96, 96);
  final bytes = (await image.toByteData(format: ui.ImageByteFormat.png))!.buffer
      .asUint8List();
  image.dispose();
  picture.dispose();
  return bytes;
}
