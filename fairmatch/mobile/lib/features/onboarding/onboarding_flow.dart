import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';
import 'choices.dart';

/// Progressive, skippable onboarding. Each answer is saved as you go; sensitive and
/// lifestyle questions are optional and explain why they're asked.
class OnboardingFlow extends ConsumerStatefulWidget {
  const OnboardingFlow({super.key});

  @override
  ConsumerState<OnboardingFlow> createState() => _OnboardingFlowState();
}

class _OnboardingFlowState extends ConsumerState<OnboardingFlow> {
  int _step = 0;
  bool _busy = false;
  String? _error;

  // Answers
  final _name = TextEditingController();
  String? _gender;
  bool _showGender = true;
  final Set<String> _interestedIn = {};
  String? _intent;
  ({String label, double lat, double lon})? _location;
  int _distance = 50;
  final Set<String> _interests = {};
  final Map<String, String> _lifestyle = {};
  final Map<String, String> _communication = {};
  final Set<String> _values = {};
  final Map<String, bool> _dealbreakers = {};
  final List<({String id, String url})> _photos = [];

  late final List<_Step> _steps = [
    _Step(
      'What should we call you?',
      'Your first name is shown on your profile.',
      required: true,
      build: _nameStep,
      valid: () => _name.text.trim().isNotEmpty,
      patch: () => {'first_name': _name.text.trim()},
    ),
    _Step(
      'How do you identify?',
      'Used to show you to people looking for someone like you. You decide whether it appears on your profile.',
      required: true,
      build: _genderStep,
      valid: () => _gender != null,
      patch: () => {'gender': _gender, 'show_gender': _showGender},
    ),
    _Step(
      'Who would you like to meet?',
      'Choose all that apply. Matching is always reciprocal — both people must fit each other\'s preferences.',
      required: true,
      build: _interestedStep,
      valid: () => _interestedIn.isNotEmpty,
      patch: () => {'interested_in': _interestedIn.toList()},
    ),
    _Step(
      'What are you looking for?',
      'Shared intentions are the strongest signal we use. You can change this anytime.',
      required: true,
      build: _intentStep,
      valid: () => _intent != null,
      patch: () => {'relationship_intent': _intent},
    ),
    _Step(
      'Where are you based?',
      'We store only an approximate area (about 2 km) and show others a rounded distance — never your exact location.',
      required: true,
      build: _locationStep,
      valid: () => _location != null,
      patch: () => {'latitude': _location!.lat, 'longitude': _location!.lon, 'city_label': _location!.label, 'max_distance_km': _distance},
    ),
    _Step(
      'What do you love doing?',
      'Pick up to 10. Shared interests help start conversations.',
      build: _interestsStep,
      valid: () => true,
      patch: () => {'interests': _interests.toList()},
    ),
    _Step(
      'Your lifestyle',
      'Optional. Helps surface people whose everyday rhythms fit yours.',
      build: _lifestyleStep,
      valid: () => true,
      patch: () => {'lifestyle': _lifestyle},
    ),
    _Step(
      'How do you communicate?',
      'Optional. People with similar styles often find it easier to connect.',
      build: _communicationStep,
      valid: () => true,
      patch: () => {'communication': _communication},
    ),
    _Step(
      'What matters most to you?',
      'Optional. Choose up to 5 values.',
      build: _valuesStep,
      valid: () => true,
      patch: () => {'values': _values.toList()},
    ),
    _Step(
      'Any dealbreakers?',
      'Optional. Dealbreakers are hard filters, so use them sparingly.',
      build: _dealbreakersStep,
      valid: () => true,
      patch: () => {'dealbreakers': _dealbreakers},
    ),
    _Step(
      'Add your photos',
      'Add at least one clear photo of yourself. Location data is removed from every upload.',
      required: true,
      build: _photosStep,
      valid: () => _photos.isNotEmpty || ref.read(sessionProvider).isDemo,
      patch: () => {},
    ),
  ];

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  FairMatchRepository get _repo => ref.read(repoProvider);

  Future<void> _next() async {
    final step = _steps[_step];
    if (!step.valid()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final patch = step.patch();
      Me? me;
      if (patch.isNotEmpty) me = await _repo.updateProfile(patch);
      if (_step == _steps.length - 1) {
        me ??= await _repo.me();
        if (me.profile?.completed ?? false) {
          ref.read(sessionProvider.notifier).onboardingComplete();
        } else {
          setState(() => _error = 'A few required details are still missing.');
        }
      } else {
        setState(() => _step++);
      }
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _skip() => setState(() => _step++);

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final step = _steps[_step];
    final progress = (_step + 1) / _steps.length;
    return PopScope(
      canPop: _step == 0,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && _step > 0) setState(() => _step--);
      },
      child: Scaffold(
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(FmSpace.lg, FmSpace.md, FmSpace.lg, FmSpace.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    if (_step > 0)
                      IconButton(onPressed: () => setState(() => _step--), icon: const Icon(Icons.arrow_back_rounded), tooltip: 'Back')
                    else
                      const SizedBox(width: 48),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: TweenAnimationBuilder<double>(
                          tween: Tween(end: progress),
                          duration: FmMotion.of(context, FmMotion.medium),
                          builder: (_, v, _) => LinearProgressIndicator(
                            value: v,
                            minHeight: 6,
                            backgroundColor: fm.surfaceHigh,
                            valueColor: AlwaysStoppedAnimation(fm.accent),
                            semanticsLabel: 'Step ${_step + 1} of ${_steps.length}',
                          ),
                        ),
                      ),
                    ),
                    SizedBox(
                      width: 64,
                      child: step.required ? null : TextButton(onPressed: _skip, child: const Text('Skip')),
                    ),
                  ],
                ),
                const SizedBox(height: FmSpace.lg),
                Expanded(
                  child: AnimatedSwitcher(
                    duration: FmMotion.of(context, FmMotion.medium),
                    transitionBuilder: (c, a) => FadeTransition(
                      opacity: a,
                      child: SlideTransition(
                        position: Tween(begin: const Offset(0.06, 0), end: Offset.zero).animate(a),
                        child: c,
                      ),
                    ),
                    child: ListView(
                      key: ValueKey(_step),
                      children: [
                        Text(step.title, style: context.text.displaySmall),
                        const SizedBox(height: FmSpace.xs),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.info_outline_rounded, size: 16, color: fm.textMuted),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(step.why, style: context.text.bodyMedium?.copyWith(color: fm.textMuted)),
                            ),
                          ],
                        ),
                        const SizedBox(height: FmSpace.lg),
                        step.build(context),
                      ],
                    ),
                  ),
                ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: FmSpace.sm),
                    child: Text(_error!, style: TextStyle(color: fm.danger)),
                  ),
                FmButton(label: _step == _steps.length - 1 ? 'Finish' : 'Continue', loading: _busy, onPressed: step.valid() ? _next : null),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ------------------------------------------------------------ steps
  Widget _nameStep(BuildContext context) => TextField(
    controller: _name,
    autofocus: true,
    maxLength: 40,
    textCapitalization: TextCapitalization.words,
    style: context.text.headlineSmall,
    decoration: const InputDecoration(hintText: 'First name'),
    onChanged: (_) => setState(() {}),
  );

  Widget _genderStep(BuildContext context) => Column(
    children: [
      ...genders.entries.map((e) => ChoiceTile(label: e.value, selected: _gender == e.key, onTap: () => setState(() => _gender = e.key))),
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        value: _showGender,
        onChanged: (v) => setState(() => _showGender = v),
        title: const Text('Show on my profile'),
      ),
    ],
  );

  Widget _interestedStep(BuildContext context) => Column(
    children: [
      ...{...genders, 'everyone': 'Everyone'}.entries.map(
        (e) => ChoiceTile(
          label: e.value,
          selected: _interestedIn.contains(e.key),
          multi: true,
          onTap: () => setState(() {
            if (e.key == 'everyone') {
              _interestedIn
                ..clear()
                ..add('everyone');
            } else {
              _interestedIn.remove('everyone');
              _interestedIn.contains(e.key) ? _interestedIn.remove(e.key) : _interestedIn.add(e.key);
            }
          }),
        ),
      ),
    ],
  );

  Widget _intentStep(BuildContext context) => Column(
    children: [
      ...intentLabels.entries.map(
        (e) =>
            ChoiceTile(label: e.value, icon: intentIcon(e.key), selected: _intent == e.key, onTap: () => setState(() => _intent = e.key)),
      ),
    ],
  );

  Widget _locationStep(BuildContext context) {
    final fm = context.fm;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        FmButton(
          label: 'Use my approximate location',
          icon: Icons.my_location_rounded,
          secondary: true,
          onPressed: () async {
            try {
              var perm = await Geolocator.checkPermission();
              if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
              if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
                setState(() => _error = 'Location permission denied — choose a city instead.');
                return;
              }
              final pos = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.low));
              setState(() => _location = (label: 'Near you', lat: pos.latitude, lon: pos.longitude));
            } catch (_) {
              setState(() => _error = "Couldn't get your location — choose a city instead.");
            }
          },
        ),
        const SizedBox(height: FmSpace.md),
        Text('Or choose a city', style: context.text.labelMedium),
        const SizedBox(height: FmSpace.xs),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final c in cities)
              ChoiceChip(label: Text(c.label), selected: _location?.label == c.label, onSelected: (_) => setState(() => _location = c)),
          ],
        ),
        if (_location != null) ...[
          const SizedBox(height: FmSpace.md),
          Text('Selected: ${_location!.label}', style: context.text.titleSmall?.copyWith(color: fm.accent)),
        ],
        const SizedBox(height: FmSpace.lg),
        Text('Maximum distance: $_distance km', style: context.text.titleSmall),
        Slider(
          value: _distance.toDouble(),
          min: 5,
          max: 200,
          divisions: 39,
          label: '$_distance km',
          onChanged: (v) => setState(() => _distance = v.round()),
        ),
      ],
    );
  }

  Widget _interestsStep(BuildContext context) =>
      TagPicker(options: interestOptions, selected: _interests, max: 10, onChanged: () => setState(() {}));

  Widget _valuesStep(BuildContext context) => TagPicker(options: valueOptions, selected: _values, max: 5, onChanged: () => setState(() {}));

  Widget _lifestyleStep(BuildContext context) =>
      QuestionGroup(questions: lifestyleQuestions, answers: _lifestyle, onChanged: () => setState(() {}));

  Widget _communicationStep(BuildContext context) =>
      QuestionGroup(questions: communicationQuestions, answers: _communication, onChanged: () => setState(() {}));

  Widget _dealbreakersStep(BuildContext context) => Column(
    children: [
      for (final e in dealbreakerOptions.entries)
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          value: _dealbreakers[e.key] ?? false,
          onChanged: (v) => setState(() => _dealbreakers[e.key] = v),
          title: Text(e.value),
        ),
    ],
  );

  Widget _photosStep(BuildContext context) {
    final fm = context.fm;
    final demo = ref.read(sessionProvider).isDemo;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GridView.count(
          crossAxisCount: 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 0.75,
          children: [
            for (final p in _photos) Portrait(name: _name.text, url: p.url, borderRadius: FmRadius.md),
            if (_photos.length < 6)
              Semantics(
                button: true,
                label: 'Add photo',
                child: InkWell(
                  borderRadius: BorderRadius.circular(FmRadius.md),
                  onTap: _busy ? null : _addPhoto,
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(FmRadius.md),
                      border: Border.all(color: fm.accent.withValues(alpha: 0.5), width: 1.5),
                      color: fm.accent.withValues(alpha: 0.06),
                    ),
                    child: Icon(Icons.add_a_photo_rounded, color: fm.accent),
                  ),
                ),
              ),
          ],
        ),
        if (demo) ...[
          const SizedBox(height: FmSpace.md),
          Text('Demo mode: photos are optional and never uploaded.', style: context.text.bodySmall),
        ],
      ],
    );
  }

  Future<void> _addPhoto() async {
    final file = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 1600, imageQuality: 88);
    if (file == null) return;
    setState(() => _busy = true);
    try {
      await _repo.uploadPhoto(await file.readAsBytes(), file.name);
      final me = await _repo.me();
      setState(() {
        _photos
          ..clear()
          ..addAll(me.profile?.photos ?? const []);
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class _Step {
  _Step(this.title, this.why, {required this.build, required this.valid, required this.patch, this.required = false});
  final String title, why;
  final Widget Function(BuildContext) build;
  final bool Function() valid;
  final Map<String, dynamic> Function() patch;
  final bool required;
}
