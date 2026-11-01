part of '../app.dart';

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
