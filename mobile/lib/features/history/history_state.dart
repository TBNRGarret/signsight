part of '../../controller.dart';

class _HistoryState {
  String? historyError;
  bool historyBusy = false;
  List<Contribution> contributions = [];
  int historyTotal = 0;
  String? historyStatus;
  List<SignReport> reports = [];
  List<Sign> confirmations = [];
  int reportTotal = 0;
  int confirmationTotal = 0;
  bool feedbackBusy = false;
  bool reportBusy = false;
  String? feedbackError;
  String? reportError;
}

extension _HistoryActions on AppController {
  Future<void> _actionLoadHistory({String? status, bool more = false}) async {
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

  Future<void> _actionLoadReports({bool more = false}) =>
      _loadFeedback(false, more);
  Future<void> _actionLoadConfirmations({bool more = false}) =>
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

  Future<UploadedPhoto?> _actionUploadEvidence(
    Uint8List bytes,
    String name,
  ) async {
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

  Future<bool> _actionSubmitReport(
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
}
