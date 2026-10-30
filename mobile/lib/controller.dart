import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'models.dart';
import 'session_store.dart';
import 'draft_store.dart';
import 'device_services.dart';

class AppController extends ChangeNotifier {
  AppController(this.api, this.store, {DraftStore? drafts})
    : drafts = drafts ?? MemoryDraftStore() {
    _sessionChanges = store.changes.listen((_) {
      ++_authVersion;
      api.useToken(null);
      _clearPrivate();
      _notify();
      unawaited(initialize());
    });
  }
  late final StreamSubscription<void> _sessionChanges;
  final SignSightApi api;
  final SessionStore store;
  final DraftStore drafts;
  Future<void> _draftWrites = Future.value();
  String? _draftOwner;
  UserProfile? user;
  String? authError, mapError, captureError, captureMessage, historyError;
  bool authBusy = false,
      mapBusy = false,
      captureBusy = false,
      historyBusy = false;
  GeoPoint center = const GeoPoint(10.7769, 106.7009);
  List<Sign> nearbySigns = [];
  int nearbyTotal = 0;
  int radius = 500;
  List<Place> places = [];
  DrivingRoute? route;
  Sign? selectedSign;
  CaptureDraft? draft;
  List<SignType> captureTypes = [];
  bool captureTypesBusy = false;
  String? captureTypesError;
  List<Contribution> contributions = [];
  int historyTotal = 0;
  String? historyStatus;
  int corridor = 50;
  List<SignReport> reports = [];
  List<Sign> confirmations = [];
  int reportTotal = 0, confirmationTotal = 0;
  bool feedbackBusy = false, reportBusy = false;
  String? feedbackError, reportError;
  int _feedbackVersion = 0;
  int _authVersion = 0, _mapVersion = 0, _photoVersion = 0, _historyVersion = 0;
  bool _disposed = false;
  Future<void> _writes = Future.value();
  bool get signedIn => user != null;
  bool get canSubmit =>
      signedIn &&
      !captureBusy &&
      draft?.photo != null &&
      draft?.previewReady == true &&
      draft?.selected != null &&
      draft!.labelConfirmed &&
      (draft!.proposedClass == null ||
          (captureTypes.any((type) => type.id == draft!.proposedClass) &&
              draft!.correctionReason.trim().length >= 3 &&
              draft!.correctionReason.length <= 1000)) &&
      draft!.confirmedLocation?.valid == true;
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  bool _current(int version) => !_disposed && version == _authVersion;
  Future<void> flushDraft() => _draftWrites;
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

  Future<void> _persist(int version, Session? session) {
    _writes = _writes.catchError((_) {}).then((_) async {
      if (!_current(version)) return;
      if (session == null) {
        await store.clear();
      } else {
        await store.save(session);
      }
    });
    return _writes;
  }

  void _clearPrivate() {
    final owner = user?.id ?? _draftOwner;
    if (owner != null) _saveDraft(clearOwner: owner);
    _draftOwner = null;
    _draftWrites = _draftWrites
        .catchError((_) {})
        .then((_) => drafts.clear('picker'))
        .catchError((_) {});
    _photoVersion++;
    _mapVersion++;
    _historyVersion++;
    _feedbackVersion++;
    user = null;
    draft = null;
    captureTypes = [];
    captureTypesBusy = false;
    captureTypesError = null;
    nearbySigns = [];
    nearbyTotal = 0;
    places = [];
    route = null;
    selectedSign = null;
    contributions = [];
    historyTotal = 0;
    reports = [];
    confirmations = [];
    reportTotal = confirmationTotal = 0;
    feedbackBusy = reportBusy = false;
    feedbackError = reportError = null;
    authBusy = false;
    center = const GeoPoint(10.7769, 106.7009);
    captureBusy = false;
    mapBusy = false;
    historyBusy = false;
    captureError = null;
    captureMessage = null;
    mapError = null;
    historyError = null;
  }

  Future<void> _failure(
    Object error,
    int version,
    void Function(String) setMessage,
  ) async {
    if (!_current(version)) return;
    if (error is ApiFailure && error.status == 401) {
      final next = ++_authVersion;
      api.useToken(null);
      _clearPrivate();
      authError = 'Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục.';
      await _persist(next, null);
    } else {
      setMessage(
        error is ApiFailure
            ? error.message
            : 'Không thể hoàn tất. Vui lòng thử lại.',
      );
    }
    _notify();
  }

  Future<void> initialize() async {
    if (authBusy) return;
    final hadUser = signedIn;
    final version = signedIn ? _authVersion : ++_authVersion;
    authBusy = true;
    authError = null;
    _notify();
    try {
      if (!await store.mayRestore) {
        ++_authVersion;
        api.useToken(null);
        _clearPrivate();
        _notify();
        return;
      }
      final saved = await store.load();
      if (!_current(version)) return;
      _draftOwner = saved?.user.id;
      if (!api.browser &&
          (saved == null || saved.expiresAt.isBefore(DateTime.now().toUtc()))) {
        final next = ++_authVersion;
        api.useToken(null);
        _clearPrivate();
        await _persist(next, null);
        _notify();
        return;
      }
      api.useToken(saved?.token);
      final profile = await api.profile();
      if (!_current(version)) return;
      if (!profile.isUser) {
        if (api.browser) {
          ++_authVersion;
          _clearPrivate();
        } else {
          await logout();
        }
        authError = 'Tài khoản quản trị sử dụng trang web quản lý.';
        _notify();
        return;
      }
      if (user != null && user!.id != profile.id) {
        ++_authVersion;
        _clearPrivate();
      }
      user = profile;
      await _restoreDraft(_authVersion);
      _notify();
    } catch (error) {
      await _failure(error, version, (message) => authError = message);
      if (!hadUser &&
          api.browser &&
          error is ApiFailure &&
          error.status == 401) {
        authError = null;
        _notify();
      }
    } finally {
      if (_current(version)) {
        authBusy = false;
        _notify();
      }
    }
  }

  Future<void> login(String username, String password, {String? email}) async {
    if (authBusy) return;
    final version = ++_authVersion;
    authBusy = true;
    authError = null;
    _notify();
    try {
      if (email != null) {
        await api.register(username.trim(), email.trim(), password);
      }
      final session = await api.login(username.trim(), password);
      if (!_current(version)) return;
      api.useToken(session.token);
      if (!session.user.isUser) {
        await api.logout();
        api.useToken(null);
        authError = 'Tài khoản quản trị sử dụng trang web quản lý.';
        await _persist(version, null);
        return;
      }
      await _persist(version, session);
      if (!_current(version)) return;
      user = session.user;
      await _restoreDraft(version);
    } catch (error) {
      await _failure(error, version, (message) => authError = message);
    } finally {
      if (_current(version)) {
        authBusy = false;
        _notify();
      }
    }
  }

  Future<void> logout() async {
    final revoke = api.logout();
    final version = ++_authVersion;
    api.useToken(null);
    _clearPrivate();
    authBusy = false;
    authError = null;
    _notify();
    try {
      await _persist(version, null);
    } finally {
      try {
        await revoke;
      } catch (_) {}
    }
  }

  Future<void> refreshNearby({bool more = false}) async {
    if (!signedIn || mapBusy) return;
    final version = _authVersion, operation = ++_mapVersion;
    mapBusy = true;
    mapError = null;
    _notify();
    try {
      final page = await api.nearby(
        center.latitude,
        center.longitude,
        radius: radius,
        offset: more ? nearbySigns.length : 0,
      );
      if (!_current(version) || operation != _mapVersion) return;
      nearbySigns = more ? [...nearbySigns, ...page.items] : page.items;
      nearbyTotal = page.total;
    } catch (error) {
      if (operation == _mapVersion) {
        await _failure(error, version, (m) => mapError = m);
      }
    } finally {
      if (_current(version) && operation == _mapVersion) {
        mapBusy = false;
        _notify();
      }
    }
  }

  void moveCenter(GeoPoint point) {
    if (point.valid) {
      center = point;
      _notify();
    }
  }

  Future<void> search(String query) async {
    if (!signedIn) return;
    final cleaned = query.trim();
    if (cleaned.length < 3) {
      mapError = 'Nhập ít nhất 3 ký tự.';
      _notify();
      return;
    }
    final version = _authVersion, operation = ++_mapVersion;
    mapBusy = true;
    mapError = null;
    places = [];
    _notify();
    try {
      final results = await api.search(cleaned);
      if (_current(version) && operation == _mapVersion) {
        places = results;
        if (results.isEmpty) {
          mapError = 'Chưa tìm thấy địa điểm. Thử thêm tên đường hoặc quận.';
        }
      }
    } catch (error) {
      if (operation == _mapVersion) {
        await _failure(error, version, (m) => mapError = m);
      }
    } finally {
      if (_current(version) && operation == _mapVersion) {
        mapBusy = false;
        _notify();
      }
    }
  }

  Future<void> routeTo(Place place) async {
    if (!signedIn) return;
    final version = _authVersion, operation = ++_mapVersion;
    mapBusy = true;
    mapError = null;
    places = [];
    route = null;
    _notify();
    try {
      final result = await api.route(center, place.point, buffer: corridor);
      if (_current(version) && operation == _mapVersion) route = result;
    } catch (error) {
      if (operation == _mapVersion) {
        await _failure(error, version, (m) => mapError = m);
      }
    } finally {
      if (_current(version) && operation == _mapVersion) {
        mapBusy = false;
        _notify();
      }
    }
  }

  void clearRoute() {
    _mapVersion++;
    route = null;
    places = [];
    mapBusy = false;
    _notify();
  }

  void selectSign(Sign? sign) {
    selectedSign = sign;
    _notify();
  }

  Future<void> openSign(String id) async {
    final version = _authVersion;
    try {
      final sign = await api.sign(id);
      if (_current(version)) {
        center = sign.point;
        selectedSign = sign;
        _notify();
      }
    } catch (error) {
      await _failure(error, version, (m) => mapError = m);
    }
  }

  Future<void> choosePhoto(Uint8List bytes, String name) async {
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

  Future<void> pickPhoto(Future<PickedPhoto?> Function() pick) async {
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

  Future<void> recoverPhoto(Future<PickedPhoto?> Function() recover) async {
    if (!signedIn || captureBusy) return;
    final version = _authVersion;
    await _draftWrites;
    final marker = await drafts.load('picker');
    if (!_current(version) || marker?['owner'] != user?.id) return;
    await pickPhoto(recover);
  }

  Future<void> retryDetection() async {
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

  void selectDetection(String id) {
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

  Future<void> loadCaptureTypes() async {
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

  void proposeClass(int? id) {
    if (draft?.selected == null || captureBusy) return;
    if (id != null && !captureTypes.any((type) => type.id == id)) return;
    draft!.proposedClass = id == draft!.selected!.classId ? null : id;
    draft!.correctionReason = '';
    draft!.labelConfirmed = false;
    _saveDraft();
    _notify();
  }

  void setCorrectionReason(String reason) {
    if (draft == null || captureBusy) return;
    draft!.correctionReason = reason;
    draft!.labelConfirmed = false;
    _saveDraft();
    _notify();
  }

  void confirmLabel(bool value) {
    draft?.labelConfirmed = value;
    _saveDraft();
    _notify();
  }

  void suggestLocation(GeoPoint point) {
    if (point.valid && draft?.confirmedLocation == null) {
      draft?.suggestion = point;
      _saveDraft();
      _notify();
    }
  }

  void confirmLocation(GeoPoint point) {
    if (point.valid && draft != null) {
      draft!.suggestion = point;
      draft!.confirmedLocation = point;
      _saveDraft();
      _notify();
    }
  }

  Future<void> submitContribution() async {
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

  void discardDraft() {
    if (captureBusy) return;
    _photoVersion++;
    draft = null;
    captureError = captureMessage = null;
    _saveDraft();
    _notify();
  }

  Future<void> loadHistory({String? status, bool more = false}) async {
    if (!signedIn) return;
    final version = _authVersion, operation = ++_historyVersion;
    historyBusy = true;
    historyError = null;
    if (!more) {
      historyStatus = status;
      contributions = [];
    }
    _notify();
    try {
      final page = await api.history(
        status: historyStatus,
        offset: more ? contributions.length : 0,
      );
      if (!_current(version) || operation != _historyVersion) return;
      contributions = more ? [...contributions, ...page.items] : page.items;
      historyTotal = page.total;
    } catch (error) {
      if (operation == _historyVersion) {
        await _failure(error, version, (m) => historyError = m);
      }
    } finally {
      if (_current(version) && operation == _historyVersion) {
        historyBusy = false;
        _notify();
      }
    }
  }

  Future<void> loadReports({bool more = false}) => _loadFeedback(false, more);
  Future<void> loadConfirmations({bool more = false}) =>
      _loadFeedback(true, more);

  Future<void> _loadFeedback(bool confirm, bool more) async {
    if (!signedIn) return;
    final version = _authVersion, operation = ++_feedbackVersion;
    feedbackBusy = true;
    feedbackError = null;
    _notify();
    try {
      if (confirm) {
        final page = await api.confirmations(
          offset: more ? confirmations.length : 0,
        );
        if (!_current(version) || operation != _feedbackVersion) return;
        confirmations = more ? [...confirmations, ...page.items] : page.items;
        confirmationTotal = page.total;
      } else {
        final page = await api.reports(offset: more ? reports.length : 0);
        if (!_current(version) || operation != _feedbackVersion) return;
        reports = more ? [...reports, ...page.items] : page.items;
        reportTotal = page.total;
      }
    } catch (error) {
      if (operation == _feedbackVersion) {
        await _failure(error, version, (m) => feedbackError = m);
      }
    } finally {
      if (_current(version) && operation == _feedbackVersion) {
        feedbackBusy = false;
        _notify();
      }
    }
  }

  Future<UploadedPhoto?> uploadEvidence(Uint8List bytes, String name) async {
    if (!signedIn || reportBusy) return null;
    final version = _authVersion;
    reportBusy = true;
    reportError = null;
    _notify();
    try {
      if (bytes.length > 10 * 1024 * 1024) {
        throw const ApiFailure(422, 'Ảnh tối đa 10 MB.');
      }
      final photo = await api.upload(bytes, name);
      return _current(version) ? photo : null;
    } catch (error) {
      await _failure(error, version, (m) => reportError = m);
      return null;
    } finally {
      if (_current(version)) {
        reportBusy = false;
        _notify();
      }
    }
  }

  Future<bool> submitReport(
    String signId,
    ReportAction action,
    String imageId,
    String comment, {
    GeoPoint? point,
    int? proposedClass,
  }) async {
    if (!signedIn || reportBusy) return false;
    reportError = null;
    if (comment.trim().length < 3 ||
        action == ReportAction.correctLocation && point?.valid != true ||
        action == ReportAction.correctClass && proposedClass == null) {
      reportError = 'Thêm mô tả, ảnh và thông tin sửa đổi trước khi gửi.';
      _notify();
      return false;
    }
    final version = _authVersion;
    reportBusy = true;
    _notify();
    try {
      final report = await api.report(
        signId,
        action,
        imageId,
        comment,
        point: point,
        proposedClass: proposedClass,
      );
      if (!_current(version)) return false;
      reports = [report, ...reports.where((r) => r.id != report.id)];
      reportTotal++;
      return true;
    } catch (error) {
      await _failure(error, version, (m) => reportError = m);
      return false;
    } finally {
      if (_current(version)) {
        reportBusy = false;
        _notify();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _authVersion++;
    unawaited(_sessionChanges.cancel());
    api.close();
    super.dispose();
  }
}
