import 'dart:typed_data';

Map<String, dynamic> jsonMap(Object? value) =>
    Map<String, dynamic>.from(value as Map);
double number(Object? value) => (value as num).toDouble();
DateTime utcDate(String value) => DateTime.parse(
  RegExp(r'(Z|[+-]\d\d:\d\d)$').hasMatch(value) ? value : '${value}Z',
).toUtc();

class GeoPoint {
  const GeoPoint(this.latitude, this.longitude);
  final double latitude, longitude;
  bool get valid =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude.abs() <= 90 &&
      longitude.abs() <= 180;
  Map<String, double> toJson() => {
    'latitude': latitude,
    'longitude': longitude,
  };
  factory GeoPoint.fromJson(Map<String, dynamic> j) =>
      GeoPoint(number(j['latitude']), number(j['longitude']));
}

class UserProfile {
  const UserProfile(this.id, this.username, this.role);
  final String id, username, role;
  bool get isUser => role == 'user';
  factory UserProfile.fromJson(Map<String, dynamic> j) => UserProfile(
    j['id'] as String,
    j['username'] as String,
    j['role'] as String,
  );
  Map<String, String> toJson() => {
    'id': id,
    'username': username,
    'role': role,
  };
}

class Session {
  const Session(this.token, this.expiresAt, this.user);
  final String token;
  final DateTime expiresAt;
  final UserProfile user;
  factory Session.fromJson(Map<String, dynamic> j) => Session(
    j['access_token'] as String,
    utcDate(j['expires_at'] as String),
    UserProfile.fromJson(jsonMap(j['user'])),
  );
  Map<String, dynamic> toJson() => {
    'access_token': token,
    'expires_at': expiresAt.toUtc().toIso8601String(),
    'user': user.toJson(),
  };
}

class Sign {
  const Sign(
    this.id,
    this.code,
    this.name,
    this.point, {
    this.distance,
    this.verification = 'current',
    this.status = 'active',
  });
  final String id, code, name, verification, status;
  final GeoPoint point;
  final double? distance;
  factory Sign.fromJson(Map<String, dynamic> j, {double? distance}) => Sign(
    j['id'] as String,
    j['qcvn_code'] as String,
    j['name_vi'] as String,
    GeoPoint.fromJson(j),
    distance: distance,
    verification: j['verification_status'] as String? ?? 'unverified',
    status: j['status'] as String? ?? 'active',
  );
  bool get needsConfirmation => verification == 'needs_confirmation';
}

class PageData<T> {
  const PageData(this.items, this.total);
  final List<T> items;
  final int total;
}

class Place {
  const Place(this.id, this.name, this.point);
  final String id, name;
  final GeoPoint point;
  factory Place.fromJson(Map<String, dynamic> j) =>
      Place(j['id'].toString(), j['name'] as String, GeoPoint.fromJson(j));
}

class DrivingRoute {
  const DrivingRoute(this.geometry, this.signs, this.distance, this.duration);
  final List<GeoPoint> geometry;
  final List<Sign> signs;
  final double distance, duration;
  factory DrivingRoute.fromJson(Map<String, dynamic> j) => DrivingRoute(
    (j['geometry'] as List).map((p) => GeoPoint.fromJson(jsonMap(p))).toList(),
    (j['signs'] as List).map((v) {
      final r = jsonMap(v);
      return Sign.fromJson(
        jsonMap(r['sign']),
        distance: number(r['distance_along_route_meters'] ?? 0),
      );
    }).toList(),
    number(j['distance_meters']),
    number(j['duration_seconds']),
  );
}

class UploadedPhoto {
  const UploadedPhoto(this.id, this.width, this.height, {this.exif});
  final String id;
  final int width, height;
  final GeoPoint? exif;
  factory UploadedPhoto.fromJson(Map<String, dynamic> j) => UploadedPhoto(
    j['id'] as String,
    j['width'] as int,
    j['height'] as int,
    exif: j['exif_latitude'] != null && j['exif_longitude'] != null
        ? GeoPoint(number(j['exif_latitude']), number(j['exif_longitude']))
        : null,
  );
}

class Detection {
  const Detection(this.id, this.code, this.name, this.confidence, {this.bbox});
  final String id, code, name;
  final double confidence;
  final List<double>? bbox;
  factory Detection.fromJson(Map<String, dynamic> j) {
    final b = j['bbox'] == null ? null : jsonMap(j['bbox']);
    return Detection(
      j['id'] as String,
      j['qcvn_code'] as String,
      j['name_vi'] as String,
      number(j['confidence'] ?? 0),
      bbox: b == null
          ? null
          : ['x1', 'y1', 'x2', 'y2'].map((k) => number(b[k])).toList(),
    );
  }
}

class CaptureDraft {
  CaptureDraft({
    required this.photo,
    required this.bytes,
    this.detections = const [],
    this.selectedId,
  });
  final UploadedPhoto photo;
  Uint8List bytes;
  List<Detection> detections;
  String? selectedId;
  bool previewReady = false;
  bool labelConfirmed = false;
  GeoPoint? suggestion, confirmedLocation;
  Detection? get selected =>
      detections.where((d) => d.id == selectedId).firstOrNull;
}

class Contribution {
  const Contribution(
    this.id,
    this.imageId,
    this.code,
    this.name,
    this.status, {
    this.signId,
    this.comment,
  });
  final String id, imageId, code, name, status;
  final String? signId, comment;
  factory Contribution.fromJson(Map<String, dynamic> j) {
    final d = jsonMap(j['detection']);
    return Contribution(
      j['id'] as String,
      j['image_id'] as String,
      d['qcvn_code'] as String,
      d['name_vi'] as String,
      j['status'] as String,
      signId: j['sign_record_id'] as String?,
      comment: j['review_comment'] as String?,
    );
  }
  String get statusLabel => switch (status) {
    'accepted' => 'Đã duyệt',
    'rejected' => 'Cần chỉnh sửa',
    _ => 'Chờ duyệt',
  };
}
