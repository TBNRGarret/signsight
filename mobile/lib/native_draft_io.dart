import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:path_provider/path_provider.dart';

import 'draft_store.dart';

DraftStore createDraftStore(String scope) => FileDraftStore(scope);

/// One bounded photo draft per API/account, inside the app's private directory.
class FileDraftStore implements DraftStore {
  FileDraftStore(this.scope, {this.directory});
  final String scope;
  final Directory? directory;
  Future<File> _file(String owner) async {
    final root = directory ?? await getApplicationSupportDirectory();
    final key = sha256.convert(utf8.encode(jsonEncode([scope, owner])));
    return File('${root.path}/drafts/$key.json');
  }

  @override
  Future<Map<String, dynamic>?> load(String owner) async {
    final file = await _file(owner);
    if (!await file.exists()) return null;
    if (await file.length() > 16 * 1024 * 1024) {
      await clear(owner);
      return null;
    }
    try {
      return Map<String, dynamic>.from(
        jsonDecode(await file.readAsString()) as Map,
      );
    } on FormatException {
      await clear(owner);
      return null;
    }
  }

  @override
  Future<void> save(String owner, Map<String, dynamic> draft) async {
    final file = await _file(owner);
    await file.parent.create(recursive: true);
    final temp = File('${file.path}.tmp');
    final raw = jsonEncode(draft);
    if (utf8.encode(raw).length > 16 * 1024 * 1024) {
      throw const FormatException('Draft too large');
    }
    await temp.writeAsString(raw, flush: true);
    await temp.rename(file.path);
  }

  @override
  Future<void> clear(String owner) async {
    final file = await _file(owner);
    for (final target in [file, File('${file.path}.tmp')]) {
      if (await target.exists()) await target.delete();
    }
  }
}
