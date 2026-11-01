part of '../../app.dart';

extension _CaptureScreen on _UserShellState {
  Widget _capture(BuildContext context) {
    if (!c.signedIn) return _gate('Đăng nhập để đóng góp');
    final draft = c.draft;
    final busy = c.captureBusy || _picking;
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
      children: [
        Text('Thêm biển báo', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(
          'Một bức ảnh rõ. Một vị trí chính xác.',
          style: Theme.of(context).textTheme.bodyLarge
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
        ContributionProgress(
          step: draft == null
              ? 0
              : draft.labelConfirmed && draft.confirmedLocation != null
              ? 2
              : 1,
        ),
        if (draft == null) ...[
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              children: [
                Icon(
                  Icons.add_a_photo_outlined,
                  size: 48,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(height: 16),
                Text(
                  'Bắt đầu từ một bức ảnh',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Giữ trọn biển trong khung hình, tránh mờ hoặc bị che khuất.',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: busy ? null : () => _pick(true),
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Chụp biển báo'),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: busy ? null : () => _pick(false),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('Chọn từ thư viện'),
          ),
          const SizedBox(height: 24),
          const AppNotice(message: 'Chỉ chụp ảnh khi đã dừng xe an toàn.'),
          const SizedBox(height: 12),
          Text(
            'Bạn sẽ kiểm tra nhãn và vị trí trước khi gửi. Biển chỉ xuất hiện trên bản đồ sau khi được duyệt.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ] else ...[
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: ColoredBox(
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              child: SizedBox(
                height: 210,
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
            ),
          ),
          const SizedBox(height: 24),
          if (draft.detections.isNotEmpty) ...[
            Text(
              'Kiểm tra loại biển',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
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
            if (!c.canSubmit)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  !draft.labelConfirmed
                      ? 'Xác nhận loại biển và vị trí để gửi đóng góp.'
                      : 'Còn một bước: xác nhận vị trí của biển.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
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
          AppNotice(message: c.captureError!, error: true),
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
            child: AppNotice(message: c.captureMessage!),
          ),
      ],
    );
  }
}
