part of '../../app.dart';

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
