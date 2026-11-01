part of '../../app.dart';

class DetectionPainter extends CustomPainter {
  DetectionPainter(this.draft);
  final CaptureDraft draft;
  @override
  void paint(Canvas canvas, Size size) {
    final box = draft.selected?.bbox;
    final photo = draft.photo;
    if (box == null || photo == null) return;
    final scale = math.min(
      size.width / photo.width,
      size.height / photo.height,
    );
    final dx = (size.width - photo.width * scale) / 2,
        dy = (size.height - photo.height * scale) / 2;
    canvas.drawRect(
      Rect.fromLTRB(
        dx + box[0] * scale,
        dy + box[1] * scale,
        dx + box[2] * scale,
        dy + box[3] * scale,
      ),
      Paint()
        ..color = Colors.red
        ..strokeWidth = 3
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant DetectionPainter oldDelegate) => true;
}
