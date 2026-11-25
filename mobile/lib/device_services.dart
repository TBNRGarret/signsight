import 'package:geolocator/geolocator.dart';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

import 'models.dart';
import 'driving_tracker.dart';

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

  Future<PickedPhoto?> recoverPhoto() async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return null;
    final result = await _picker.retrieveLostData();
    if (result.exception != null) throw result.exception!;
    final file = result.files?.firstOrNull;
    return file == null
        ? null
        : PickedPhoto(await file.readAsBytes(), file.name);
  }

  Future<void> _locationPermission() async {
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
  }

  Future<GeoPoint> locate() async {
    await _locationPermission();
    final p = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 15),
      ),
    );
    return GeoPoint(p.latitude, p.longitude);
  }

  Stream<LocationFix> watchLocation() async* {
    await _locationPermission();
    yield* Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 3,
      ),
    ).map(
      (p) => LocationFix(
        GeoPoint(p.latitude, p.longitude),
        p.timestamp.toUtc(),
        accuracy: p.accuracy,
        bearing: p.speed.isFinite && p.speed >= 2 ? p.heading : null,
      ),
    );
  }
}
