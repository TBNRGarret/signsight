import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'controller.dart';
import 'device_services.dart';
import 'feedback.dart';
import 'map_canvas.dart';
import 'models.dart';

class SignSightApp extends StatefulWidget {
  const SignSightApp({
    super.key,
    required this.controller,
    this.mapBuilder = buildSignMap,
    this.devices,
  });
  final AppController controller;
  final MapBuilder mapBuilder;
  final DeviceServices? devices;
  @override
  State<SignSightApp> createState() => _SignSightAppState();
}

class _SignSightAppState extends State<SignSightApp> {
  ThemeMode _theme = ThemeMode.system;
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'SignSight',
    themeMode: _theme,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff2563eb)),
      useMaterial3: true,
    ),
    darkTheme: ThemeData(
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xff60a5fa),
        brightness: Brightness.dark,
      ),
      useMaterial3: true,
    ),
    home: UserShell(
      controller: widget.controller,
      mapBuilder: widget.mapBuilder,
      devices: widget.devices ?? DeviceServices(),
      theme: _theme,
      onTheme: (v) => setState(() => _theme = v),
    ),
  );
}

class UserShell extends StatefulWidget {
  const UserShell({
    super.key,
    required this.controller,
    required this.mapBuilder,
    required this.devices,
    required this.theme,
    required this.onTheme,
  });
  final AppController controller;
  final MapBuilder mapBuilder;
  final DeviceServices devices;
  final ThemeMode theme;
  final ValueChanged<ThemeMode> onTheme;
  @override
  State<UserShell> createState() => _UserShellState();
}

class _UserShellState extends State<UserShell> with WidgetsBindingObserver {
  int _tab = 0;
  String? _notice;
  final _query = TextEditingController();
  bool _picking = false;
  String? _loadedUser;
  AppController get c => widget.controller;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    c.addListener(_changed);
  }

  void _changed() {
    if (_loadedUser != c.user?.id) {
      _loadedUser = c.user?.id;
      if (!c.signedIn) {
        _query.clear();
        _notice = null;
      }
      if (c.signedIn) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            unawaited(c.refreshNearby());
            unawaited(_recoverPhoto());
            if (_tab == 2) unawaited(c.loadHistory());
          }
        });
      }
    }
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && c.signedIn && !c.authBusy) {
      unawaited(c.initialize());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    c.removeListener(_changed);
    _query.dispose();
    super.dispose();
  }

  void _message(String text) {
    if (mounted) setState(() => _notice = text);
  }

  Future<void> _account() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (context) => ListenableBuilder(
        listenable: c,
        builder: (context, _) => c.signedIn
            ? Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      c.user!.username,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 20),
                    const Text('Giao diện'),
                    const SizedBox(height: 8),
                    SegmentedButton<ThemeMode>(
                      segments: const [
                        ButtonSegment(
                          value: ThemeMode.system,
                          icon: Icon(Icons.devices),
                          label: Text('Thiết bị'),
                        ),
                        ButtonSegment(
                          value: ThemeMode.light,
                          icon: Icon(Icons.light_mode_outlined),
                          label: Text('Sáng'),
                        ),
                        ButtonSegment(
                          value: ThemeMode.dark,
                          icon: Icon(Icons.dark_mode_outlined),
                          label: Text('Tối'),
                        ),
                      ],
                      selected: {widget.theme},
                      onSelectionChanged: (v) {
                        widget.onTheme(v.single);
                        Navigator.pop(context);
                      },
                    ),
                    const SizedBox(height: 20),
                    OutlinedButton.icon(
                      onPressed: () {
                        Navigator.pop(context);
                        unawaited(c.logout());
                      },
                      icon: const Icon(Icons.logout),
                      label: const Text('Đăng xuất'),
                    ),
                  ],
                ),
              )
            : AuthSheet(controller: c),
      ),
    );
  }

  void _changeTab(int value) {
    setState(() => _tab = value);
    if (value == 2 && c.signedIn) unawaited(c.loadHistory());
  }

  Future<void> _pick(bool camera) async {
    if (_picking || c.captureBusy) return;
    setState(() => _picking = true);
    try {
      await c.pickPhoto(() => widget.devices.pickPhoto(camera));
    } catch (_) {
      _message(
        'Không mở được ảnh/camera. Kiểm tra quyền hoặc chọn ảnh từ thư viện.',
      );
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _recoverPhoto() async {
    try {
      await c.recoverPhoto(widget.devices.recoverPhoto);
    } catch (_) {
      _message('Chưa khôi phục được ảnh từ camera. Chọn lại từ thư viện.');
    }
  }

  Future<void> _gps({bool forDraft = false}) async {
    try {
      final point = await widget.devices.locate();
      if (!mounted || !c.signedIn) return;
      if (forDraft) {
        c.suggestLocation(point);
      } else {
        c.moveCenter(point);
        await c.refreshNearby();
      }
    } catch (error) {
      _message(
        error is StateError
            ? error.message.toString()
            : 'Chưa lấy được vị trí. Bạn có thể chọn điểm trên bản đồ.',
      );
    }
  }

  Future<void> _pickLocation() async {
    final initial = c.draft?.confirmedLocation ?? c.draft?.suggestion;
    final result = await Navigator.of(context).push<GeoPoint>(
      MaterialPageRoute(
        builder: (context) => PinPicker(
          initial: initial,
          fallback: c.center,
          mapBuilder: widget.mapBuilder,
          devices: widget.devices,
        ),
      ),
    );
    if (result != null && mounted) c.confirmLocation(result);
  }

  Future<void> _signList() async {
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SignList(
        controller: c,
        onSelect: (sign) {
          Navigator.pop(context);
          c.selectSign(sign);
        },
      ),
    );
  }

  Future<void> _report(Sign sign) async {
    final success = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ReportPage(
          controller: c,
          sign: sign,
          devices: widget.devices,
          pickLocation: () => Navigator.of(context).push<GeoPoint>(
            MaterialPageRoute(
              builder: (_) => PinPicker(
                fallback: sign.point,
                mapBuilder: widget.mapBuilder,
                devices: widget.devices,
              ),
            ),
          ),
        ),
      ),
    );
    if (success == true) _message('Đã gửi báo cáo, đang chờ duyệt.');
  }

  Future<void> _activity() async {
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => FractionallySizedBox(
        heightFactor: .85,
        child: ActivityPanel(
          controller: c,
          onSign: (id) {
            Navigator.pop(context);
            _changeTab(0);
            c.clearRoute();
            unawaited(c.openSign(id));
          },
        ),
      ),
    );
  }

  Future<void> _mapOptions() async {
    var radius = c.radius, corridor = c.corridor;
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Phạm vi tìm biển',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              DropdownButtonFormField<int>(
                initialValue: radius,
                decoration: const InputDecoration(
                  labelText: 'Bán kính quanh điểm chọn',
                ),
                items: [100, 300, 500, 1000]
                    .map((v) => DropdownMenuItem(value: v, child: Text('$v m')))
                    .toList(),
                onChanged: (v) => update(() => radius = v!),
              ),
              DropdownButtonFormField<int>(
                initialValue: corridor,
                decoration: const InputDecoration(
                  labelText: 'Hành lang mỗi bên tuyến',
                ),
                items: [20, 50, 100]
                    .map((v) => DropdownMenuItem(value: v, child: Text('$v m')))
                    .toList(),
                onChanged: (v) => update(() => corridor = v!),
              ),
              const SizedBox(height: 12),
              const Text(
                'Biển gần tuyến có thể thuộc chiều đường khác. Chọn lại điểm đến để áp dụng hành lang mới.',
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () {
                  c.radius = radius;
                  c.corridor = corridor;
                  Navigator.pop(context);
                  c.clearRoute();
                  unawaited(c.refreshNearby());
                },
                child: const Text('Áp dụng'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: Theme.of(context).colorScheme.surfaceContainerLow,
    child: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600),
        child: Scaffold(
          appBar: AppBar(
            title: const Text('SignSight'),
            actions: [
              if (_tab == 0 && c.signedIn)
                IconButton(
                  tooltip: 'Phạm vi tìm biển',
                  onPressed: _mapOptions,
                  icon: const Icon(Icons.tune),
                ),
              IconButton(
                tooltip: 'Tài khoản',
                onPressed: _account,
                icon: const Icon(Icons.account_circle_outlined),
              ),
              const SizedBox(width: 8),
            ],
          ),
          body: Column(
            children: [
              if (_notice != null)
                MaterialBanner(
                  content: Text(_notice!),
                  actions: [
                    TextButton(
                      onPressed: () => setState(() => _notice = null),
                      child: const Text('Đóng'),
                    ),
                  ],
                ),
              Expanded(
                child: IndexedStack(
                  index: _tab,
                  children: [
                    _map(context),
                    _capture(context),
                    _history(context),
                  ],
                ),
              ),
            ],
          ),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _tab,
            onDestinationSelected: _changeTab,
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.explore_outlined),
                selectedIcon: Icon(Icons.explore),
                label: 'Bản đồ',
              ),
              NavigationDestination(
                icon: Icon(Icons.add_a_photo_outlined),
                selectedIcon: Icon(Icons.add_a_photo),
                label: 'Đóng góp',
              ),
              NavigationDestination(
                icon: Icon(Icons.history),
                label: 'Của tôi',
              ),
            ],
          ),
        ),
      ),
    ),
  );
  Widget _map(BuildContext context) {
    final visible = c.route?.signs ?? c.nearbySigns;
    final selected = c.selectedSign;
    final signs = [
      ...visible,
      if (selected != null && !visible.any((s) => s.id == selected.id))
        selected,
    ];
    return Stack(
      children: [
        Positioned.fill(
          child: widget.mapBuilder(
            context,
            MapScene(
              center: c.center,
              signs: signs,
              route: c.route?.geometry ?? const [],
              onSign: c.selectSign,
              onIdle: (point) {
                if ((point.latitude - c.center.latitude).abs() > .0001 ||
                    (point.longitude - c.center.longitude).abs() > .0001) {
                  c.moveCenter(point);
                  if (c.route == null) unawaited(c.refreshNearby());
                }
              },
            ),
          ),
        ),
        Positioned(
          left: 16,
          right: 16,
          top: 12,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Material(
                elevation: 3,
                borderRadius: BorderRadius.circular(18),
                child: TextField(
                  controller: _query,
                  textInputAction: TextInputAction.search,
                  onSubmitted: (value) {
                    if (c.signedIn) {
                      unawaited(c.search(value));
                    } else {
                      unawaited(_account());
                    }
                  },
                  decoration: InputDecoration(
                    hintText: 'Bạn muốn đi đâu?',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: c.mapBusy
                        ? const Padding(
                            padding: EdgeInsets.all(14),
                            child: SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          )
                        : IconButton(
                            tooltip: 'Tìm điểm đến',
                            onPressed: () {
                              if (c.signedIn) {
                                unawaited(c.search(_query.text));
                              } else {
                                unawaited(_account());
                              }
                            },
                            icon: const Icon(Icons.arrow_forward),
                          ),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.all(16),
                  ),
                ),
              ),
              if (c.places.isNotEmpty)
                Container(
                  margin: const EdgeInsets.only(top: 6),
                  constraints: const BoxConstraints(maxHeight: 230),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: ListView.builder(
                    shrinkWrap: true,
                    itemCount: c.places.length,
                    itemBuilder: (context, i) {
                      final place = c.places[i];
                      return ListTile(
                        dense: true,
                        leading: const Icon(Icons.place_outlined),
                        title: Text(
                          place.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        onTap: () {
                          FocusScope.of(context).unfocus();
                          unawaited(c.routeTo(place));
                        },
                      );
                    },
                  ),
                ),
              if (c.mapError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Material(
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(c.mapError!),
                    ),
                  ),
                ),
            ],
          ),
        ),
        Positioned(
          right: 16,
          bottom: 128,
          child: FloatingActionButton.small(
            heroTag: 'gps',
            tooltip: 'Vị trí của tôi',
            onPressed: c.signedIn ? () => _gps() : _account,
            child: const Icon(Icons.my_location),
          ),
        ),
        Positioned(
          left: 16,
          right: 16,
          bottom: 36,
          child: Material(
            elevation: 4,
            borderRadius: BorderRadius.circular(18),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: !c.signedIn
                  ? Row(
                      children: [
                        const Expanded(
                          child: Text('Đăng nhập để xem biển quanh đây'),
                        ),
                        TextButton(
                          onPressed: _account,
                          child: const Text('Đăng nhập'),
                        ),
                      ],
                    )
                  : c.selectedSign != null
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                c.selectedSign!.code,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                            ),
                            IconButton(
                              tooltip: 'Đóng chi tiết',
                              onPressed: () => c.selectSign(null),
                              icon: const Icon(Icons.close),
                            ),
                          ],
                        ),
                        Text(c.selectedSign!.name),
                        Text(
                          c.selectedSign!.needsConfirmation
                              ? 'Cần xác nhận lại'
                              : 'Đã được duyệt',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        TextButton.icon(
                          onPressed: () => _report(c.selectedSign!),
                          icon: const Icon(Icons.flag_outlined),
                          label: const Text('Báo cáo / xác nhận'),
                        ),
                      ],
                    )
                  : c.route != null
                  ? Row(
                      children: [
                        Expanded(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${(c.route!.distance / 1000).toStringAsFixed(1)} km · ${(c.route!.duration / 60).ceil()} phút',
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              Text(
                                '${c.route!.signs.length} biển gần tuyến · hành lang ${c.corridor} m',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Danh sách biển trên tuyến',
                          onPressed: _signList,
                          icon: const Icon(Icons.list),
                        ),
                        IconButton(
                          tooltip: 'Xóa tuyến',
                          onPressed: c.clearRoute,
                          icon: const Icon(Icons.close),
                        ),
                      ],
                    )
                  : Row(
                      children: [
                        Expanded(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                c.mapBusy
                                    ? 'Đang tìm biển…'
                                    : '${c.nearbyTotal} biển quanh điểm đang xem',
                                style: Theme.of(context).textTheme.titleSmall,
                              ),
                              Text(
                                'Bán kính ${c.radius} m',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Tải lại biển',
                          onPressed: c.mapBusy ? null : () => c.refreshNearby(),
                          icon: const Icon(Icons.refresh),
                        ),
                        IconButton(
                          tooltip: 'Danh sách biển',
                          onPressed: _signList,
                          icon: const Icon(Icons.list),
                        ),
                      ],
                    ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _gate(String message) => Center(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.account_circle_outlined, size: 48),
          const SizedBox(height: 16),
          Text(
            message,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _account,
            child: const Text('Đăng nhập / Đăng ký'),
          ),
        ],
      ),
    ),
  );
  Widget _capture(BuildContext context) {
    if (!c.signedIn) return _gate('Đăng nhập để đóng góp');
    final draft = c.draft;
    final busy = c.captureBusy || _picking;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Thêm biển báo', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 6),
        const Text('Chụp rõ biển, kiểm tra rồi gửi.'),
        const SizedBox(height: 20),
        if (draft == null) ...[
          const Icon(Icons.add_a_photo_outlined, size: 64),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: busy ? null : () => _pick(true),
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Chụp biển báo'),
          ),
          OutlinedButton.icon(
            onPressed: busy ? null : () => _pick(false),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('Chọn từ thư viện'),
          ),
        ] else ...[
          SizedBox(
            height: 230,
            child: CustomPaint(
              foregroundPainter: DetectionPainter(draft),
              child: Image.memory(
                draft.bytes,
                fit: BoxFit.contain,
                errorBuilder: (_, error, stack) => const Center(
                  child: Text('Không hiển thị được ảnh. Chọn ảnh khác.'),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          if (draft.detections.isNotEmpty) ...[
            DropdownButtonFormField<String>(
              initialValue: draft.selectedId,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Biển phát hiện',
                border: OutlineInputBorder(),
              ),
              items: draft.detections
                  .map(
                    (d) => DropdownMenuItem(
                      value: d.id,
                      child: Text(
                        '${d.code} · ${(d.confidence * 100).round()}%',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  )
                  .toList(),
              onChanged: busy
                  ? null
                  : (value) {
                      if (value != null) c.selectDetection(value);
                    },
            ),
            const SizedBox(height: 4),
            Text(draft.selected?.name ?? ''),
            ExpansionTile(
              key: ValueKey('correction-${draft.selectedId}'),
              tilePadding: EdgeInsets.zero,
              title: const Text('Sửa loại biển nếu AI nhận sai'),
              initiallyExpanded: draft.proposedClass != null,
              onExpansionChanged: (open) {
                if (open) c.loadCaptureTypes();
              },
              children: [
                if (c.captureTypesBusy) const LinearProgressIndicator(),
                if (c.captureTypesError != null) ...[
                  Text(c.captureTypesError!),
                  TextButton(
                    onPressed: c.loadCaptureTypes,
                    child: const Text('Tải lại danh mục'),
                  ),
                ],
                if (c.captureTypes.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  DropdownButtonFormField<int>(
                    key: ValueKey(
                      'capture-class-${draft.selectedId}-${draft.proposedClass}',
                    ),
                    initialValue:
                        c.captureTypes.any(
                          (type) =>
                              type.id ==
                              (draft.proposedClass ?? draft.selected?.classId),
                        )
                        ? draft.proposedClass ?? draft.selected?.classId
                        : null,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Loại biển đúng',
                      border: OutlineInputBorder(),
                    ),
                    items: c.captureTypes
                        .map(
                          (type) => DropdownMenuItem(
                            value: type.id,
                            child: Text(
                              '${type.code} · ${type.name}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: busy ? null : c.proposeClass,
                  ),
                  if (draft.proposedClass != null) ...[
                    const SizedBox(height: 12),
                    TextFormField(
                      key: ValueKey(
                        'capture-reason-${draft.selectedId}-${draft.proposedClass}',
                      ),
                      initialValue: draft.correctionReason,
                      enabled: !busy,
                      maxLength: 1000,
                      minLines: 1,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Lý do sửa nhãn',
                        helperText:
                            'Ít nhất 3 ký tự để người duyệt đối chiếu ảnh.',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: c.setCorrectionReason,
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton(
                        onPressed: busy ? null : () => c.proposeClass(null),
                        child: const Text('Dùng lại nhãn AI'),
                      ),
                    ),
                  ],
                ],
              ],
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                draft.proposedClass == null
                    ? 'Đúng biển tôi muốn đóng góp'
                    : 'Tôi đã kiểm tra nhãn vừa sửa',
              ),
              value: draft.labelConfirmed,
              onChanged: busy
                  ? null
                  : (value) => c.confirmLabel(value ?? false),
              controlAffinity: ListTileControlAffinity.leading,
            ),
            const Divider(),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                draft.confirmedLocation == null
                    ? Icons.location_on_outlined
                    : Icons.check_circle_outline,
              ),
              title: Text(
                draft.confirmedLocation == null
                    ? 'Xác nhận vị trí biển'
                    : 'Đã xác nhận vị trí',
              ),
              subtitle: Text(
                draft.confirmedLocation == null
                    ? 'Chạm bản đồ hoặc dùng GPS rồi kiểm tra lại.'
                    : '${draft.confirmedLocation!.latitude.toStringAsFixed(5)}, ${draft.confirmedLocation!.longitude.toStringAsFixed(5)}',
              ),
              trailing: TextButton(
                onPressed: busy ? null : _pickLocation,
                child: const Text('Chọn'),
              ),
            ),
            FilledButton.icon(
              onPressed: c.canSubmit ? c.submitContribution : null,
              icon: const Icon(Icons.send_outlined),
              label: const Text('Gửi đóng góp'),
            ),
          ],
          TextButton.icon(
            onPressed: busy ? null : () => _pick(false),
            icon: const Icon(Icons.photo_outlined),
            label: const Text('Chọn ảnh khác'),
          ),
          if (!busy)
            TextButton(
              onPressed: c.discardDraft,
              child: const Text('Bỏ bản nháp'),
            ),
          if (!busy && draft.detections.isEmpty && c.captureError == null)
            OutlinedButton.icon(
              onPressed: c.retryDetection,
              icon: const Icon(Icons.refresh),
              label: const Text('Tiếp tục nhận diện'),
            ),
        ],
        if (busy)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: LinearProgressIndicator(),
          ),
        if (c.captureError != null) ...[
          Text(
            c.captureError!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
          if (draft != null)
            TextButton.icon(
              onPressed: busy ? null : c.retryDetection,
              icon: const Icon(Icons.refresh),
              label: const Text('Thử nhận diện lại'),
            ),
        ],
        if (c.captureMessage != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Text(c.captureMessage!),
          ),
      ],
    );
  }

  Widget _history(BuildContext context) {
    if (!c.signedIn) return _gate('Theo dõi đóng góp của bạn');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: OutlinedButton.icon(
            onPressed: _activity,
            icon: const Icon(Icons.fact_check_outlined),
            label: const Text('Báo cáo & xác nhận lại'),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  'Đóng góp của tôi',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              IconButton(
                tooltip: 'Tải lại đóng góp',
                onPressed: c.historyBusy
                    ? null
                    : () => c.loadHistory(status: c.historyStatus),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              for (final entry in <String?, String>{
                null: 'Tất cả',
                'pending': 'Chờ duyệt',
                'accepted': 'Đã duyệt',
                'rejected': 'Cần sửa',
              }.entries)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(entry.value),
                    selected: c.historyStatus == entry.key,
                    onSelected: (_) => c.loadHistory(status: entry.key),
                  ),
                ),
            ],
          ),
        ),
        if (c.historyBusy) const LinearProgressIndicator(),
        if (c.historyError != null)
          Padding(
            padding: const EdgeInsets.all(20),
            child: Text(c.historyError!),
          ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () => c.loadHistory(status: c.historyStatus),
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.symmetric(vertical: 12),
              itemCount: c.contributions.isEmpty
                  ? 1
                  : c.contributions.length + 1,
              itemBuilder: (context, index) {
                if (c.contributions.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.all(28),
                    child: Text('Chưa có đóng góp ở trạng thái này.'),
                  );
                }
                if (index == c.contributions.length) {
                  return c.contributions.length < c.historyTotal
                      ? TextButton(
                          onPressed: c.historyBusy
                              ? null
                              : () => c.loadHistory(more: true),
                          child: const Text('Xem thêm'),
                        )
                      : const SizedBox(height: 12);
                }
                final item = c.contributions[index];
                return ListTile(
                  leading: Icon(
                    item.status == 'accepted'
                        ? Icons.check_circle_outline
                        : item.status == 'rejected'
                        ? Icons.edit_outlined
                        : Icons.schedule,
                  ),
                  title: Text(item.code),
                  subtitle: Text(
                    item.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: Text(item.statusLabel),
                  onTap: () => _contributionDetail(item),
                );
              },
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _contributionDetail(Contribution item) async {
    final content = c.api.photoContent(item.imageId);
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => ListenableBuilder(
        listenable: c,
        builder: (context, _) => !c.signedIn
            ? const SizedBox(
                height: 80,
                child: Center(child: Text('Vui lòng đăng nhập lại.')),
              )
            : Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      item.code,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    Text(item.name),
                    const SizedBox(height: 12),
                    SizedBox(
                      height: 200,
                      child: FutureBuilder(
                        future: content,
                        builder: (context, snapshot) {
                          if (snapshot.hasError) {
                            return const Center(
                              child: Text('Chưa tải được ảnh.'),
                            );
                          }
                          if (!snapshot.hasData) {
                            return const Center(
                              child: CircularProgressIndicator(),
                            );
                          }
                          return Image.memory(
                            snapshot.data!,
                            fit: BoxFit.contain,
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(item.statusLabel),
                    if (item.comment?.isNotEmpty == true) Text(item.comment!),
                    if (item.status == 'accepted' && item.signId != null)
                      FilledButton.icon(
                        onPressed: () {
                          Navigator.pop(context);
                          _changeTab(0);
                          c.clearRoute();
                          unawaited(c.openSign(item.signId!));
                        },
                        icon: const Icon(Icons.map_outlined),
                        label: const Text('Xem trên bản đồ'),
                      ),
                  ],
                ),
              ),
      ),
    );
  }
}

class AuthSheet extends StatefulWidget {
  const AuthSheet({super.key, required this.controller});
  final AppController controller;
  @override
  State<AuthSheet> createState() => _AuthSheetState();
}

class _AuthSheetState extends State<AuthSheet> {
  final _username = TextEditingController(),
      _password = TextEditingController(),
      _email = TextEditingController();
  bool _register = false;
  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    await widget.controller.login(
      _username.text,
      _password.text,
      email: _register ? _email.text : null,
    );
    if (mounted && widget.controller.signedIn) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.controller,
    builder: (context, _) => SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        24,
        0,
        24,
        24 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: AutofillGroup(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              _register ? 'Tạo tài khoản' : 'Đăng nhập',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _username,
              autofillHints: const [AutofillHints.username],
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Tên đăng nhập',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            if (_register) ...[
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                decoration: const InputDecoration(
                  labelText: 'Email',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
            ],
            TextField(
              controller: _password,
              obscureText: true,
              autofillHints: [
                _register ? AutofillHints.newPassword : AutofillHints.password,
              ],
              onSubmitted: (_) => _submit(),
              decoration: InputDecoration(
                labelText: 'Mật khẩu',
                helperText: _register ? 'Tối thiểu 10 ký tự' : null,
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            if (widget.controller.authError != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  widget.controller.authError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            FilledButton(
              onPressed: widget.controller.authBusy ? null : _submit,
              child: Text(
                widget.controller.authBusy
                    ? 'Đang kết nối…'
                    : _register
                    ? 'Đăng ký'
                    : 'Đăng nhập',
              ),
            ),
            TextButton(
              onPressed: widget.controller.authBusy
                  ? null
                  : () => setState(() => _register = !_register),
              child: Text(
                _register
                    ? 'Đã có tài khoản? Đăng nhập'
                    : 'Chưa có tài khoản? Đăng ký',
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class PinPicker extends StatefulWidget {
  const PinPicker({
    super.key,
    this.initial,
    required this.fallback,
    required this.mapBuilder,
    required this.devices,
  });
  final GeoPoint? initial;
  final GeoPoint fallback;
  final MapBuilder mapBuilder;
  final DeviceServices devices;
  @override
  State<PinPicker> createState() => _PinPickerState();
}

class _PinPickerState extends State<PinPicker> {
  GeoPoint? _point;
  late GeoPoint _center;
  String? _error;
  @override
  void initState() {
    super.initState();
    _point = widget.initial;
    _center = _point ?? widget.fallback;
  }

  Future<void> _gps() async {
    try {
      final p = await widget.devices.locate();
      if (mounted) {
        setState(() {
          _point = p;
          _center = p;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Chưa lấy được GPS. Chạm bản đồ để đặt vị trí.',
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Vị trí của biển')),
    body: Stack(
      children: [
        Positioned.fill(
          child: widget.mapBuilder(
            context,
            MapScene(
              center: _center,
              pin: _point,
              pinOnly: true,
              onTap: (point) => setState(() => _point = point),
            ),
          ),
        ),
        Positioned(
          right: 16,
          top: 16,
          child: FloatingActionButton.small(
            heroTag: 'pin-gps',
            tooltip: 'Dùng GPS',
            onPressed: _gps,
            child: const Icon(Icons.my_location),
          ),
        ),
        Positioned(
          left: 16,
          right: 16,
          bottom: 24,
          child: Material(
            borderRadius: BorderRadius.circular(18),
            elevation: 4,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    _error ??
                        (_point == null
                            ? 'Chạm bản đồ để đặt biển.'
                            : 'Kiểm tra ghim đúng vị trí biển rồi xác nhận.'),
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: _point == null
                        ? null
                        : () => Navigator.pop(context, _point),
                    child: const Text('Xác nhận vị trí'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    ),
  );
}

class SignList extends StatefulWidget {
  const SignList({super.key, required this.controller, required this.onSelect});
  final AppController controller;
  final ValueChanged<Sign> onSelect;
  @override
  State<SignList> createState() => _SignListState();
}

class _SignListState extends State<SignList> {
  String _filter = 'all';
  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.controller,
    builder: (context, _) {
      final c = widget.controller;
      final all = c.route?.signs ?? c.nearbySigns;
      final signs = all
          .where(
            (s) =>
                _filter == 'all' ||
                _filter == 'speed' && s.code.contains('P.127') ||
                _filter == 'confirm' && s.needsConfirmation,
          )
          .toList();
      return SizedBox(
        height: MediaQuery.sizeOf(context).height * .68,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text(
                c.route == null ? 'Biển quanh điểm đang xem' : 'Biển gần tuyến',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Wrap(
                spacing: 8,
                children: [
                  for (final entry in {
                    'all': 'Tất cả',
                    'speed': 'Tốc độ',
                    'confirm': 'Cần xác nhận',
                  }.entries)
                    ChoiceChip(
                      label: Text(entry.value),
                      selected: _filter == entry.key,
                      onSelected: (_) => setState(() => _filter = entry.key),
                    ),
                ],
              ),
            ),
            if (!c.signedIn)
              const Text('Vui lòng đăng nhập lại.')
            else
              Expanded(
                child: ListView.builder(
                  itemCount: signs.isEmpty ? 1 : signs.length,
                  itemBuilder: (context, i) {
                    if (signs.isEmpty) {
                      return const Padding(
                        padding: EdgeInsets.all(24),
                        child: Text('Chưa có biển phù hợp.'),
                      );
                    }
                    final sign = signs[i];
                    return ListTile(
                      title: Text(sign.code),
                      subtitle: Text(sign.name, maxLines: 2),
                      trailing: Text(
                        sign.distance == null
                            ? ''
                            : '${sign.distance!.round()} m',
                      ),
                      onTap: () => widget.onSelect(sign),
                    );
                  },
                ),
              ),
            if (c.route == null && c.nearbySigns.length < c.nearbyTotal)
              TextButton(
                onPressed: c.mapBusy ? null : () => c.refreshNearby(more: true),
                child: Text(
                  'Xem thêm (${c.nearbySigns.length}/${c.nearbyTotal})',
                ),
              ),
          ],
        ),
      );
    },
  );
}

class DetectionPainter extends CustomPainter {
  DetectionPainter(this.draft);
  final CaptureDraft draft;
  @override
  void paint(Canvas canvas, Size size) {
    final box = draft.selected?.bbox;
    final photo = draft.photo;
    if (box == null || photo == null) return;
    final scale = math.min(
      size.width / photo.width,
      size.height / photo.height,
    );
    final dx = (size.width - photo.width * scale) / 2,
        dy = (size.height - photo.height * scale) / 2;
    canvas.drawRect(
      Rect.fromLTRB(
        dx + box[0] * scale,
        dy + box[1] * scale,
        dx + box[2] * scale,
        dy + box[3] * scale,
      ),
      Paint()
        ..color = Colors.red
        ..strokeWidth = 3
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant DetectionPainter oldDelegate) => true;
}
