import 'dart:typed_data';
import 'dart:convert';

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
  const Detection(
    this.id,
    this.code,
    this.name,
    this.confidence, {
    this.bbox,
    this.classId,
  });
  final String id, code, name;
  final double confidence;
  final List<double>? bbox;
  final int? classId;
  factory Detection.fromJson(Map<String, dynamic> j) {
    final b = j['bbox'] == null ? null : jsonMap(j['bbox']);
    return Detection(
      j['id'] as String,
      j['qcvn_code'] as String,
      j['name_vi'] as String,
      number(j['confidence'] ?? 0),
      classId: j['predicted_class'] as int?,
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
    this.name = 'capture.jpg',
  });
  UploadedPhoto? photo;
  final String name;
  Uint8List bytes;
  List<Detection> detections;
  String? selectedId;
  bool previewReady = false;
  bool labelConfirmed = false;
  int? proposedClass;
  String correctionReason = '';
  GeoPoint? suggestion, confirmedLocation;
  Detection? get selected =>
      detections.where((d) => d.id == selectedId).firstOrNull;

  Map<String, dynamic> toJson() => {
    'version': 1,
    'name': name,
    'bytes': base64Encode(bytes),
    if (photo != null)
      'photo': {
        'id': photo!.id,
        'width': photo!.width,
        'height': photo!.height,
      },
    'detections': detections
        .map(
          (d) => {
            'id': d.id,
            'qcvn_code': d.code,
            'name_vi': d.name,
            'confidence': d.confidence,
            if (d.classId != null) 'predicted_class': d.classId,
            if (d.bbox != null)
              'bbox': Map.fromIterables(['x1', 'y1', 'x2', 'y2'], d.bbox!),
          },
        )
        .toList(),
    'selected_id': selectedId,
    'preview_ready': previewReady,
    'label_confirmed': labelConfirmed,
    'proposed_class': proposedClass,
    'correction_reason': correctionReason,
    'suggestion': suggestion?.toJson(),
    'confirmed_location': confirmedLocation?.toJson(),
  };
  factory CaptureDraft.fromJson(Map<String, dynamic> j) {
    if (j['version'] != 1) throw const FormatException('Unknown draft version');
    final bytes = base64Decode(j['bytes'] as String);
    if (bytes.isEmpty || bytes.length > 10 * 1024 * 1024) {
      throw const FormatException('Invalid draft photo');
    }
    return CaptureDraft(
        photo: j['photo'] == null
            ? null
            : UploadedPhoto.fromJson(jsonMap(j['photo'])),
        bytes: bytes,
        name: j['name'] as String,
        detections: (j['detections'] as List)
            .map((d) => Detection.fromJson(jsonMap(d)))
            .toList(),
        selectedId: j['selected_id'] as String?,
      )
      ..previewReady = j['preview_ready'] == true
      ..labelConfirmed = j['label_confirmed'] == true
      ..proposedClass = j['proposed_class'] as int?
      ..correctionReason = (j['correction_reason'] as String?) ?? ''
      ..suggestion = j['suggestion'] == null
          ? null
          : GeoPoint.fromJson(jsonMap(j['suggestion']))
      ..confirmedLocation = j['confirmed_location'] == null
          ? null
          : GeoPoint.fromJson(jsonMap(j['confirmed_location']));
  }
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
      (j['proposed_qcvn_code'] ?? d['qcvn_code']) as String,
      (j['proposed_name_vi'] ?? d['name_vi']) as String,
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

enum ReportAction {
  confirmExisting('confirm_existing', 'Biển vẫn còn'),
  reportRemoved('report_removed', 'Biển đã bị gỡ'),
  reportDamaged('report_damaged', 'Biển hư hỏng'),
  correctLocation('correct_location', 'Sai vị trí'),
  correctClass('correct_class', 'Sai loại biển'),
  updateEvidence('update_evidence', 'Cập nhật ảnh');

  const ReportAction(this.value, this.label);
  final String value, label;
}

class SignReport {
  const SignReport(
    this.id,
    this.signId,
    this.imageId,
    this.action,
    this.status,
    this.comment,
    this.reviewComment,
  );
  final String id, signId, imageId, action, status, comment;
  final String? reviewComment;
  factory SignReport.fromJson(Map<String, dynamic> j) => SignReport(
    j['id'] as String,
    j['record_id'] as String,
    j['image_id'] as String,
    j['action'] as String,
    j['status'] as String,
    j['comment'] as String,
    j['review_comment'] as String?,
  );
  String get actionLabel =>
      ReportAction.values.where((a) => a.value == action).firstOrNull?.label ??
      action;
  String get statusLabel => switch (status) {
    'accepted' => 'Đã duyệt',
    'rejected' => 'Từ chối',
    _ => 'Chờ duyệt',
  };
}

class SignType {
  const SignType(this.id, this.code, this.name);
  final int id;
  final String code, name;
  factory SignType.fromJson(Map<String, dynamic> j) => SignType(
    j['new_id'] as int,
    j['qcvn_code'] as String,
    j['name_vi'] as String,
  );
}
