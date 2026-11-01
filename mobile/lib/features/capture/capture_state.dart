part of '../../controller.dart';

class _CaptureState {
  String? captureError;
  String? captureMessage;
  bool captureBusy = false;
  CaptureDraft? draft;
  List<SignType> captureTypes = [];
  bool captureTypesBusy = false;
  String? captureTypesError;
}

extension _CaptureActions on AppController {
  Future<void> _restoreDraft(int version) async {
    if (user == null || draft != null) return;
    final operation = _photoVersion, owner = user!.id;
    _draftOwner = owner;
    try {
      await _draftWrites;
      final raw = await drafts.load(owner);
      if (!_current(version) || operation != _photoVersion || draft != null) {
        return;
      }
      if (raw != null) {
        draft = CaptureDraft.fromJson(raw);
        if (draft!.proposedClass != null) await loadCaptureTypes();
        captureMessage = 'Đã khôi phục bản nháp. Kiểm tra rồi tiếp tục gửi.';
      }
    } catch (_) {
      if (_current(version)) {
        _saveDraft(clearOwner: owner);
        captureError = 'Không đọc được bản nháp cũ. Chọn lại ảnh.';
      }
    }
  }

  void _saveDraft({String? clearOwner}) {
    final owner = clearOwner ?? user?.id;
    if (owner == null) return;
    final value = clearOwner == null ? draft?.toJson() : null;
    _draftWrites = _draftWrites
        .catchError((_) {})
        .then((_) async {
          if (value == null) {
            await drafts.clear(owner);
          } else {
            await drafts.save(owner, value);
          }
        })
        .catchError((Object error) {
          if (user?.id == owner) {
            captureError =
                'Chưa lưu được bản nháp trên thiết bị. Kiểm tra dung lượng.';
            _notify();
          }
        });
  }

  Future<void> _actionChoosePhoto(Uint8List bytes, String name) async {
    if (!signedIn || captureBusy) return;
    if (bytes.length > 10 * 1024 * 1024) {
      captureError = 'Ảnh tối đa 10 MB. Chọn ảnh nhỏ hơn.';
      _notify();
      return;
    }
    final version = _authVersion, operation = ++_photoVersion;
    captureBusy = true;
    captureError = null;
    captureMessage = null;
    draft = CaptureDraft(photo: null, bytes: bytes, name: name);
    _saveDraft();
    _notify();
    try {
      final photo = await api.upload(bytes, name);
      if (!_current(version) || operation != _photoVersion) return;
      draft!.photo = photo;
      draft!.suggestion = photo.exif;
      _saveDraft();
      _notify();
      final sanitized = await api.photoContent(photo.id);
      if (!_current(version) || operation != _photoVersion) return;
      draft!.bytes = sanitized;
      draft!.previewReady = true;
      _saveDraft();
      final result = await api.detect(photo.id);
      if (!_current(version) || operation != _photoVersion) return;
      draft!.detections = result;
      draft!.selectedId = result.firstOrNull?.id;
      _saveDraft();
      if (result.isEmpty) {
        captureMessage = 'Chưa tìm thấy biển. Thử ảnh gần và rõ hơn.';
      }
    } catch (error) {
      if (operation == _photoVersion) {
        await _failure(error, version, (m) => captureError = m);
      }
    } finally {
      if (_current(version) && operation == _photoVersion) {
        captureBusy = false;
        _notify();
      }
    }
  }

  Future<void> _actionPickPhoto(Future<PickedPhoto?> Function() pick) async {
    if (!signedIn || captureBusy) return;
    final version = _authVersion, owner = user!.id;
    var saved = false;
    _draftWrites = _draftWrites
        .catchError((_) {})
        .then((_) async {
          if (_current(version)) {
            await drafts.save('picker', {'owner': owner});
            saved = true;
          }
        })
        .catchError((_) {
          if (_current(version)) {
            captureError =
                'Chưa lưu được bản nháp trên thiết bị. Kiểm tra dung lượng.';
            _notify();
          }
        });
    await _draftWrites;
    if (!_current(version) || !saved) return;
    try {
      final photo = await pick();
      if (photo != null && _current(version)) {
        await choosePhoto(photo.bytes, photo.name);
      }
    } finally {
      if (_current(version)) {
        _draftWrites = _draftWrites
            .catchError((_) {})
            .then((_) => drafts.clear('picker'))
            .catchError((_) {});
        await _draftWrites;
      }
    }
  }

  Future<void> _actionRecoverPhoto(
    Future<PickedPhoto?> Function() recover,
  ) async {
    if (!signedIn || captureBusy) return;
    final version = _authVersion;
    await _draftWrites;
    final marker = await drafts.load('picker');
    if (!_current(version) || marker?['owner'] != user?.id) return;
    await pickPhoto(recover);
  }

  Future<void> _actionRetryDetection() async {
    if (draft == null || captureBusy || !signedIn) return;
    final version = _authVersion, operation = ++_photoVersion;
    captureBusy = true;
    captureError = null;
    captureMessage = null;
    _notify();
    try {
      if (draft!.photo == null) {
        final photo = await api.upload(draft!.bytes, draft!.name);
        if (!_current(version) || operation != _photoVersion) return;
        draft!.photo = photo;
        draft!.suggestion = photo.exif;
        _saveDraft();
      }
      if (!draft!.previewReady) {
        final sanitized = await api.photoContent(draft!.photo!.id);
        if (!_current(version) || operation != _photoVersion) return;
        draft!.bytes = sanitized;
        draft!.previewReady = true;
        _saveDraft();
      }
      final result = await api.detect(draft!.photo!.id);
      if (!_current(version) || operation != _photoVersion) return;
      draft!.detections = result;
      draft!.selectedId = result.firstOrNull?.id;
      draft!.labelConfirmed = false;
      draft!.proposedClass = null;
      draft!.correctionReason = '';
      draft!.confirmedLocation = null;
      _saveDraft();
      if (result.isEmpty) {
        captureMessage = 'Chưa tìm thấy biển. Thử ảnh gần và rõ hơn.';
      }
    } catch (error) {
      if (operation == _photoVersion) {
        await _failure(error, version, (m) => captureError = m);
      }
    } finally {
      if (_current(version) && operation == _photoVersion) {
        captureBusy = false;
        _notify();
      }
    }
  }

  void _actionSelectDetection(String id) {
    if (draft?.selectedId == id) return;
    if (draft?.detections.any((d) => d.id == id) != true) return;
    draft!.selectedId = id;
    draft!.labelConfirmed = false;
    draft!.proposedClass = null;
    draft!.correctionReason = '';
    draft!.confirmedLocation = null;
    _saveDraft();
    _notify();
  }

  Future<void> _actionLoadCaptureTypes() async {
    if (!signedIn || captureTypesBusy || captureTypes.isNotEmpty) return;
    final version = _authVersion;
    captureTypesBusy = true;
    captureTypesError = null;
    _notify();
    try {
      final types = await api.taxonomy();
      if (!_current(version)) return;
      if (types.isEmpty ||
          types.any((type) => type.id < 0) ||
          types.map((type) => type.id).toSet().length != types.length) {
        throw const FormatException('Invalid catalog');
      }
      captureTypes = types;
    } catch (error) {
      await _failure(
        error,
        version,
        (message) =>
            captureTypesError = 'Chưa tải được danh mục biển. Thử lại.',
      );
    } finally {
      if (_current(version)) {
        captureTypesBusy = false;
        _notify();
      }
    }
  }

  void _actionProposeClass(int? id) {
    if (draft?.selected == null || captureBusy) return;
    if (id != null && !captureTypes.any((type) => type.id == id)) return;
    draft!.proposedClass = id == draft!.selected!.classId ? null : id;
    draft!.correctionReason = '';
    draft!.labelConfirmed = false;
    _saveDraft();
    _notify();
  }

  void _actionSetCorrectionReason(String reason) {
    if (draft == null || captureBusy) return;
    draft!.correctionReason = reason;
    draft!.labelConfirmed = false;
    _saveDraft();
    _notify();
  }

  void _actionConfirmLabel(bool value) {
    draft?.labelConfirmed = value;
    _saveDraft();
    _notify();
  }

  void _actionSuggestLocation(GeoPoint point) {
    if (point.valid && draft?.confirmedLocation == null) {
      draft?.suggestion = point;
      _saveDraft();
      _notify();
    }
  }

  void _actionConfirmLocation(GeoPoint point) {
    if (point.valid && draft != null) {
      draft!.suggestion = point;
      draft!.confirmedLocation = point;
      _saveDraft();
      _notify();
    }
  }

  Future<void> _actionSubmitContribution() async {
    if (!canSubmit) return;
    final version = _authVersion, operation = ++_photoVersion;
    final current = draft!;
    captureBusy = true;
    captureError = null;
    _notify();
    try {
      await api.contribute(
        current.photo!.id,
        current.selected!.id,
        current.confirmedLocation!,
        proposedClass: current.proposedClass,
        correctionReason: current.correctionReason.trim(),
      );
      if (!_current(version) || operation != _photoVersion) return;
      draft = null;
      _saveDraft();
      captureMessage = 'Đã gửi đóng góp, đang chờ duyệt.';
    } catch (error) {
      if (operation == _photoVersion) {
        await _failure(error, version, (m) => captureError = m);
      }
    } finally {
      if (_current(version) && operation == _photoVersion) {
        captureBusy = false;
        _notify();
      }
    }
  }

  void _actionDiscardDraft() {
    if (captureBusy) return;
    _photoVersion++;
    draft = null;
    captureError = captureMessage = null;
    _saveDraft();
    _notify();
  }
}
