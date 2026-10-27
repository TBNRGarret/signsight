import 'package:flutter_test/flutter_test.dart';
import 'package:signsight_user/sign_icons.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('map icons distinguish speed, no entry and unknown class', () async {
    final fifty = await renderSignIcon('P.127 (50)');
    final noEntry = await renderSignIcon('P.102');
    final unknown = await renderSignIcon('Unknown');
    expect(fifty.take(8), [137, 80, 78, 71, 13, 10, 26, 10]);
    expect(noEntry, isNot(orderedEquals(fifty)));
    expect(unknown.length, greaterThan(100));
  });
}
