import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import 'api.dart';
import 'app.dart';
import 'controller.dart';
import 'session_store.dart';
import 'cookie_session_store.dart';
import 'native_draft_store.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  const configured = String.fromEnvironment('SIGNSIGHT_API_URL');
  final defaultUrl = kIsWeb
      ? Uri.base.origin
      : defaultTargetPlatform == TargetPlatform.android
      ? 'http://10.0.2.2:8000'
      : 'http://127.0.0.1:8000';
  final origin = Uri.parse(configured.isEmpty ? defaultUrl : configured);
  if (!kDebugMode &&
      !kIsWeb &&
      (configured.isEmpty || origin.scheme != 'https')) {
    runApp(
      const MaterialApp(
        home: Scaffold(
          body: Center(
            child: Text('Chưa cấu hình máy chủ HTTPS cho bản phát hành.'),
          ),
        ),
      ),
    );
    return;
  }
  if (kIsWeb) MapLibreMap.webLibrarySource = const MapLibreJsSource.preloaded();
  final controller = AppController(
    SignSightApi(origin, browser: kIsWeb),
    kIsWeb ? CookieSessionStore() : SecureSessionStore(scope: origin.origin),
    drafts: createDraftStore(origin.origin),
  );
  runApp(SignSightApp(controller: controller));
  unawaited(controller.initialize());
}
