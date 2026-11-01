import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'controller.dart';
import 'device_services.dart';
import 'feedback.dart';
import 'map_canvas.dart';
import 'models.dart';
import 'app_theme.dart';
import 'ui_components.dart';

part 'app/auth_sheet.dart';
part 'app/user_shell.dart';
part 'features/capture/capture_screen.dart';
part 'features/capture/detection_overlay.dart';
part 'features/history/contribution_detail.dart';
part 'features/history/history_screen.dart';
part 'features/map/map_screen.dart';
part 'features/map/pin_picker.dart';
part 'features/map/sign_list.dart';

class SignSightApp extends StatefulWidget {
  const SignSightApp({
    super.key,
    required this.controller,
    this.mapBuilder = buildSignMap,
    this.devices,
  });
  final AppController controller;
  final MapBuilder mapBuilder;
  final DeviceServices? devices;
  @override
  State<SignSightApp> createState() => _SignSightAppState();
}

class _SignSightAppState extends State<SignSightApp> {
  ThemeMode _theme = ThemeMode.system;
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'SignSight',
    themeMode: _theme,
    theme: signSightTheme(Brightness.light),
    darkTheme: signSightTheme(Brightness.dark),
    home: UserShell(
      controller: widget.controller,
      mapBuilder: widget.mapBuilder,
      devices: widget.devices ?? DeviceServices(),
      theme: _theme,
      onTheme: (v) => setState(() => _theme = v),
    ),
  );
}
