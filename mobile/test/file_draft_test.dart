import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:signsight_user/native_draft_io.dart';

void main() {
  test(
    'private file drafts replace atomically, isolate API/account and clear',
    () async {
      final root = await Directory.systemTemp.createTemp('signsight-draft-');
      addTearDown(() => root.delete(recursive: true));
      final store = FileDraftStore('https://one.example', directory: root);
      await store.save('u', {'value': 1});
      await store.save('u', {'value': 2});
      expect(await store.load('u'), {'value': 2});
      expect(await store.load('other'), isNull);
      expect(
        await FileDraftStore('https://two.example', directory: root).load('u'),
        isNull,
      );
      await store.clear('u');
      expect(await store.load('u'), isNull);
      expect(
        await root.list(recursive: true).where((e) => e is File).isEmpty,
        true,
      );
    },
  );
}
