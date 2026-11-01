import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'models.dart';
import 'session_store.dart';
import 'draft_store.dart';
import 'device_services.dart';

part 'features/map/map_state.dart';
part 'features/capture/capture_state.dart';
part 'features/history/history_state.dart';

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
  String? authError;
  bool authBusy = false;
  final _mapState = _MapState();
  String? get mapError => _mapState.mapError;
  set mapError(String? value) => _mapState.mapError = value;
  bool get mapBusy => _mapState.mapBusy;
  set mapBusy(bool value) => _mapState.mapBusy = value;
  GeoPoint get center => _mapState.center;
  set center(GeoPoint value) => _mapState.center = value;
  List<Sign> get nearbySigns => _mapState.nearbySigns;
  set nearbySigns(List<Sign> value) => _mapState.nearbySigns = value;
  int get nearbyTotal => _mapState.nearbyTotal;
  set nearbyTotal(int value) => _mapState.nearbyTotal = value;
  int get radius => _mapState.radius;
  set radius(int value) => _mapState.radius = value;
  List<Place> get places => _mapState.places;
  set places(List<Place> value) => _mapState.places = value;
  DrivingRoute? get route => _mapState.route;
  set route(DrivingRoute? value) => _mapState.route = value;
  Sign? get selectedSign => _mapState.selectedSign;
  set selectedSign(Sign? value) => _mapState.selectedSign = value;
  int get corridor => _mapState.corridor;
  set corridor(int value) => _mapState.corridor = value;
  final _captureState = _CaptureState();
  String? get captureError => _captureState.captureError;
  set captureError(String? value) => _captureState.captureError = value;
  String? get captureMessage => _captureState.captureMessage;
  set captureMessage(String? value) => _captureState.captureMessage = value;
  bool get captureBusy => _captureState.captureBusy;
  set captureBusy(bool value) => _captureState.captureBusy = value;
  CaptureDraft? get draft => _captureState.draft;
  set draft(CaptureDraft? value) => _captureState.draft = value;
  List<SignType> get captureTypes => _captureState.captureTypes;
  set captureTypes(List<SignType> value) => _captureState.captureTypes = value;
  bool get captureTypesBusy => _captureState.captureTypesBusy;
  set captureTypesBusy(bool value) => _captureState.captureTypesBusy = value;
  String? get captureTypesError => _captureState.captureTypesError;
  set captureTypesError(String? value) =>
      _captureState.captureTypesError = value;
  final _historyState = _HistoryState();
  String? get historyError => _historyState.historyError;
  set historyError(String? value) => _historyState.historyError = value;
  bool get historyBusy => _historyState.historyBusy;
  set historyBusy(bool value) => _historyState.historyBusy = value;
  List<Contribution> get contributions => _historyState.contributions;
  set contributions(List<Contribution> value) =>
      _historyState.contributions = value;
  int get historyTotal => _historyState.historyTotal;
  set historyTotal(int value) => _historyState.historyTotal = value;
  String? get historyStatus => _historyState.historyStatus;
  set historyStatus(String? value) => _historyState.historyStatus = value;
  List<SignReport> get reports => _historyState.reports;
  set reports(List<SignReport> value) => _historyState.reports = value;
  List<Sign> get confirmations => _historyState.confirmations;
  set confirmations(List<Sign> value) => _historyState.confirmations = value;
  int get reportTotal => _historyState.reportTotal;
  set reportTotal(int value) => _historyState.reportTotal = value;
  int get confirmationTotal => _historyState.confirmationTotal;
  set confirmationTotal(int value) => _historyState.confirmationTotal = value;
  bool get feedbackBusy => _historyState.feedbackBusy;
  set feedbackBusy(bool value) => _historyState.feedbackBusy = value;
  bool get reportBusy => _historyState.reportBusy;
  set reportBusy(bool value) => _historyState.reportBusy = value;
  String? get feedbackError => _historyState.feedbackError;
  set feedbackError(String? value) => _historyState.feedbackError = value;
  String? get reportError => _historyState.reportError;
  set reportError(String? value) => _historyState.reportError = value;
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

  Future<void> refreshNearby({bool more = false}) =>
      _actionRefreshNearby(more: more);
  void moveCenter(GeoPoint point) => _actionMoveCenter(point);
  Future<void> search(String query) => _actionSearch(query);
  Future<void> routeTo(Place place) => _actionRouteTo(place);
  void clearRoute() => _actionClearRoute();
  void selectSign(Sign? sign) => _actionSelectSign(sign);
  Future<void> openSign(String id) => _actionOpenSign(id);
  Future<void> choosePhoto(Uint8List bytes, String name) =>
      _actionChoosePhoto(bytes, name);
  Future<void> pickPhoto(Future<PickedPhoto?> Function() pick) =>
      _actionPickPhoto(pick);
  Future<void> recoverPhoto(Future<PickedPhoto?> Function() recover) =>
      _actionRecoverPhoto(recover);
  Future<void> retryDetection() => _actionRetryDetection();
  void selectDetection(String id) => _actionSelectDetection(id);
  Future<void> loadCaptureTypes() => _actionLoadCaptureTypes();
  void proposeClass(int? id) => _actionProposeClass(id);
  void setCorrectionReason(String reason) => _actionSetCorrectionReason(reason);
  void confirmLabel(bool value) => _actionConfirmLabel(value);
  void suggestLocation(GeoPoint point) => _actionSuggestLocation(point);
  void confirmLocation(GeoPoint point) => _actionConfirmLocation(point);
  Future<void> submitContribution() => _actionSubmitContribution();
  void discardDraft() => _actionDiscardDraft();
  Future<void> loadHistory({String? status, bool more = false}) =>
      _actionLoadHistory(status: status, more: more);
  Future<void> loadReports({bool more = false}) =>
      _actionLoadReports(more: more);
  Future<void> loadConfirmations({bool more = false}) =>
      _actionLoadConfirmations(more: more);
  Future<UploadedPhoto?> uploadEvidence(Uint8List bytes, String name) =>
      _actionUploadEvidence(bytes, name);
  Future<bool> submitReport(
    String signId,
    ReportAction action,
    String imageId,
    String comment, {
    GeoPoint? point,
    int? proposedClass,
  }) => _actionSubmitReport(
    signId,
    action,
    imageId,
    comment,
    point: point,
    proposedClass: proposedClass,
  );

  @override
  void dispose() {
    _disposed = true;
    _authVersion++;
    unawaited(_sessionChanges.cancel());
    api.close();
    super.dispose();
  }
}
