import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:mime/mime.dart';

import 'models.dart';

class ApiFailure implements Exception {
  const ApiFailure(this.status, this.message);
  final int status;
  final String message;
  @override
  String toString() => message;
}

class SignSightApi {
  SignSightApi(this.origin, {http.Client? client, this.browser = false})
    : _client = client ?? http.Client() {
    if (!['http', 'https'].contains(origin.scheme) ||
        origin.host.isEmpty ||
        origin.userInfo.isNotEmpty ||
        origin.hasQuery ||
        origin.hasFragment) {
      throw ArgumentError('Invalid API origin');
    }
  }
  final Uri origin;
  final http.Client _client;
  final bool browser;
  String? _token;
  void useToken(String? token) {
    _token = browser ? null : token;
  }

  Map<String, String> get _headers => {
    if (browser) 'X-SignSight-Web': '1',
    if (!browser && _token != null) 'Authorization': 'Bearer $_token',
  };
  Uri _url(String path, [Map<String, String>? query]) =>
      origin.resolve('/api/v1$path').replace(queryParameters: query);
  Future<http.Response> _send(http.BaseRequest request) async {
    request.headers.addAll(_headers);
    try {
      final response = await http.Response.fromStream(
        await _client.send(request).timeout(const Duration(seconds: 90)),
      ).timeout(const Duration(seconds: 90));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        var message = 'Không thể hoàn tất yêu cầu (${response.statusCode}).';
        try {
          final body = jsonMap(jsonDecode(utf8.decode(response.bodyBytes)));
          final detail = body['detail'];
          if (detail is String) message = detail;
          if (detail is List) {
            message = detail
                .map((e) => jsonMap(e)['msg'].toString())
                .join('; ');
          }
        } catch (_) {}
        throw ApiFailure(response.statusCode, message);
      }
      return response;
    } on ApiFailure {
      rethrow;
    } on TimeoutException {
      throw const ApiFailure(0, 'Kết nối quá lâu. Vui lòng thử lại.');
    } on http.ClientException {
      throw const ApiFailure(
        0,
        'Chưa kết nối được máy chủ. Kiểm tra Wi-Fi và địa chỉ API.',
      );
    }
  }

  Future<dynamic> _json(
    String method,
    String path, {
    Object? body,
    Map<String, String>? query,
  }) async {
    final request = http.Request(method, _url(path, query));
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    final response = await _send(request);
    return response.bodyBytes.isEmpty
        ? null
        : jsonDecode(utf8.decode(response.bodyBytes));
  }

  Future<Session> login(String username, String password) async =>
      Session.fromJson(
        jsonMap(
          await _json(
            'POST',
            '/auth/login',
            body: {
              'username': username,
              'password': password,
              'remember_me': browser,
            },
          ),
        ),
      );
  Future<void> register(String username, String email, String password) async {
    await _json(
      'POST',
      '/auth/register',
      body: {'username': username, 'email': email, 'password': password},
    );
  }

  Future<UserProfile> profile() async =>
      UserProfile.fromJson(jsonMap(await _json('GET', '/auth/me')));
  Future<void> logout() async {
    await _json('POST', '/auth/logout');
  }

  Future<PageData<Sign>> nearby(
    double latitude,
    double longitude, {
    int offset = 0,
    int radius = 500,
  }) async {
    final j = jsonMap(
      await _json(
        'GET',
        '/signs/nearby',
        query: {
          'latitude': '$latitude',
          'longitude': '$longitude',
          'radius_meters': '$radius',
          'offset': '$offset',
          'limit': '25',
        },
      ),
    );
    return PageData(
      (j['items'] as List).map((v) {
        final r = jsonMap(v);
        return Sign.fromJson(
          jsonMap(r['sign']),
          distance: number(r['distance_meters']),
        );
      }).toList(),
      j['total'] as int,
    );
  }

  Future<Sign> sign(String id) async => Sign.fromJson(
    jsonMap(
      jsonMap(await _json('GET', '/signs/${Uri.encodeComponent(id)}'))['sign'],
    ),
  );
  Future<List<Place>> search(String query) async {
    final j = jsonMap(
      await _json('GET', '/places/search', query: {'q': query}),
    );
    return (j['items'] as List).map((v) => Place.fromJson(jsonMap(v))).toList();
  }

  Future<DrivingRoute> route(
    GeoPoint origin,
    GeoPoint destination, {
    int buffer = 50,
  }) async => DrivingRoute.fromJson(
    jsonMap(
      await _json(
        'POST',
        '/navigation/route',
        body: {
          'origin': origin.toJson(),
          'destination': destination.toJson(),
          'buffer_meters': buffer,
        },
      ),
    ),
  );
  Future<UploadedPhoto> upload(Uint8List bytes, String name) async {
    final mime =
        lookupMimeType(name, headerBytes: bytes) ?? 'application/octet-stream';
    if (!['image/jpeg', 'image/png', 'image/webp'].contains(mime)) {
      throw const ApiFailure(422, 'Chọn ảnh JPG, PNG hoặc WebP.');
    }
    final request = http.MultipartRequest('POST', _url('/images'))
      ..files.add(
        http.MultipartFile.fromBytes(
          'file',
          bytes,
          filename: name,
          contentType: MediaType.parse(mime),
        ),
      );
    return UploadedPhoto.fromJson(
      jsonMap(jsonDecode(utf8.decode((await _send(request)).bodyBytes))),
    );
  }

  Future<Uint8List> photoContent(String id) async => (await _send(
    http.Request('GET', _url('/images/${Uri.encodeComponent(id)}/content')),
  )).bodyBytes;
  Future<List<Detection>> detect(String id) async {
    final j = jsonMap(
      await _json('POST', '/images/${Uri.encodeComponent(id)}/detect'),
    );
    return (j['detections'] as List)
        .map((v) => Detection.fromJson(jsonMap(v)))
        .toList();
  }

  Future<void> contribute(
    String imageId,
    String detectionId,
    GeoPoint point,
  ) async {
    await _json(
      'POST',
      '/observations',
      body: {
        'image_id': imageId,
        'items': [
          {
            'detection_id': detectionId,
            ...point.toJson(),
            'location_source': 'user_confirmed',
          },
        ],
      },
    );
  }

  Future<PageData<Contribution>> history({
    String? status,
    int offset = 0,
  }) async {
    final j = jsonMap(
      await _json(
        'GET',
        '/me/observations',
        query: {'offset': '$offset', 'limit': '20', 'status': ?status},
      ),
    );
    return PageData(
      (j['items'] as List)
          .map((v) => Contribution.fromJson(jsonMap(v)))
          .toList(),
      j['total'] as int,
    );
  }

  Future<PageData<Sign>> confirmations({int offset = 0}) async {
    final j = jsonMap(
      await _json(
        'GET',
        '/me/confirmation-requests',
        query: {'offset': '$offset', 'limit': '20'},
      ),
    );
    return PageData(
      (j['items'] as List).map((v) => Sign.fromJson(jsonMap(v))).toList(),
      j['total'] as int,
    );
  }

  Future<PageData<SignReport>> reports({int offset = 0}) async {
    final j = jsonMap(
      await _json(
        'GET',
        '/me/reports',
        query: {'offset': '$offset', 'limit': '20'},
      ),
    );
    return PageData(
      (j['items'] as List).map((v) => SignReport.fromJson(jsonMap(v))).toList(),
      j['total'] as int,
    );
  }

  Future<List<SignType>> taxonomy() async {
    final j = jsonMap(await _json('GET', '/taxonomy'));
    return (j['items'] as List)
        .map((v) => SignType.fromJson(jsonMap(v)))
        .toList();
  }

  Future<SignReport> report(
    String signId,
    ReportAction action,
    String imageId,
    String comment, {
    GeoPoint? point,
    int? proposedClass,
  }) async => SignReport.fromJson(
    jsonMap(
      await _json(
        'POST',
        '/signs/${Uri.encodeComponent(signId)}/reports',
        body: {
          'action': action.value,
          'image_id': imageId,
          'comment': comment.trim(),
          if (action == ReportAction.correctLocation && point != null)
            ...point.toJson(),
          if (action == ReportAction.correctClass)
            'proposed_class': proposedClass,
        },
      ),
    ),
  );

  void close() => _client.close();
}
