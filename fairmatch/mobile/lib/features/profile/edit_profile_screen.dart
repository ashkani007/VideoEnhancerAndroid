import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';
import '../onboarding/choices.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});
  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  MyProfile? _p;
  final _bio = TextEditingController();
  final _promptAnswers = <TextEditingController>[];
  final _promptQuestions = <String>[];
  bool _saving = false;

  static const promptQuestions = [
    'A perfect Sunday',
    "I'm weirdly good at",
    'Green flag I look for',
    "Let's debate",
    'The way to win me over',
    'Something I learned recently',
  ];

  @override
  void initState() {
    super.initState();
    ref.read(meProvider.future).then((me) {
      if (!mounted || me.profile == null) return;
      setState(() {
        _p = me.profile!
          ..lifestyle = Map.of(me.profile!.lifestyle)
          ..communication = Map.of(me.profile!.communication);
        _bio.text = _p!.bio;
        for (final pr in _p!.prompts) {
          _promptQuestions.add(pr.question);
          _promptAnswers.add(TextEditingController(text: pr.answer));
        }
      });
    });
  }

  @override
  void dispose() {
    _bio.dispose();
    for (final c in _promptAnswers) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final p = _p!;
    setState(() => _saving = true);
    try {
      await ref.read(repoProvider).updateProfile({
        'bio': _bio.text.trim(),
        'interests': p.interests,
        'values': p.values,
        'lifestyle': p.lifestyle,
        'communication': p.communication,
        'relationship_intent': p.intent,
        'prompts': [
          for (var i = 0; i < _promptQuestions.length; i++)
            if (_promptAnswers[i].text.trim().isNotEmpty) {'q': _promptQuestions[i], 'a': _promptAnswers[i].text.trim()},
        ],
      });
      ref.invalidate(meProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile saved')));
        Navigator.pop(context);
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _addPhoto() async {
    final f = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 1600, imageQuality: 88);
    if (f == null) return;
    try {
      await ref.read(repoProvider).uploadPhoto(await f.readAsBytes(), f.name);
      final me = await ref.refresh(meProvider.future);
      setState(() => _p!.photos = me.profile?.photos ?? []);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _p;
    return Scaffold(
      appBar: AppBar(title: const Text('Edit profile')),
      body: p == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.xxl), children: [
              Text('Photos', style: context.text.titleLarge),
              const SizedBox(height: FmSpace.sm),
              SizedBox(
                height: 132,
                child: ListView(scrollDirection: Axis.horizontal, children: [
                  for (final ph in p.photos)
                    Padding(
                      padding: const EdgeInsets.only(right: 10),
                      child: Stack(children: [
                        SizedBox(width: 100, height: 132, child: Portrait(name: p.firstName, url: ph.url, borderRadius: FmRadius.md)),
                        Positioned(
                          right: 4,
                          top: 4,
                          child: IconButton.filledTonal(
                            tooltip: 'Remove photo',
                            visualDensity: VisualDensity.compact,
                            onPressed: () async {
                              await ref.read(repoProvider).deletePhoto(ph.id);
                              final me = await ref.refresh(meProvider.future);
                              setState(() => p.photos = me.profile?.photos ?? []);
                            },
                            icon: const Icon(Icons.close_rounded, size: 16),
                          ),
                        ),
                      ]),
                    ),
                  if (p.photos.length < 6)
                    InkWell(
                      onTap: _addPhoto,
                      borderRadius: BorderRadius.circular(FmRadius.md),
                      child: Container(
                        width: 100,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(FmRadius.md),
                          border: Border.all(color: context.fm.accent.withValues(alpha: 0.5), width: 1.5),
                        ),
                        child: Icon(Icons.add_a_photo_rounded, color: context.fm.accent),
                      ),
                    ),
                ]),
              ),
              const SizedBox(height: FmSpace.lg),
              Text('About you', style: context.text.titleLarge),
              const SizedBox(height: FmSpace.sm),
              TextField(controller: _bio, maxLines: 4, maxLength: 600, decoration: const InputDecoration(hintText: 'A few lines about you')),
              const SizedBox(height: FmSpace.md),
              Text('Looking for', style: context.text.titleLarge),
              const SizedBox(height: FmSpace.sm),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final e in intentLabels.entries)
                  ChoiceChip(label: Text(e.value), selected: p.intent == e.key, onSelected: (_) => setState(() => p.intent = e.key)),
              ]),
              const SizedBox(height: FmSpace.lg),
              Text('Prompts', style: context.text.titleLarge),
              for (var i = 0; i < _promptQuestions.length; i++)
                Padding(
                  padding: const EdgeInsets.only(top: FmSpace.sm),
                  child: TextField(
                    controller: _promptAnswers[i],
                    maxLength: 300,
                    decoration: InputDecoration(
                      labelText: _promptQuestions[i],
                      suffixIcon: IconButton(
                        tooltip: 'Remove prompt',
                        icon: const Icon(Icons.delete_outline_rounded),
                        onPressed: () => setState(() {
                          _promptQuestions.removeAt(i);
                          _promptAnswers.removeAt(i).dispose();
                        }),
                      ),
                    ),
                  ),
                ),
              if (_promptQuestions.length < 3)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    icon: const Icon(Icons.add_rounded),
                    label: const Text('Add a prompt'),
                    onPressed: () async {
                      final q = await showModalBottomSheet<String>(
                        context: context,
                        builder: (_) => ListView(shrinkWrap: true, children: [
                          for (final q in promptQuestions.where((q) => !_promptQuestions.contains(q)))
                            ListTile(title: Text(q), onTap: () => Navigator.pop(context, q)),
                        ]),
                      );
                      if (q != null) {
                        setState(() {
                          _promptQuestions.add(q);
                          _promptAnswers.add(TextEditingController());
                        });
                      }
                    },
                  ),
                ),
              const SizedBox(height: FmSpace.lg),
              Text('Interests', style: context.text.titleLarge),
              const SizedBox(height: FmSpace.sm),
              _SetEditor(options: interestOptions, values: p.interests, max: 10, onChanged: (v) => setState(() => p.interests = v)),
              const SizedBox(height: FmSpace.lg),
              Text('Values', style: context.text.titleLarge),
              const SizedBox(height: FmSpace.sm),
              _SetEditor(options: valueOptions, values: p.values, max: 5, onChanged: (v) => setState(() => p.values = v)),
              const SizedBox(height: FmSpace.lg),
              Text('Lifestyle', style: context.text.titleLarge),
              const SizedBox(height: FmSpace.sm),
              QuestionGroup(
                questions: lifestyleQuestions,
                answers: p.lifestyle,
                onChanged: () => setState(() {}),
              ),
              Text('Communication', style: context.text.titleLarge),
              const SizedBox(height: FmSpace.sm),
              QuestionGroup(
                questions: communicationQuestions,
                answers: p.communication,
                onChanged: () => setState(() {}),
              ),
              FmButton(label: 'Save', loading: _saving, onPressed: _save),
            ]),
    );
  }
}

class _SetEditor extends StatelessWidget {
  const _SetEditor({required this.options, required this.values, required this.max, required this.onChanged});
  final List<String> options, values;
  final int max;
  final ValueChanged<List<String>> onChanged;

  @override
  Widget build(BuildContext context) {
    final sel = values.toSet();
    return TagPicker(options: {...options, ...values}.toList(), selected: sel, max: max, onChanged: () => onChanged(sel.toList()));
  }
}
