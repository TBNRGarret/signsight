import 'dart:typed_data';

import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import 'models.dart';

class PickedPhoto {
  const PickedPhoto(this.bytes, this.name);
  final Uint8List bytes;
  final String name;
}

class DeviceServices {
  final ImagePicker _picker = ImagePicker();
  Future<PickedPhoto?> pickPhoto(bool camera) async {
    final file = await _picker.pickImage(
      source: camera ? ImageSource.camera : ImageSource.gallery,
      imageQuality: 85,
      maxWidth: 2048,
      maxHeight: 2048,
    );
    return file == null
        ? null
        : PickedPhoto(await file.readAsBytes(), file.name);
  }

  Future<GeoPoint> locate() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw StateError('Bật vị trí trên thiết bị rồi thử lại.');
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw StateError(
        'Chưa có quyền vị trí. Bạn vẫn có thể chạm bản đồ để đặt biển.',
      );
    }
    final p = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 15),
      ),
    );
    return GeoPoint(p.latitude, p.longitude);
  }
}
