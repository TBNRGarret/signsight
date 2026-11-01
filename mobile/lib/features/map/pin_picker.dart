part of '../../app.dart';

class PinPicker extends StatefulWidget {
  const PinPicker({
    super.key,
    this.initial,
    required this.fallback,
    required this.mapBuilder,
    required this.devices,
  });
  final GeoPoint? initial;
  final GeoPoint fallback;
  final MapBuilder mapBuilder;
  final DeviceServices devices;
  @override
  State<PinPicker> createState() => _PinPickerState();
}

class _PinPickerState extends State<PinPicker> {
  GeoPoint? _point;
  late GeoPoint _center;
  String? _error;
  @override
  void initState() {
    super.initState();
    _point = widget.initial;
    _center = _point ?? widget.fallback;
  }

  Future<void> _gps() async {
    try {
      final p = await widget.devices.locate();
      if (mounted) {
        setState(() {
          _point = p;
          _center = p;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Chưa lấy được GPS. Chạm bản đồ để đặt vị trí.',
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Vị trí của biển')),
    body: Stack(
      children: [
        Positioned.fill(
          child: widget.mapBuilder(
            context,
            MapScene(
              center: _center,
              pin: _point,
              pinOnly: true,
              onTap: (point) => setState(() => _point = point),
            ),
          ),
        ),
        Positioned(
          right: 16,
          top: 16,
          child: FloatingActionButton.small(
            heroTag: 'pin-gps',
            tooltip: 'Dùng GPS',
            onPressed: _gps,
            child: const Icon(Icons.my_location),
          ),
        ),
        Positioned(
          left: 16,
          right: 16,
          bottom: 24,
          child: Material(
            borderRadius: BorderRadius.circular(18),
            elevation: 4,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    _error ??
                        (_point == null
                            ? 'Chạm bản đồ để đặt biển.'
                            : 'Kiểm tra ghim đúng vị trí biển rồi xác nhận.'),
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: _point == null
                        ? null
                        : () => Navigator.pop(context, _point),
                    child: const Text('Xác nhận vị trí'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    ),
  );
}
