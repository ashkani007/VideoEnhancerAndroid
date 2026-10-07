package com.lensprompt.app.billing

import android.app.Activity
import android.content.Context
import android.util.Log
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import com.lensprompt.app.BuildConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Google Play Billing implementation. Only constructed when
 * BuildConfig.BILLING_ENABLED is true (an explicit build flag; off for 1.0).
 *
 * Entitlement is derived from Play's purchase records on every refresh; it
 * is never stored or granted locally. Purchases are acknowledged so Play does
 * not refund them after 3 days.
 *
 * Not yet done (needs owner decisions / a backend): server-side purchase
 * verification and real-time developer notifications. See docs/MONETIZATION.md.
 */
class PlayBillingRepository(context: Context) : ProRepository {

    private val _availability = MutableStateFlow(BillingAvailability.CONNECTING)
    override val availability: StateFlow<BillingAvailability> = _availability.asStateFlow()
    private val _offers = MutableStateFlow<List<ProOffer>>(emptyList())
    override val offers: StateFlow<List<ProOffer>> = _offers.asStateFlow()
    private val _entitlement = MutableStateFlow(ProEntitlement())
    override val entitlement: StateFlow<ProEntitlement> = _entitlement.asStateFlow()

    private var details: Map<String, ProductDetails> = emptyMap()
    private var subsPurchases: List<Purchase> = emptyList()
    private var inappPurchases: List<Purchase> = emptyList()
    private var debugOverride = false

    private val client: BillingClient = BillingClient.newBuilder(context.applicationContext)
        .setListener { result, purchases -> onPurchasesUpdated(result, purchases) }
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .build()

    init {
        refresh()
    }

    override fun refresh() {
        if (client.isReady) {
            loadProducts(); loadPurchases()
            return
        }
        _availability.value = BillingAvailability.CONNECTING
        client.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(result: BillingResult) {
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    _availability.value = BillingAvailability.READY
                    loadProducts()
                    loadPurchases()
                } else {
                    Log.w(TAG, "billing setup failed: ${result.responseCode} ${result.debugMessage}")
                    _availability.value = BillingAvailability.UNAVAILABLE
                }
            }

            override fun onBillingServiceDisconnected() {
                _availability.value = BillingAvailability.UNAVAILABLE
            }
        })
    }

    private fun loadProducts() {
        fun product(id: String, type: String) =
            QueryProductDetailsParams.Product.newBuilder().setProductId(id).setProductType(type).build()
        val queries = listOf(
            listOf(product(ProProducts.SUBSCRIPTION_ID, BillingClient.ProductType.SUBS)),
            listOf(product(ProProducts.LIFETIME_ID, BillingClient.ProductType.INAPP)),
        )
        for (q in queries) {
            client.queryProductDetailsAsync(QueryProductDetailsParams.newBuilder().setProductList(q).build()) { result, productResult ->
                if (result.responseCode != BillingClient.BillingResponseCode.OK) {
                    Log.w(TAG, "product query failed: ${result.responseCode} ${result.debugMessage}")
                    return@queryProductDetailsAsync
                }
                synchronized(this) {
                    details = details + productResult.productDetailsList.associateBy { it.productId }
                    _offers.value = buildOffers()
                }
            }
        }
    }

    private fun buildOffers(): List<ProOffer> = ProPlan.entries.mapNotNull { plan ->
        val d = details[plan.productId] ?: return@mapNotNull null
        if (plan.isSubscription) {
            val offer = baseOffer(d, plan) ?: return@mapNotNull null
            val phase = offer.pricingPhases.pricingPhaseList.lastOrNull() ?: return@mapNotNull null
            ProOffer(plan, phase.formattedPrice, phase.billingPeriod)
        } else {
            val one = d.oneTimePurchaseOfferDetails ?: return@mapNotNull null
            ProOffer(plan, one.formattedPrice, null)
        }
    }

    /** The plain base-plan offer (no promotional offer id) for a subscription plan. */
    private fun baseOffer(d: ProductDetails, plan: ProPlan): ProductDetails.SubscriptionOfferDetails? {
        val forPlan = d.subscriptionOfferDetails.orEmpty().filter { it.basePlanId == plan.basePlanId }
        return forPlan.firstOrNull { it.offerId == null } ?: forPlan.firstOrNull()
    }

    private fun loadPurchases() {
        client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build()) { r, list ->
            if (r.responseCode == BillingClient.BillingResponseCode.OK) { subsPurchases = list; handlePurchases(list); recompute() }
        }
        client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build()) { r, list ->
            if (r.responseCode == BillingClient.BillingResponseCode.OK) { inappPurchases = list; handlePurchases(list); recompute() }
        }
    }

    private fun onPurchasesUpdated(result: BillingResult, purchases: List<Purchase>?) {
        when (result.responseCode) {
            BillingClient.BillingResponseCode.OK, BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED -> loadPurchases()
            BillingClient.BillingResponseCode.USER_CANCELED -> Unit
            else -> Log.w(TAG, "purchase failed: ${result.responseCode} ${result.debugMessage}")
        }
        purchases?.let { handlePurchases(it) }
    }

    /** Acknowledge new purchases (otherwise Play refunds them after 3 days). */
    private fun handlePurchases(list: List<Purchase>) {
        for (p in list) {
            if (p.purchaseState == Purchase.PurchaseState.PURCHASED && !p.isAcknowledged) {
                client.acknowledgePurchase(AcknowledgePurchaseParams.newBuilder().setPurchaseToken(p.purchaseToken).build()) { r ->
                    if (r.responseCode != BillingClient.BillingResponseCode.OK) Log.w(TAG, "acknowledge failed: ${r.responseCode}")
                }
            }
        }
    }

    @Synchronized
    private fun recompute() {
        val owned = (subsPurchases + inappPurchases).map {
            OwnedPurchase(it.products, it.purchaseState == Purchase.PurchaseState.PURCHASED)
        }
        _entitlement.value = Entitlements.compute(owned, debugOverride, BuildConfig.DEBUG)
    }

    override fun purchase(activity: Activity, plan: ProPlan): Boolean {
        val d = details[plan.productId] ?: return false
        val params = BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(d)
        if (plan.isSubscription) params.setOfferToken(baseOffer(d, plan)?.offerToken ?: return false)
        val flow = BillingFlowParams.newBuilder().setProductDetailsParamsList(listOf(params.build())).build()
        return client.launchBillingFlow(activity, flow).responseCode == BillingClient.BillingResponseCode.OK
    }

    override fun setDebugOverride(enabled: Boolean) {
        debugOverride = enabled
        recompute()
    }

    private companion object { const val TAG = "LensPromptBilling" }
}
