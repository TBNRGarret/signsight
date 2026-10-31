import 'package:flutter/material.dart';

class ContributionProgress extends StatelessWidget {
  const ContributionProgress({super.key, required this.step});
  final int step;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    const labels = ['Ảnh', 'Kiểm tra', 'Gửi duyệt'];
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: LayoutBuilder(
        builder: (context, constraints) => Stack(
          children: [
            Positioned(
              top: 17,
              left: constraints.maxWidth / 6,
              right: constraints.maxWidth / 6,
              child: Row(
                children: [
                  for (var i = 1; i < labels.length; i++)
                    Expanded(
                      child: Divider(
                        height: 1,
                        color: i <= step
                            ? colors.primary
                            : colors.outlineVariant,
                      ),
                    ),
                ],
              ),
            ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < labels.length; i++)
                  Expanded(
                    child: Semantics(
                      label:
                          'Bước ${i + 1}, ${i < step
                              ? 'đã xong'
                              : i == step
                              ? 'hiện tại'
                              : 'tiếp theo'}',
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: i <= step
                                  ? colors.primary
                                  : colors.surfaceContainerHigh,
                            ),
                            alignment: Alignment.center,
                            child: i < step
                                ? Icon(
                                    Icons.check,
                                    size: 20,
                                    color: colors.onPrimary,
                                  )
                                : Text(
                                    '${i + 1}',
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelLarge
                                        ?.copyWith(
                                          color: i <= step
                                              ? colors.onPrimary
                                              : colors.onSurfaceVariant,
                                        ),
                                  ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            labels[i],
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.labelLarge
                                ?.copyWith(
                                  color: i == step
                                      ? colors.primary
                                      : colors.onSurfaceVariant,
                                ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class AppEmptyState extends StatelessWidget {
  const AppEmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    required this.action,
    required this.onAction,
  });
  final IconData icon;
  final String title, message, action;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 32),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 40, color: Theme.of(context).colorScheme.primary),
        const SizedBox(height: 20),
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          message,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyMedium
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 20),
        FilledButton(
          onPressed: onAction,
          child: Text(action, textAlign: TextAlign.center),
        ),
      ],
    ),
  );
}

class AppNotice extends StatelessWidget {
  const AppNotice({super.key, required this.message, this.error = false});
  final String message;
  final bool error;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: error ? colors.errorContainer : colors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            error ? Icons.error_outline : Icons.info_outline,
            size: 20,
            color: error ? colors.onErrorContainer : colors.onSurfaceVariant,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: error
                    ? colors.onErrorContainer
                    : colors.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
