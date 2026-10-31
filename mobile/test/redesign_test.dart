import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:signsight_user/api.dart';
import 'package:signsight_user/app.dart';
import 'package:signsight_user/controller.dart';
import 'package:signsight_user/models.dart';
import 'package:signsight_user/session_store.dart';

AppController controller() => AppController(
  SignSightApi(
    Uri.parse('https://example.com'),
    client: MockClient(
      (_) async => http.Response('{"items":[],"total":0}', 200),
    ),
  ),
  MemorySessionStore(),
)..user = const UserProfile('u', 'driver', 'user');

Future<void> showApp(WidgetTester tester, AppController c) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    SignSightApp(
      controller: c,
      mapBuilder: (_, scene) => const SizedBox.expand(),
    ),
  );
  await tester.pumpAndSettle();
  addTearDown(() async {
    await tester.pumpWidget(const SizedBox.shrink());
    c.dispose();
  });
}

void main() {
  testWidgets('map summary gives search results and the keyboard room', (
    tester,
  ) async {
    final c = controller();
    await showApp(tester, c);
    expect(find.text('Danh sách biển'), findsOneWidget);
    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(tester.view.resetViewInsets);
    await tester.pumpAndSettle();
    expect(find.text('Danh sách biển'), findsNothing);
    tester.view.resetViewInsets();
    await tester.pumpAndSettle();
    expect(find.text('Danh sách biển'), findsOneWidget);
    c.places = [const Place('p', 'Điểm đến đang tìm', GeoPoint(10.7, 106.7))];
    await tester.pumpWidget(
      SignSightApp(
        controller: c,
        mapBuilder: (_, scene) => const SizedBox.expand(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Điểm đến đang tìm'), findsOneWidget);
    expect(find.text('Danh sách biển'), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('first contribution explains the evidence path before capture', (
    tester,
  ) async {
    final c = controller();
    await showApp(tester, c);
    await tester.tap(find.text('Đóng góp').last);
    await tester.pumpAndSettle();
    expect(find.text('Ảnh'), findsOneWidget);
    expect(find.text('Kiểm tra'), findsOneWidget);
    expect(find.text('Gửi duyệt'), findsOneWidget);
    expect(find.text('Chỉ chụp ảnh khi đã dừng xe an toàn.'), findsOneWidget);
    expect(find.text('Chụp biển báo'), findsOneWidget);
    expect(find.text('Chọn từ thư viện'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('empty history offers a working first contribution action', (
    tester,
  ) async {
    final c = controller();
    await showApp(tester, c);
    await tester.tap(find.text('Của tôi').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Đóng góp đầu tiên'));
    await tester.pumpAndSettle();
    expect(find.text('Chụp biển báo'), findsOneWidget);
    expect(
      tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
      1,
    );
  });

  testWidgets(
    'empty filtered history offers to clear the filter instead of a first contribution',
    (tester) async {
      final c = controller();
      await showApp(tester, c);
      await tester.tap(find.text('Của tôi').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Chờ duyệt').last);
      await tester.pumpAndSettle();
      expect(c.historyStatus, 'pending');
      await tester.tap(find.text('Xem tất cả đóng góp'));
      await tester.pumpAndSettle();
      expect(c.historyStatus, isNull);
    },
  );

  for (final brightness in Brightness.values) {
    testWidgets('capture and empty history fit at large text in $brightness', (
      tester,
    ) async {
      tester.platformDispatcher.textScaleFactorTestValue = 1.3;
      tester.platformDispatcher.platformBrightnessTestValue = brightness;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
      final c = controller();
      await showApp(tester, c);
      for (final tab in ['Đóng góp', 'Của tôi']) {
        await tester.tap(find.text(tab).last);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      }
    });
  }
}
