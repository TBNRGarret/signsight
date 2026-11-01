part of '../../app.dart';

extension _ContributionDetail on _UserShellState {
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
