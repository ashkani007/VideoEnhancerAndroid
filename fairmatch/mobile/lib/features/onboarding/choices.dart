import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/theme.dart';

const genders = {'woman': 'Woman', 'man': 'Man', 'nonbinary': 'Non-binary', 'other': 'Another identity'};

const cities = [
  (label: 'Amsterdam', lat: 52.3676, lon: 4.9041),
  (label: 'Berlin', lat: 52.52, lon: 13.405),
  (label: 'Brussels', lat: 50.8503, lon: 4.3517),
  (label: 'Dublin', lat: 53.3498, lon: -6.2603),
  (label: 'Lisbon', lat: 38.7223, lon: -9.1393),
  (label: 'London', lat: 51.5072, lon: -0.1276),
  (label: 'Madrid', lat: 40.4168, lon: -3.7038),
  (label: 'Paris', lat: 48.8566, lon: 2.3522),
  (label: 'Rome', lat: 41.9028, lon: 12.4964),
  (label: 'Stockholm', lat: 59.3293, lon: 18.0686),
  (label: 'Vienna', lat: 48.2082, lon: 16.3738),
  (label: 'Warsaw', lat: 52.2297, lon: 21.0122),
];

const interestOptions = [
  'hiking', 'climbing', 'running', 'yoga', 'cycling', 'football', 'surfing', 'dancing', 'cooking', 'baking', 'coffee', 'tea',
  'wine', 'film', 'theatre', 'museums', 'books', 'poetry', 'photography', 'design', 'ceramics', 'gardening', 'board games',
  'chess', 'gaming', 'jazz', 'vinyl', 'festivals', 'music production', 'travel', 'languages', 'volunteering',
];

const valueOptions = [
  'honesty', 'kindness', 'humour', 'family', 'ambition', 'curiosity', 'growth', 'loyalty', 'adventure', 'creativity',
  'independence', 'faith', 'community', 'sustainability',
];

const lifestyleQuestions = {
  'smoking': ('Smoking', {'never': 'Never', 'sometimes': 'Sometimes', 'regularly': 'Regularly'}),
  'drinking': ('Drinking', {'never': 'Never', 'rarely': 'Rarely', 'socially': 'Socially', 'often': 'Often'}),
  'exercise': ('Exercise', {'rarely': 'Rarely', 'sometimes': 'Sometimes', 'often': 'Often'}),
  'kids_want': ('Children in the future', {'yes': 'Want', 'open': 'Open', 'no': "Don't want"}),
  'pets': ('Pets', {'dog': 'Dog person', 'cat': 'Cat person', 'open': 'Love all', 'none': 'No pets'}),
};

const communicationQuestions = {
  'texting': ('Texting', {'often': 'Throughout the day', 'flexible': 'Flexible', 'rarely': 'Prefer meeting up'}),
  'calls': ('Calls', {'love': 'Love a call', 'flexible': 'Sometimes', 'rarely': 'Rarely'}),
  'conflict': ('In disagreements I…', {'talk': 'Talk it out now', 'space': 'Need space first', 'flexible': 'Depends'}),
  'planning': ('Plans', {'planner': 'Planner', 'spontaneous': 'Spontaneous', 'flexible': 'Bit of both'}),
};

const dealbreakerOptions = {
  'no_smokers': 'Only show non-smokers',
  'must_want_kids': 'Only people who want children',
  'must_not_want_kids': "Only people who don't want children",
  'verified_only': 'Only photo-verified people',
};

class ChoiceTile extends StatelessWidget {
  const ChoiceTile({super.key, required this.label, required this.selected, required this.onTap, this.icon, this.multi = false});
  final String label;
  final bool selected, multi;
  final VoidCallback onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Semantics(
        selected: selected,
        button: true,
        child: InkWell(
          borderRadius: BorderRadius.circular(FmRadius.md),
          onTap: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          child: AnimatedContainer(
            duration: FmMotion.of(context, FmMotion.fast),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
            decoration: BoxDecoration(
              color: selected ? fm.accent.withValues(alpha: 0.14) : fm.surface,
              borderRadius: BorderRadius.circular(FmRadius.md),
              border: Border.all(color: selected ? fm.accent : fm.stroke, width: selected ? 1.6 : 1),
            ),
            child: Row(children: [
              if (icon != null) ...[Icon(icon, color: selected ? fm.accent : fm.textMuted, size: 20), const SizedBox(width: 12)],
              Expanded(child: Text(label, style: context.text.titleMedium)),
              Icon(
                selected
                    ? (multi ? Icons.check_box_rounded : Icons.radio_button_checked_rounded)
                    : (multi ? Icons.check_box_outline_blank_rounded : Icons.radio_button_unchecked_rounded),
                color: selected ? fm.accent : fm.textMuted,
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class TagPicker extends StatelessWidget {
  const TagPicker({super.key, required this.options, required this.selected, required this.max, required this.onChanged});
  final List<String> options;
  final Set<String> selected;
  final int max;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${selected.length} of $max selected', style: context.text.bodySmall),
        const SizedBox(height: FmSpace.sm),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final o in options)
            FilterChip(
              label: Text(o),
              selected: selected.contains(o),
              onSelected: (v) {
                if (v && selected.length >= max) return;
                v ? selected.add(o) : selected.remove(o);
                onChanged();
              },
            ),
        ]),
      ]);
}

class QuestionGroup extends StatelessWidget {
  const QuestionGroup({super.key, required this.questions, required this.answers, required this.onChanged});
  final Map<String, (String, Map<String, String>)> questions;
  final Map<String, String> answers;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        for (final q in questions.entries) ...[
          Text(q.value.$1, style: context.text.titleSmall),
          const SizedBox(height: FmSpace.xs),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final o in q.value.$2.entries)
              ChoiceChip(
                label: Text(o.value),
                selected: answers[q.key] == o.key,
                onSelected: (v) {
                  v ? answers[q.key] = o.key : answers.remove(q.key);
                  onChanged();
                },
              ),
          ]),
          const SizedBox(height: FmSpace.lg),
        ],
      ]);
}
