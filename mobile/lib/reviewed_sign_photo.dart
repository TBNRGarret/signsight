import 'dart:typed_data';

import 'package:flutter/material.dart';

import 'api.dart';

/// Fetches a single reviewed photo only for the current sign and session.
class ReviewedSignPhoto extends StatefulWidget {
  const ReviewedSignPhoto({
    super.key,
    required this.api,
    required this.signId,
    required this.sessionKey,
  });
  final SignSightApi api;
  final String signId, sessionKey;
  @override
  State<ReviewedSignPhoto> createState() => _ReviewedSignPhotoState();
}

class _ReviewedSignPhotoState extends State<ReviewedSignPhoto> {
  late Future<Uint8List?> _photo;
  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    _photo = widget.api.signPhoto(widget.signId);
  }

  @override
  void didUpdateWidget(covariant ReviewedSignPhoto oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.api != widget.api ||
        oldWidget.signId != widget.signId ||
        oldWidget.sessionKey != widget.sessionKey) {
      _load();
    }
  }

  Widget _failure() => Row(
    children: [
      const Expanded(child: Text('Chưa tải được ảnh đã duyệt.')),
      TextButton(
        onPressed: () => setState(_load),
        child: const Text('Thử lại'),
      ),
    ],
  );

  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List?>(
    future: _photo,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Text('Đang tải ảnh đã duyệt…'),
        );
      }
      if (snapshot.hasError) return _failure();
      final bytes = snapshot.data;
      if (bytes == null) return const Text('Chưa có ảnh đã duyệt.');
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Image.memory(
            bytes,
            height: 136,
            width: double.infinity,
            fit: BoxFit.contain,
            gaplessPlayback: false,
            semanticLabel: 'Ảnh đóng góp đã duyệt của biển',
            errorBuilder: (context, error, stack) => _failure(),
          ),
        ),
      );
    },
  );
}
