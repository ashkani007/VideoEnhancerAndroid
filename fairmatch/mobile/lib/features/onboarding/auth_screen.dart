import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key, required this.register});
  final bool register;

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  DateTime? _dob;
  bool _terms = false, _busy = false, _obscure = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  static int ageOn(DateTime dob, DateTime today) =>
      today.year - dob.year - ((today.month < dob.month || (today.month == dob.month && today.day < dob.day)) ? 1 : 0);

  Future<void> _pickDob() async {
    final now = DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: DateTime(now.year - 25, now.month, now.day),
      firstDate: DateTime(now.year - 100),
      lastDate: now,
      helpText: 'Your date of birth',
      initialEntryMode: DatePickerEntryMode.input,
    );
    if (d != null) setState(() => _dob = d);
  }

  Future<void> _submit() async {
    setState(() => _error = null);
    if (!_form.currentState!.validate()) return;
    if (widget.register) {
      if (_dob == null) return setState(() => _error = 'Please add your date of birth.');
      if (ageOn(_dob!, DateTime.now()) < 18) return setState(() => _error = 'FairMatch is only available to adults aged 18 or older.');
      if (!_terms) return setState(() => _error = 'Please accept the Terms and Privacy Policy to continue.');
    }
    setState(() => _busy = true);
    final session = ref.read(sessionProvider.notifier);
    try {
      if (widget.register) {
        await session.register(_email.text.trim(), _password.text, _dob!);
      } else {
        await session.login(_email.text.trim(), _password.text);
      }
    } on ApiException catch (e) {
      setState(
        () => _error = e.isOffline ? "Can't reach the FairMatch server. You can still try the demo from the welcome screen." : e.message,
      );
    } catch (_) {
      setState(() => _error = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final reg = widget.register;
    return Scaffold(
      appBar: AppBar(),
      body: SafeArea(
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.all(FmSpace.lg),
            children: [
              Text(reg ? 'Create your account' : 'Welcome back', style: context.text.displaySmall),
              const SizedBox(height: FmSpace.xs),
              Text(
                reg ? 'It takes about three minutes. Only the essentials are required.' : 'Sign in to continue.',
                style: context.text.bodyLarge?.copyWith(color: fm.textMuted),
              ),
              const SizedBox(height: FmSpace.xl),
              TextFormField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                decoration: const InputDecoration(labelText: 'Email'),
                validator: (v) => (v == null || !RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(v.trim())) ? 'Enter a valid email' : null,
              ),
              const SizedBox(height: FmSpace.md),
              TextFormField(
                controller: _password,
                obscureText: _obscure,
                autofillHints: [reg ? AutofillHints.newPassword : AutofillHints.password],
                decoration: InputDecoration(
                  labelText: 'Password',
                  helperText: reg ? 'At least 10 characters' : null,
                  suffixIcon: IconButton(
                    tooltip: _obscure ? 'Show password' : 'Hide password',
                    icon: Icon(_obscure ? Icons.visibility_rounded : Icons.visibility_off_rounded),
                    onPressed: () => setState(() => _obscure = !_obscure),
                  ),
                ),
                validator: (v) => (v == null || (reg && v.length < 10) || v.isEmpty)
                    ? (reg ? 'Use at least 10 characters' : 'Enter your password')
                    : null,
              ),
              if (reg) ...[
                const SizedBox(height: FmSpace.md),
                Semantics(
                  button: true,
                  label: 'Date of birth: ${_dob == null ? 'not set' : DateFormat.yMMMMd().format(_dob!)}',
                  excludeSemantics: true,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(FmRadius.md),
                    onTap: _pickDob,
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        labelText: 'Date of birth',
                        helperText: 'Used to confirm you are 18+. Only your age is shown to others.',
                        helperMaxLines: 2,
                      ),
                      child: Text(_dob == null ? 'Select' : DateFormat.yMMMMd().format(_dob!)),
                    ),
                  ),
                ),
                const SizedBox(height: FmSpace.md),
                CheckboxListTile(
                  value: _terms,
                  onChanged: (v) => setState(() => _terms = v ?? false),
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: Text(
                    'I agree to the Terms of Service and Privacy Policy, and confirm I am 18 or older.',
                    style: context.text.bodyMedium,
                  ),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: FmSpace.sm),
                Semantics(
                  liveRegion: true,
                  child: Container(
                    padding: const EdgeInsets.all(FmSpace.sm),
                    decoration: BoxDecoration(color: fm.danger.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(FmRadius.sm)),
                    child: Text(_error!, style: TextStyle(color: fm.danger)),
                  ),
                ),
              ],
              const SizedBox(height: FmSpace.lg),
              FmButton(label: reg ? 'Continue' : 'Sign in', loading: _busy, onPressed: _submit),
            ],
          ),
        ),
      ),
    );
  }
}
