// Run only against tests/browser_server.py, which owns disposable data/inference.
import 'dart:convert';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/device_services.dart';
import 'package:signsight_user/map_canvas.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';
import 'package:http/http.dart' as http;

class FixtureDevice extends DeviceServices {
  @override
  Future<GeoPoint> locate() async => const GeoPoint(10.777, 106.701);
  @override
  Future<PickedPhoto?> recoverPhoto() async => null;
  @override
  Future<PickedPhoto?> pickPhoto(bool camera) async {
    final recorder = ui.PictureRecorder();
    Canvas(
      recorder,
    ).drawRect(const Rect.fromLTWH(0, 0, 64, 64), Paint()..color = Colors.red);
    final picture = recorder.endRecording();
    final image = await picture.toImage(64, 64);
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    picture.dispose();
    return PickedPhoto(data!.buffer.asUint8List(), 'synthetic.png');
  }
}

Future<void> waitFor(WidgetTester tester, bool Function() ready) async {
  for (var i = 0; i < 200; i++) {
    await tester.pump(const Duration(milliseconds: 100));
    if (ready()) return;
  }
  fail('Timed out waiting for native user flow');
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Android authenticated contribution, approval, report and exact map record',
    (tester) async {
      const configured = String.fromEnvironment('SIGNSIGHT_TEST_API');
      if (configured.isEmpty) {
        fail('Set SIGNSIGHT_TEST_API to the disposable browser server');
      }
      final origin = Uri.parse(configured);
      // Never accept the personal runtime on port 8000 for an automated test.
      expect(origin.port, 8765);
      final api = SignSightApi(origin);
      final controller = AppController(api, MemorySessionStore());
      final name = 'native_${DateTime.now().microsecondsSinceEpoch}';
      const password = 'Native-fixture-password-123';
      await api.register(name, '$name@example.com', password);
      MapScene? scene;
      await tester.pumpWidget(
        SignSightApp(
          controller: controller,
          devices: FixtureDevice(),
          mapBuilder: (context, current) {
            scene = current;
            return SignMap(
              scene: current,
              styleString: origin.resolve('/test-map.json').toString(),
            );
          },
        ),
      );
      await tester.tap(find.byTooltip('Tài khoản'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Tên đăng nhập'),
        name,
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Mật khẩu'),
        password,
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Đăng nhập'));
      await waitFor(tester, () => controller.signedIn && !controller.authBusy);
      await tester.pump(const Duration(seconds: 1));
      await tester.tap(find.text('Đóng góp').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Chụp biển báo'));
      await waitFor(
        tester,
        () => controller.draft?.selected != null && !controller.captureBusy,
      );
      await tester.pump();
      await tester.ensureVisible(find.text('Sửa loại biển nếu AI nhận sai'));
      await tester.tap(find.text('Sửa loại biển nếu AI nhận sai'));
      await waitFor(tester, () => controller.captureTypes.isNotEmpty);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byType(DropdownButtonFormField<int>));
      await tester.tap(find.byType(DropdownButtonFormField<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('P.125 ·').last);
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.widgetWithText(TextFormField, 'Lý do sửa nhãn'),
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Lý do sửa nhãn'),
        'Native synthetic correction',
      );
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pumpAndSettle();
      expect(controller.draft!.proposedClass, 3);
      expect(controller.draft!.selected!.classId, 5);
      if (const bool.fromEnvironment('SIGNSIGHT_CAPTURE_VISUALS')) {
        // Capture via adb screencap: converting the Flutter surface can recreate
        // MapLibre platform views and interfere with lifecycle acceptance.
        debugPrint('NATIVE_CORRECTION_PREVIEW_READY');
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(seconds: 8)),
        );
      }
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      await tester.ensureVisible(find.text('Chọn'));
      await tester.tap(find.text('Chọn'));
      await tester.pump(const Duration(seconds: 1));
      await tester.tap(find.byTooltip('Dùng GPS'));
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.text('Xác nhận vị trí'));
      await tester.pump(const Duration(seconds: 1));
      await tester.ensureVisible(find.text('Gửi đóng góp'));
      expect(controller.canSubmit, true);
      await tester.tap(find.text('Gửi đóng góp'));
      await waitFor(
        tester,
        () => controller.draft == null && !controller.captureBusy,
      );
      await controller.loadHistory();
      final observation = controller.contributions.single;
      expect(observation.code, 'P.125');
      final staff = SignSightApi(origin);
      final session = await staff.login(
        'browser_manager',
        'Browser-test-password-123',
      );
      staff.useToken(session.token);
      final reviewed = await http.post(
        origin.resolve('/api/v1/manager/observations/${observation.id}/review'),
        headers: {
          'Authorization': 'Bearer ${session.token}',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'action': 'accept',
          'comment': 'Native synthetic test',
        }),
      );
      expect(reviewed.statusCode, 200);
      final signId = jsonDecode(reviewed.body)['sign_record_id'] as String;
      await controller.loadHistory();
      await tester.tap(find.text('Của tôi').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('P.125'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Xem trên bản đồ'));
      await waitFor(tester, () => controller.selectedSign?.id == signId);
      await tester.pump(const Duration(seconds: 2));
      expect(scene!.signs.map((s) => s.id), contains(signId));
      expect(find.byType(SignMap), findsOneWidget);
      expect(
        find.text('Không thể cập nhật bản đồ. Thử tải lại.'),
        findsNothing,
      );
      await tester.tap(find.text('Báo cáo / xác nhận'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Mô tả quan sát'),
        'Biển vẫn còn - synthetic evidence',
      );
      await tester.ensureVisible(find.text('Chọn ảnh'));
      await tester.tap(find.text('Chọn ảnh'));
      await waitFor(
        tester,
        () => find.text('Đã tải ảnh bằng chứng').evaluate().isNotEmpty,
      );
      await tester.ensureVisible(find.text('Gửi báo cáo'));
      await tester.tap(find.text('Gửi báo cáo'));
      await waitFor(
        tester,
        () => controller.reports.isNotEmpty && !controller.reportBusy,
      );
      expect(controller.reports.single.status, 'pending');
      await controller.logout();
      await controller.flushDraft();
      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
      staff.close();
    },
  );
}
