import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../state/billing.dart';
import '../../state/providers.dart';
import '../../widgets/common.dart';

class SubscriptionScreen extends ConsumerStatefulWidget {
  const SubscriptionScreen({super.key});
  @override
  ConsumerState<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends ConsumerState<SubscriptionScreen> {
  StreamSubscription<String>? _sub;
  Map<String, ProductDetails> _store = {};
  String? _busy;

  static const _plans = {
    'fairmatch_plus_monthly': (
      'Plus',
      Icons.workspace_premium_rounded,
      ['15 positive selections a day', 'See and answer people who chose you', 'Advanced preference filters', 'Profile analytics'],
    ),
    'fairmatch_premium_ai_monthly': (
      'Premium AI',
      Icons.auto_awesome,
      ['Everything in Plus', 'AI compatibility insights', 'Conversation starters & writing help', 'Personal preference reflections'],
    ),
  };

  @override
  void initState() {
    super.initState();
    final billing = ref.read(billingProvider);
    _sub = billing.status.listen((m) {
      if (mounted) {
        setState(() => _busy = null);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
      }
    });
    billing
        .storeProducts({..._plans.keys, 'fairmatch_boost_30m'})
        .then((p) => mounted ? setState(() => _store = p) : null)
        .catchError((_) {});
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  Future<void> _buy(String id, {bool consumable = false}) async {
    final demo = ref.read(sessionProvider).isDemo;
    if (demo) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Demo purchase'),
          content: const Text('This is a simulated purchase in demo mode. No payment is taken.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Simulate')),
          ],
        ),
      );
      if (ok != true) return;
    }
    setState(() => _busy = id);
    try {
      await ref.read(billingProvider).buy(id, consumable: consumable, details: _store[id]);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      setState(() => _busy = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    final me = ref.watch(meProvider).value;
    final products = ref.watch(productsProvider).value ?? const <Product>[];
    String price(String id) {
      final store = _store[id];
      if (store != null) return store.price;
      final p = products.where((p) => p.id == id).firstOrNull;
      return p == null ? '' : '€${p.price}';
    }

    final tier = me?.entitlements.tier ?? 'free';
    return Scaffold(
      appBar: AppBar(title: const Text('FairMatch plans')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(FmSpace.md, 0, FmSpace.md, FmSpace.xxl),
        children: [
          Text('Upgrade if it helps — never because you have to.', style: context.text.headlineSmall),
          const SizedBox(height: FmSpace.xs),
          Text(
            'Matching, messaging and every safety feature stay free. Paid plans never override anyone\'s preferences or '
            'buy you a match.',
            style: context.text.bodyMedium?.copyWith(color: fm.textMuted),
          ),
          const SizedBox(height: FmSpace.lg),
          for (final e in _plans.entries) ...[
            _PlanTile(
              name: e.value.$1,
              icon: e.value.$2,
              features: e.value.$3,
              price: price(e.key),
              current: (e.key.contains('plus') && tier == 'plus') || (e.key.contains('premium') && tier == 'premium_ai'),
              busy: _busy == e.key,
              onBuy: () => _buy(e.key),
            ),
            const SizedBox(height: FmSpace.md),
          ],
          Container(
            padding: const EdgeInsets.all(FmSpace.lg),
            decoration: BoxDecoration(
              color: fm.surface,
              borderRadius: BorderRadius.circular(FmRadius.xl),
              border: Border.all(color: fm.stroke),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.bolt_rounded, color: fm.warning),
                    const SizedBox(width: 8),
                    Expanded(child: Text('Profile Boost · 30 min', style: context.text.titleLarge)),
                    Text(price('fairmatch_boost_30m'), style: context.text.titleMedium),
                  ],
                ),
                const SizedBox(height: FmSpace.xs),
                Text(
                  'Shown a little more often to people who already fit your preferences. Boosted cards are labelled “Promoted”, '
                  'are capped at 10% of recommendations, and never guarantee a match.',
                  style: context.text.bodySmall,
                ),
                const SizedBox(height: FmSpace.md),
                FmButton(
                  label: me?.boostActiveUntil != null ? 'Boost active' : 'Boost my profile',
                  secondary: true,
                  loading: _busy == 'fairmatch_boost_30m',
                  onPressed: me?.boostActiveUntil != null ? null : () => _buy('fairmatch_boost_30m', consumable: true),
                ),
              ],
            ),
          ),
          const SizedBox(height: FmSpace.lg),
          Center(
            child: TextButton(onPressed: () => ref.read(billingProvider).restore(), child: const Text('Restore purchases')),
          ),
          Text(
            'Subscriptions renew monthly until cancelled. Cancel anytime in Google Play → Payments & subscriptions; '
            'you keep access until the end of the period you paid for. Prices include VAT where applicable.',
            style: context.text.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _PlanTile extends StatelessWidget {
  const _PlanTile({
    required this.name,
    required this.icon,
    required this.features,
    required this.price,
    required this.current,
    required this.busy,
    required this.onBuy,
  });
  final String name, price;
  final IconData icon;
  final List<String> features;
  final bool current, busy;
  final VoidCallback onBuy;

  @override
  Widget build(BuildContext context) {
    final fm = context.fm;
    return Container(
      padding: const EdgeInsets.all(FmSpace.lg),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(FmRadius.xl),
        gradient: LinearGradient(colors: [fm.accent.withValues(alpha: 0.22), fm.accent2.withValues(alpha: 0.12)]),
        border: Border.all(color: current ? fm.success : fm.accent.withValues(alpha: 0.35), width: current ? 2 : 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: fm.accent),
              const SizedBox(width: 8),
              Expanded(child: Text(name, style: context.text.headlineSmall)),
              if (price.isNotEmpty)
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(text: price, style: context.text.titleLarge),
                      TextSpan(text: ' /month', style: context.text.bodySmall),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: FmSpace.sm),
          for (final f in features)
            Padding(
              padding: const EdgeInsets.only(bottom: 5),
              child: Row(
                children: [
                  Icon(Icons.check_rounded, size: 17, color: fm.success),
                  const SizedBox(width: 8),
                  Expanded(child: Text(f, style: context.text.bodyMedium)),
                ],
              ),
            ),
          const SizedBox(height: FmSpace.md),
          current
              ? Row(
                  children: [
                    Icon(Icons.check_circle_rounded, color: fm.success),
                    const SizedBox(width: 6),
                    const Text('Your current plan'),
                  ],
                )
              : FmButton(label: 'Choose $name', loading: busy, onPressed: onBuy),
        ],
      ),
    );
  }
}
