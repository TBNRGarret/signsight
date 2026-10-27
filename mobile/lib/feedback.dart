import 'package:flutter/material.dart';

import 'controller.dart';
import 'device_services.dart';
import 'models.dart';

/// Evidence is uploaded once; a failed submission retains its image ID for retry.
class ReportPage extends StatefulWidget {
  const ReportPage({
    super.key,
    required this.controller,
    required this.sign,
    required this.devices,
    required this.pickLocation,
  });
  final AppController controller;
  final Sign sign;
  final DeviceServices devices;
  final Future<GeoPoint?> Function() pickLocation;
  @override
  State<ReportPage> createState() => _ReportPageState();
}

class _ReportPageState extends State<ReportPage> {
  final _comment = TextEditingController();
  ReportAction _action = ReportAction.confirmExisting;
  UploadedPhoto? _photo;
  String? _photoName, _error;
  GeoPoint? _point;
  int? _class;
  List<SignType> _types = [];
  bool _busy = false;
  late final String? _owner;
  bool get _sameAccount => _owner != null && c.user?.id == _owner;
  AppController get c => widget.controller;
  @override
  void initState() {
    super.initState();
    _owner = c.user?.id;
    _loadTypes();
  }

  Future<void> _loadTypes() async {
    try {
      final types = await c.api.taxonomy();
      if (mounted && _sameAccount) setState(() => _types = types);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Chưa tải được loại biển. Thử tải lại.');
      }
    }
  }

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _pick(bool camera) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final picked = await widget.devices.pickPhoto(camera);
      if (picked == null || !mounted || !_sameAccount) return;
      final photo = await c.uploadEvidence(picked.bytes, picked.name);
      if (mounted && _sameAccount && photo != null) {
        setState(() {
          _photo = photo;
          _photoName = picked.name;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () =>
              _error = 'Không mở được camera/ảnh. Kiểm tra quyền rồi thử lại.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    if (_photo == null || !_sameAccount) return;
    final success = await c.submitReport(
      widget.sign.id,
      _action,
      _photo!.id,
      _comment.text,
      point: _point,
      proposedClass: _class,
    );
    if (mounted && success) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: c,
    builder: (context, _) => Scaffold(
      appBar: AppBar(title: const Text('Báo cáo biển báo')),
      body: !_sameAccount
          ? const Center(child: Text('Vui lòng đăng nhập lại.'))
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  widget.sign.code,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(widget.sign.name),
                const SizedBox(height: 16),
                DropdownButtonFormField<ReportAction>(
                  initialValue: _action,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Nội dung báo cáo',
                    border: OutlineInputBorder(),
                  ),
                  items: ReportAction.values
                      .map(
                        (a) => DropdownMenuItem(value: a, child: Text(a.label)),
                      )
                      .toList(),
                  onChanged: _busy || c.reportBusy
                      ? null
                      : (a) => setState(() {
                          _action = a!;
                          _point = null;
                          _class = null;
                        }),
                ),
                if (_action == ReportAction.correctClass) ...[
                  const SizedBox(height: 16),
                  if (_types.isEmpty)
                    TextButton(
                      onPressed: _loadTypes,
                      child: const Text('Tải loại biển'),
                    ),
                  DropdownButtonFormField<int>(
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Loại biển đúng',
                    ),
                    items: _types
                        .map(
                          (t) => DropdownMenuItem(
                            value: t.id,
                            child: Text(
                              '${t.code} · ${t.name}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: _busy || c.reportBusy
                        ? null
                        : (v) => setState(() => _class = v),
                  ),
                ],
                if (_action == ReportAction.correctLocation)
                  TextButton.icon(
                    onPressed: _busy || c.reportBusy
                        ? null
                        : () async {
                            final point = await widget.pickLocation();
                            if (mounted && point != null) {
                              setState(() => _point = point);
                            }
                          },
                    icon: const Icon(Icons.edit_location_alt_outlined),
                    label: Text(
                      _point == null
                          ? 'Chọn vị trí đúng'
                          : 'Đã chọn vị trí đúng',
                    ),
                  ),
                const SizedBox(height: 16),
                TextField(
                  controller: _comment,
                  maxLength: 2000,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: 'Mô tả quan sát',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 8),
                const Text('Thêm ảnh hiện trạng để người duyệt kiểm tra.'),
                if (_photoName != null)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.check_circle_outline),
                    title: Text(_photoName!),
                    subtitle: const Text('Đã tải ảnh bằng chứng'),
                  ),
                Wrap(
                  spacing: 8,
                  children: [
                    OutlinedButton.icon(
                      onPressed: _busy || c.reportBusy
                          ? null
                          : () => _pick(true),
                      icon: const Icon(Icons.camera_alt_outlined),
                      label: const Text('Chụp ảnh'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _busy || c.reportBusy
                          ? null
                          : () => _pick(false),
                      icon: const Icon(Icons.photo_library_outlined),
                      label: const Text('Chọn ảnh'),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (_busy || c.reportBusy) const LinearProgressIndicator(),
                if (_error != null || c.reportError != null)
                  Text(
                    _error ?? c.reportError!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed:
                      _busy ||
                          c.reportBusy ||
                          _photo == null ||
                          _comment.text.trim().length < 3 ||
                          _action == ReportAction.correctClass &&
                              _class == null ||
                          _action == ReportAction.correctLocation &&
                              _point == null
                      ? null
                      : _submit,
                  icon: const Icon(Icons.send_outlined),
                  label: const Text('Gửi báo cáo'),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Báo cáo được quản trị viên kiểm tra trước khi cập nhật bản đồ.',
                ),
              ],
            ),
    ),
  );
}

class ActivityPanel extends StatefulWidget {
  const ActivityPanel({
    super.key,
    required this.controller,
    required this.onSign,
  });
  final AppController controller;
  final ValueChanged<String> onSign;
  @override
  State<ActivityPanel> createState() => _ActivityPanelState();
}

class _ActivityPanelState extends State<ActivityPanel> {
  bool _confirm = false;
  AppController get c => widget.controller;
  @override
  void initState() {
    super.initState();
    c.loadReports();
  }

  Future<void> _load({bool more = false}) =>
      _confirm ? c.loadConfirmations(more: more) : c.loadReports(more: more);
  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: c,
    builder: (context, _) => !c.signedIn
        ? const Center(child: Text('Vui lòng đăng nhập lại.'))
        : Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Theo dõi biển báo',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                    IconButton(
                      tooltip: 'Tải lại hoạt động',
                      onPressed: c.feedbackBusy ? null : _load,
                      icon: const Icon(Icons.refresh),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('Báo cáo của tôi')),
                    ButtonSegment(value: true, label: Text('Cần xác nhận')),
                  ],
                  selected: {_confirm},
                  onSelectionChanged: (v) {
                    setState(() => _confirm = v.single);
                    _load();
                  },
                ),
              ),
              if (c.feedbackBusy) const LinearProgressIndicator(),
              if (c.feedbackError != null)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(c.feedbackError!),
                ),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  'Cần xác nhận lại là độ mới của dữ liệu, không phải biển hết hiệu lực pháp lý.',
                ),
              ),
              Expanded(
                child: ListView(
                  children: [
                    if (_confirm && c.confirmations.isEmpty ||
                        !_confirm && c.reports.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(24),
                        child: Text('Chưa có mục nào.'),
                      ),
                    if (_confirm)
                      for (final sign in c.confirmations)
                        ListTile(
                          title: Text(sign.code),
                          subtitle: Text(sign.name),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => widget.onSign(sign.id),
                        ),
                    if (!_confirm)
                      for (final report in c.reports)
                        ListTile(
                          title: Text(report.actionLabel),
                          subtitle: Text(
                            '${report.comment}\n${report.reviewComment ?? ''}',
                          ),
                          isThreeLine: true,
                          trailing: Text(report.statusLabel),
                          onTap: () => widget.onSign(report.signId),
                        ),
                    if (_confirm
                        ? c.confirmations.length < c.confirmationTotal
                        : c.reports.length < c.reportTotal)
                      TextButton(
                        onPressed: c.feedbackBusy
                            ? null
                            : () => _load(more: true),
                        child: const Text('Xem thêm'),
                      ),
                  ],
                ),
              ),
            ],
          ),
  );
}
