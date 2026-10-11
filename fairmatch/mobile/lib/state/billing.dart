import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../data/repository.dart';
import 'providers.dart';

/// Google Play Billing bridge. The client NEVER unlocks anything itself: every purchase
/// token is sent to the backend, which verifies it with Google and grants entitlements.
class BillingService {
  BillingService(this.ref) {
    if (!ref.read(sessionProvider).isDemo && !kIsWeb) {
      _sub = InAppPurchase.instance.purchaseStream.listen(_onPurchases, onError: (Object e) => _status.add('Purchase error: $e'));
    }
  }

  final Ref ref;
  StreamSubscription<List<PurchaseDetails>>? _sub;
  final _status = StreamController<String>.broadcast();
  Stream<String> get status => _status.stream;

  bool get _demo => ref.read(sessionProvider).isDemo;

  Future<Map<String, ProductDetails>> storeProducts(Set<String> ids) async {
    if (_demo || kIsWeb || !await InAppPurchase.instance.isAvailable()) return {};
    final res = await InAppPurchase.instance.queryProductDetails(ids);
    return {for (final p in res.productDetails) p.id: p};
  }

  /// Starts a purchase. In demo mode it is simulated (no charge) and clearly labelled.
  Future<void> buy(String productId, {required bool consumable, ProductDetails? details}) async {
    final repo = ref.read(repoProvider);
    if (_demo) {
      await repo.verifyPurchase(productId, 'dev-demo-${DateTime.now().millisecondsSinceEpoch}');
      _refresh();
      _status.add('Demo purchase complete — no charge was made.');
      return;
    }
    if (details == null) {
      throw ApiException(
        'store_unavailable',
        'Google Play is not available on this device. Try again from an Android device with Play Store.',
      );
    }
    final param = PurchaseParam(productDetails: details);
    if (consumable) {
      await InAppPurchase.instance.buyConsumable(purchaseParam: param);
    } else {
      await InAppPurchase.instance.buyNonConsumable(purchaseParam: param);
    }
  }

  Future<void> restore() async {
    if (_demo || kIsWeb) {
      _status.add('Nothing to restore in demo mode.');
      return;
    }
    await InAppPurchase.instance.restorePurchases();
  }

  Future<void> _onPurchases(List<PurchaseDetails> purchases) async {
    for (final p in purchases) {
      switch (p.status) {
        case PurchaseStatus.pending:
          _status.add('Payment pending — we\'ll unlock your plan once Google confirms it.');
        case PurchaseStatus.error:
          _status.add(p.error?.message ?? 'The purchase failed.');
        case PurchaseStatus.canceled:
          _status.add('Purchase cancelled.');
        case PurchaseStatus.purchased:
        case PurchaseStatus.restored:
          try {
            await ref.read(repoProvider).verifyPurchase(p.productID, p.verificationData.serverVerificationData);
            _status.add(p.status == PurchaseStatus.restored ? 'Purchases restored.' : 'Thank you! Your plan is active.');
            _refresh();
          } on ApiException catch (e) {
            _status.add('We could not verify this purchase yet: ${e.message}');
            continue; // leave uncompleted so it is retried on next launch
          }
      }
      if (p.pendingCompletePurchase) await InAppPurchase.instance.completePurchase(p);
    }
  }

  void _refresh() {
    ref.invalidate(meProvider);
    ref.invalidate(likesProvider);
    ref.invalidate(pairProvider);
  }

  void dispose() {
    _sub?.cancel();
    _status.close();
  }
}

final billingProvider = Provider<BillingService>((ref) {
  ref.watch(sessionProvider);
  final s = BillingService(ref);
  ref.onDispose(s.dispose);
  return s;
});
