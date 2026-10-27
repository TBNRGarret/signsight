abstract class DraftStore {
  Future<Map<String, dynamic>?> load(String owner);
  Future<void> save(String owner, Map<String, dynamic> draft);
  Future<void> clear(String owner);
}

class MemoryDraftStore implements DraftStore {
  final _values = <String, Map<String, dynamic>>{};
  @override
  Future<Map<String, dynamic>?> load(String owner) async => _values[owner];
  @override
  Future<void> save(String owner, Map<String, dynamic> draft) async {
    _values[owner] = draft;
  }

  @override
  Future<void> clear(String owner) async {
    _values.remove(owner);
  }
}
