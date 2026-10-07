package com.lensprompt.app.billing

/**
 * LensPrompt Pro: the purchasable plans and how they map to Google Play
 * products. IDs here must match the products created in Play Console:
 *
 *  - one subscription product [SUBSCRIPTION_ID] with two base plans,
 *    [BASE_PLAN_MONTHLY] and [BASE_PLAN_YEARLY];
 *  - one one-time (in-app) product [LIFETIME_ID].
 *
 * Prices are never hard-coded: they always come from Play
 * (ProductDetails.formattedPrice) in the user's currency.
 * PLACEHOLDERS until the products exist in Play Console (see docs/MONETIZATION.md).
 */
object ProProducts {
    const val SUBSCRIPTION_ID = "lensprompt_pro"
    const val BASE_PLAN_MONTHLY = "monthly"
    const val BASE_PLAN_YEARLY = "yearly"
    const val LIFETIME_ID = "lensprompt_pro_lifetime"

    /** Every product whose purchase grants Pro. */
    val ALL_PRO_PRODUCT_IDS = setOf(SUBSCRIPTION_ID, LIFETIME_ID)
}

enum class ProPlan(val productId: String, val basePlanId: String?, val isSubscription: Boolean) {
    MONTHLY(ProProducts.SUBSCRIPTION_ID, ProProducts.BASE_PLAN_MONTHLY, true),
    YEARLY(ProProducts.SUBSCRIPTION_ID, ProProducts.BASE_PLAN_YEARLY, true),
    LIFETIME(ProProducts.LIFETIME_ID, null, false),
}

/** Where a Pro entitlement came from. */
enum class EntitlementSource { NONE, GOOGLE_PLAY, DEBUG_OVERRIDE }

data class ProEntitlement(
    val isPro: Boolean = false,
    val source: EntitlementSource = EntitlementSource.NONE,
    /** Products the user owns that grant Pro (for display / support). */
    val ownedProducts: Set<String> = emptySet(),
)

/** Whether purchasing is possible right now. */
enum class BillingAvailability {
    /** Billing is switched off in this build (LensPrompt 1.0 default). */
    NOT_LAUNCHED,
    CONNECTING,
    READY,
    /** Google Play billing is not available (no Play Store, not signed in, …). */
    UNAVAILABLE,
}

/** A plan as offered by Google Play, with Play's localized price text. */
data class ProOffer(
    val plan: ProPlan,
    val formattedPrice: String,
    /** ISO-8601 billing period for subscriptions (P1M, P1Y), null for lifetime. */
    val billingPeriod: String?,
)

/** A purchase as reported by Play, reduced to what entitlement decisions need. */
data class OwnedPurchase(val productIds: List<String>, val purchased: Boolean)

/**
 * Pure entitlement rule, unit-tested:
 *  - only PURCHASED (not PENDING) purchases of Pro products grant Pro;
 *  - the debug override works only in debug builds, never in release.
 */
object Entitlements {
    fun compute(purchases: List<OwnedPurchase>, debugOverride: Boolean, isDebugBuild: Boolean): ProEntitlement {
        val owned = purchases.filter { it.purchased }
            .flatMap { it.productIds }
            .filter { it in ProProducts.ALL_PRO_PRODUCT_IDS }
            .toSet()
        return when {
            owned.isNotEmpty() -> ProEntitlement(true, EntitlementSource.GOOGLE_PLAY, owned)
            debugOverride && isDebugBuild -> ProEntitlement(true, EntitlementSource.DEBUG_OVERRIDE)
            else -> ProEntitlement()
        }
    }
}

/**
 * Features that LensPrompt Pro may unlock. Which ones are Pro is a product
 * decision that has NOT been made yet, so in 1.0 nothing is locked:
 * every feature that works today keeps working for everyone.
 */
enum class ProFeature { SMART_FOLLOW_OFFLINE, FLOATING_TELEPROMPTER, UNLIMITED_SCRIPTS, RECORDING_WITH_SOUND }

object FeatureGate {
    /** Features that require Pro. Empty for 1.0 (decision pending). */
    val PRO_ONLY: Set<ProFeature> = emptySet()

    fun isAvailable(feature: ProFeature, entitlement: ProEntitlement): Boolean =
        feature !in PRO_ONLY || entitlement.isPro
}
