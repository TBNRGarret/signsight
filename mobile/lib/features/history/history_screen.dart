part of '../../app.dart';

extension _HistoryScreen on _UserShellState {
  Widget _history(BuildContext context) {
    if (!c.signedIn) return _gate('Theo dõi đóng góp của bạn');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 12, 16, 4),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  'Đóng góp của tôi',
                  style: Theme.of(context).textTheme.headlineSmall,
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
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
          child: Text(
            'Ảnh bạn gửi và kết quả từ người duyệt.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: OutlinedButton.icon(
            onPressed: _activity,
            icon: const Icon(Icons.fact_check_outlined),
            label: const Text('Báo cáo & xác nhận lại'),
          ),
        ),
        const SizedBox(height: 16),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              for (final entry in <String?, String>{
                null: 'Tất cả',
                'pending': 'Chờ duyệt',
                'accepted': 'Đã duyệt',
                'rejected': 'Từ chối',
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
                  if (c.historyBusy || c.historyError != null) {
                    return const SizedBox.shrink();
                  }
                  return AppEmptyState(
                    icon: c.historyStatus == null
                        ? Icons.add_photo_alternate_outlined
                        : Icons.filter_alt_off_outlined,
                    title: c.historyStatus == null
                        ? 'Bắt đầu với biển báo đầu tiên'
                        : 'Chưa có đóng góp ở trạng thái này.',
                    message: c.historyStatus == null
                        ? 'Chụp hoặc chọn ảnh biển báo. Kết quả duyệt sẽ xuất hiện tại đây.'
                        : 'Chọn trạng thái khác hoặc xem lại tất cả ảnh đã gửi.',
                    action: c.historyStatus == null
                        ? 'Đóng góp đầu tiên'
                        : 'Xem tất cả đóng góp',
                    onAction: c.historyStatus == null
                        ? () => _changeTab(1)
                        : () => c.loadHistory(),
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
                final colors = Theme.of(context).colorScheme;
                final stateColor = item.status == 'accepted'
                    ? colors.primary
                    : item.status == 'rejected'
                    ? colors.error
                    : colors.onSurfaceVariant;
                return ListTile(
                  leading: Icon(
                    item.status == 'accepted'
                        ? Icons.check_circle_outline
                        : item.status == 'rejected'
                        ? Icons.edit_outlined
                        : Icons.schedule,
                    color: stateColor,
                  ),
                  title: Text(item.code),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.name,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        item.statusLabel,
                        style: Theme.of(context).textTheme.labelMedium
                            ?.copyWith(color: stateColor),
                      ),
                    ],
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _contributionDetail(item),
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}
