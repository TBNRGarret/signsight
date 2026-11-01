part of '../app.dart';

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
            title: Text(['SignSight', 'Đóng góp', 'Của tôi'][_tab]),
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
                icon: const Icon(Icons.person_outline),
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
                icon: Icon(Icons.map_outlined),
                selectedIcon: Icon(Icons.map),
                label: 'Bản đồ',
              ),
              NavigationDestination(
                icon: Icon(Icons.add_a_photo_outlined),
                selectedIcon: Icon(Icons.add_a_photo),
                label: 'Đóng góp',
              ),
              NavigationDestination(
                icon: Icon(Icons.inbox_outlined),
                selectedIcon: Icon(Icons.inbox),
                label: 'Của tôi',
              ),
            ],
          ),
        ),
      ),
    ),
  );

  Widget _gate(String message) => Center(
    child: SingleChildScrollView(
      child: AppEmptyState(
        icon: _tab == 1 ? Icons.add_a_photo_outlined : Icons.inbox_outlined,
        title: message,
        message: _tab == 1
            ? 'Góp ảnh biển báo, xác nhận thông tin và theo dõi kết quả duyệt.'
            : 'Xem trạng thái, phản hồi và biển báo từ những ảnh bạn đã gửi.',
        action: 'Đăng nhập / Đăng ký',
        onAction: _account,
      ),
    ),
  );
}
