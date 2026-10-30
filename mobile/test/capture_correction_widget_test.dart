import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:signsight_user/app.dart';

import 'capture_correction_test.dart' show fixture, taxonomy;

void main() {
  for (final scale in [1.0, 1.3]) {
    testWidgets(
      'optional correction uses the server catalog on a narrow phone at text scale $scale',
      (tester) async {
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        tester.platformDispatcher.platformBrightnessTestValue = scale == 1.3
            ? Brightness.dark
            : Brightness.light;
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final c = fixture((_) async => taxonomy());
        c.draft!.bytes = File('../tests/browser/fixtures/sign.png')
            .readAsBytesSync();
        await tester.pumpWidget(
          SignSightApp(
            controller: c,
            mapBuilder: (_, scene) => const SizedBox.expand(),
          ),
        );
        await tester.tap(find.text('Đóng góp').last);
        await tester.pumpAndSettle();
        final edit = find.text('Sửa loại biển nếu AI nhận sai');
        await tester.ensureVisible(edit);
        await tester.tap(edit);
        await tester.pumpAndSettle();
        final select = find.byType(DropdownButtonFormField<int>);
        await tester.ensureVisible(select);
        await tester.tap(select);
        await tester.pumpAndSettle();
        await tester.tap(find.text('FIXTURE.42 · Synthetic extension').last);
        await tester.pumpAndSettle();
        expect(c.draft!.proposedClass, 42);
        expect(c.canSubmit, false);
        final reason = find.widgetWithText(TextFormField, 'Lý do sửa nhãn');
        await tester.ensureVisible(reason);
        await tester.enterText(reason, 'Photo checked');
        await tester.pumpAndSettle();
        await tester.ensureVisible(find.byType(CheckboxListTile));
        await tester.tap(find.byType(CheckboxListTile));
        await tester.pumpAndSettle();
        expect(c.canSubmit, true);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        c.dispose();
      },
    );
  }
  testWidgets(
    'an unknown restored correction cannot crash the selector or be submitted',
    (tester) async {
      final c = fixture((_) async => taxonomy());
      await c.loadCaptureTypes();
      c.draft!.proposedClass = 999;
      c.draft!.correctionReason = 'Old draft';
      c.draft!.bytes = File('../tests/browser/fixtures/sign.png')
          .readAsBytesSync();
      await tester.pumpWidget(
        SignSightApp(
          controller: c,
          mapBuilder: (_, scene) => const SizedBox.expand(),
        ),
      );
      await tester.tap(find.text('Đóng góp').last);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(c.canSubmit, false);
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    },
  );
}
