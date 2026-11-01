part of '../../app.dart';

extension _MapScreen on _UserShellState {
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
        if (MediaQuery.viewInsetsOf(context).bottom == 0 && c.places.isEmpty)
          Positioned(
            left: 16,
            right: 16,
            bottom: 28,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: IconButton.filledTonal(
                    tooltip: 'Vị trí của tôi',
                    onPressed: c.signedIn ? () => _gps() : _account,
                    icon: const Icon(Icons.my_location),
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
                            ? Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          '${(c.route!.distance / 1000).toStringAsFixed(1)} km · ${(c.route!.duration / 60).ceil()} phút',
                                          style: Theme.of(context)
                                              .textTheme
                                              .titleMedium,
                                        ),
                                        Text(
                                          '${c.route!.signs.length} biển gần tuyến · hành lang ${c.corridor} m',
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodySmall,
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
                if (c.signedIn &&
                    c.route == null &&
                    c.selectedSign == null) ...[
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
}
