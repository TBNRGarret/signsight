part of '../../app.dart';

extension _MapScreen on _UserShellState {
  Widget _map(BuildContext context) {
    final signs = c.mapSigns;
    final selected = signs.any((s) => s.id == c.selectedSign?.id)
        ? c.selectedSign
        : null;
    return Stack(
      children: [
        Positioned.fill(
          child: widget.mapBuilder(
            context,
            MapScene(
              center: c.center,
              signs: signs,
              selectedSignId: selected?.id,
              route: c.route?.geometry ?? const [],
              routeFitRevision: c.routeFitRevision,
              routeProgress: _driving.driving ? _journeyProgress : null,
              headingUp: _headingUp,
              userLocation: c.signedIn ? _driving.fix : null,
              userLocationStale: !_driving.fresh,
              followUser:
                  _driving.driving && _driving.following && _driving.fresh,
              followRevision: _driving.followRevision,
              onUserGesture: _driving.browse,
              onSign: (sign) {
                if (_driving.driving) _driving.browse();
                c.selectSign(sign);
              },
              onIdle: (point) {
                if (_driving.driving && _driving.following) return;
                if ((point.latitude - c.center.latitude).abs() > .0001 ||
                    (point.longitude - c.center.longitude).abs() > .0001) {
                  c.moveCenter(point);
                  unawaited(c.refreshNearby());
                }
              },
            ),
          ),
        ),
        if (!_driving.driving)
          Positioned(
            left: 16,
            right: 16,
            top: 12,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Material(
                  elevation: 1,
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(14),
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
                      filled: false,
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: c.mapBusy
                          ? const Padding(
                              padding: EdgeInsets.all(14),
                              child: SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
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
                      enabledBorder: InputBorder.none,
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: BorderSide(
                          color: Theme.of(context).colorScheme.primary,
                          width: 2,
                        ),
                      ),
                      contentPadding: const EdgeInsets.all(16),
                    ),
                  ),
                ),
                if (c.places.isNotEmpty)
                  Container(
                    margin: const EdgeInsets.only(top: 6),
                    constraints: const BoxConstraints(maxHeight: 230),
                    child: Material(
                      color: Theme.of(context).colorScheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      clipBehavior: Clip.antiAlias,
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
        if (_driving.driving)
          Positioned(
            left: 16,
            right: 16,
            top: 12,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Material(
                  elevation: 2,
                  borderRadius: BorderRadius.circular(16),
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Row(
                      children: [
                        Icon(
                          _driving.fresh
                              ? Icons.gps_fixed
                              : Icons.gps_not_fixed,
                          color: _driving.fresh
                              ? Theme.of(context).colorScheme.primary
                              : Theme.of(context).colorScheme.error,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            _driving.busy
                                ? 'Đang tìm vị trí GPS…'
                                : _driving.error ??
                                      (!_driving.fresh
                                          ? 'GPS chưa cập nhật. Vị trí hiển thị là lần cuối.'
                                          : _offRoute
                                          ? 'Bạn đang ngoài tuyến. Chưa tính lại tuyến.'
                                          : 'GPS${_driving.fix?.accuracy == null ? '' : ' · ±${_driving.fix!.accuracy!.round()} m'}'),
                          ),
                        ),
                        if (!_driving.fresh && !_driving.busy)
                          TextButton(
                            onPressed: () => _driving.resume(),
                            child: const Text('Thử lại'),
                          ),
                        Semantics(
                          label: _headingUp ? 'Bắc ở trên' : 'Theo hướng xe',
                          container: true,
                          button: true,
                          onTap: _toggleHeading,
                          excludeSemantics: true,
                          child: Tooltip(
                            message: _headingUp
                                ? 'Bắc ở trên'
                                : 'Theo hướng xe',
                            excludeFromSemantics: true,
                            child: IconButton(
                              onPressed: _toggleHeading,
                              icon: Icon(
                                _headingUp
                                    ? Icons.explore_outlined
                                    : Icons.navigation_outlined,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                if (_driving.fresh &&
                    !_offRoute &&
                    !c.routeSignsBusy &&
                    c.routeSignsError == null &&
                    _journeyProgress != null)
                  _upcomingSign(context),
              ],
            ),
          ),
        if (MediaQuery.viewInsetsOf(context).bottom == 0 && c.places.isEmpty)
          Positioned(
            left: 16,
            right: 16,
            bottom: 28,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (!_driving.driving)
                  Align(
                    alignment: Alignment.centerRight,
                    child: IconButton.filledTonal(
                      tooltip: 'Vị trí của tôi',
                      onPressed: c.signedIn
                          ? () {
                              if (_driving.driving) {
                                _driving.follow();
                              } else {
                                unawaited(_gps());
                              }
                            }
                          : _account,
                      icon: const Icon(Icons.my_location),
                    ),
                  ),
                if (_driving.driving && !_driving.following)
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton.icon(
                      onPressed: _driving.follow,
                      icon: const Icon(Icons.navigation),
                      label: const Text('Theo dõi lại'),
                    ),
                  ),
                const SizedBox(height: 12),
                Material(
                  elevation: 2,
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(16),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      maxHeight: MediaQuery.sizeOf(context).height * .4,
                    ),
                    child: SingleChildScrollView(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: !c.signedIn
                            ? Row(
                                children: [
                                  const Expanded(
                                    child: Text(
                                      'Đăng nhập để xem biển quanh đây',
                                    ),
                                  ),
                                  TextButton(
                                    onPressed: _account,
                                    child: const Text('Đăng nhập'),
                                  ),
                                ],
                              )
                            : selected != null
                            ? Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (c.route != null)
                                    TextButton.icon(
                                      onPressed: () {
                                        c.selectSign(null);
                                        c.showRoute();
                                      },
                                      icon: const Icon(Icons.route),
                                      label: const Text(
                                        'Quay lại tuyến đã chọn',
                                      ),
                                    ),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          c.selectedSign!.code,
                                          style: Theme.of(context)
                                              .textTheme
                                              .titleMedium,
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
                                  ReviewedSignPhoto(
                                    api: c.api,
                                    signId: c.selectedSign!.id,
                                    sessionKey:
                                        '${c.user?.id}:${identityHashCode(c.user)}',
                                  ),
                                  Text(
                                    c.selectedSign!.needsConfirmation
                                        ? 'Cần xác nhận lại'
                                        : 'Đã được duyệt',
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall,
                                  ),
                                  TextButton.icon(
                                    onPressed: () => _report(c.selectedSign!),
                                    icon: const Icon(Icons.flag_outlined),
                                    label: const Text('Báo cáo / xác nhận'),
                                  ),
                                ],
                              )
                            : c.route != null
                            ? _routeSummary(context)
                            : Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          'Biển báo quanh đây',
                                          style: Theme.of(context)
                                              .textTheme
                                              .titleMedium,
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          c.mapBusy
                                              ? 'Đang tìm biển…'
                                              : '${c.nearbyTotal} biển · Bán kính ${c.radius} m',
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodySmall,
                                        ),
                                      ],
                                    ),
                                  ),
                                  IconButton(
                                    tooltip: 'Tải lại biển',
                                    onPressed: c.mapBusy
                                        ? null
                                        : () => c.refreshNearby(),
                                    icon: const Icon(Icons.refresh),
                                  ),
                                ],
                              ),
                      ),
                    ),
                  ),
                ),
                if (c.signedIn && c.route == null && selected == null) ...[
                  const SizedBox(height: 8),
                  FilledButton.icon(
                    onPressed: _signList,
                    icon: const Icon(Icons.format_list_bulleted),
                    label: const Text('Danh sách biển'),
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }

  Widget _routeSummary(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          const Icon(Icons.directions_car, size: 28),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              c.routeDestination == null
                  ? 'Tuyến đã chọn'
                  : 'Đến ${c.routeDestination!.name}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          IconButton(
            tooltip: 'Xóa tuyến',
            onPressed: () {
              _stopDrive();
              c.clearRoute();
            },
            icon: const Icon(Icons.close),
          ),
        ],
      ),
      Text(
        _driving.driving &&
                _driving.fresh &&
                !_offRoute &&
                _journeyProgress != null
            ? 'Còn khoảng ${(_journeyProgress!.remainingMeters / 1000).toStringAsFixed(1)} km'
            : '${(c.route!.distance / 1000).toStringAsFixed(1)} km · ${(c.route!.duration / 60).ceil()} phút',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      Text(
        !_driving.driving
            ? 'Xem trước tuyến'
            : _driving.fresh && !_offRoute && _journeyProgress != null
            ? 'Khoảng cách dọc tuyến đã chọn'
            : 'Toàn tuyến · Ước tính ban đầu',
        style: Theme.of(context).textTheme.bodySmall,
      ),
      Text(
        '${c.route!.signs.length} biển gần tuyến · hành lang ${c.routeAppliedCorridor ?? c.corridor} m',
        style: Theme.of(context).textTheme.bodySmall,
      ),
      if (!_driving.driving && c.userLocation?.usableAt(DateTime.now()) != true)
        const Text(
          'Điểm xuất phát đang là điểm xem trên bản đồ. Bắt đầu sẽ dùng GPS.',
          style: TextStyle(fontSize: 12),
        ),
      if (!_driving.driving && _driving.error != null)
        Text(
          _driving.error!,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      if (c.routeSignsBusy) ...[
        const SizedBox(height: 8),
        const LinearProgressIndicator(),
        const Text('Đang cập nhật biển trên tuyến…'),
      ],
      if (c.routeSignsError != null) ...[
        Text(
          'Chưa cập nhật hành lang ${c.corridor} m: ${c.routeSignsError}',
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
        TextButton(
          onPressed: c.refreshRouteSigns,
          child: const Text('Thử lại biển trên tuyến'),
        ),
      ],
      const SizedBox(height: 8),
      SizedBox(
        width: double.infinity,
        child: _driving.driving
            ? OutlinedButton.icon(
                onPressed: _stopDrive,
                icon: const Icon(Icons.stop_circle_outlined),
                label: const Text('Kết thúc'),
              )
            : FilledButton.icon(
                onPressed: _startingDrive ? null : _startDrive,
                icon: const Icon(Icons.navigation),
                label: const Text('Bắt đầu'),
              ),
      ),
      const SizedBox(height: 4),
      Wrap(
        spacing: 8,
        runSpacing: 4,
        children: [
          OutlinedButton.icon(
            onPressed: _showWholeRoute,
            icon: const Icon(Icons.zoom_out_map),
            label: const Text('Xem toàn tuyến'),
          ),
          TextButton.icon(
            onPressed: _signList,
            icon: const Icon(Icons.list),
            label: const Text('Biển trên tuyến'),
          ),
        ],
      ),
    ],
  );

  Widget _upcomingSign(BuildContext context) {
    final upcoming = _journeyProgress!.upcoming(c.route?.signs ?? const []);
    if (upcoming == null) return const SizedBox.shrink();
    final sign = upcoming.sign;
    final image = _drivingIcons.putIfAbsent(
      '${sign.code}:${sign.name}',
      () => renderSignIcon(sign.code, name: sign.name),
    );
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Material(
        key: const ValueKey('upcoming-sign'),
        elevation: 2,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              FutureBuilder<Uint8List>(
                future: image,
                builder: (context, snapshot) => SizedBox(
                  width: 56,
                  height: 56,
                  child: snapshot.hasData
                      ? Image.memory(
                          snapshot.data!,
                          fit: BoxFit.contain,
                          semanticLabel: sign.name,
                        )
                      : const Icon(Icons.traffic_outlined, size: 40),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      upcoming.meters < 1000
                          ? '${(upcoming.meters / 10).round() * 10} m phía trước'
                          : '${(upcoming.meters / 1000).toStringAsFixed(1)} km phía trước',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      sign.name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      sign.needsConfirmation
                          ? 'Biển gần tuyến · cần xác nhận lại'
                          : 'Biển gần tuyến · kiểm tra chiều/làn',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
