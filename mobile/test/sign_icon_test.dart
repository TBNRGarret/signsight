import 'package:flutter_test/flutter_test.dart';
import 'package:signsight_user/sign_icons.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('legacy labels must match the reviewed meaning exactly', () async {
    final catalog = await SignIconCatalog.load();
    expect(catalog.resolve('R.301e', name: 'Left or right'), 'unknown');
    expect(
      catalog.resolve('R.301e', name: 'Không phải biển đi vòng sang bên phải'),
      'unknown',
    );
    expect(catalog.resolve('W.245a', name: 'Unknown'), 'unknown');
    expect(catalog.resolve('W.245a'), 'unknown');
    expect(catalog.resolve('W.245a', name: 'Đi chậm'), 'slow_down');
  });
  test(
    'CAR35 speed class uses the same approved image as its legacy speed code',
    () async {
      expect(
        await renderSignIcon('DS.SS.00'),
        orderedEquals(await renderSignIcon('P.127 (40)')),
      );
    },
  );
  test('unrecognized codes share a neutral unknown graphic instead of inventing a road sign', () async {
    expect(
      await renderSignIcon('Unknown'),
      orderedEquals(await renderSignIcon('untrusted/other')),
    );
  });
  test('map icons distinguish speed, no entry and unknown class', () async {
    final fifty = await renderSignIcon('P.127 (50)');
    final noEntry = await renderSignIcon('P.102');
    final unknown = await renderSignIcon('Unknown');
    expect(fifty.take(8), [137, 80, 78, 71, 13, 10, 26, 10]);
    expect(noEntry, isNot(orderedEquals(fifty)));
    expect(unknown.length, greaterThan(100));
  });
}
