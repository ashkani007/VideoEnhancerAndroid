package com.lensprompt.app.billing

import android.app.Activity
import kotlinx.coroutines.flow.StateFlow

/** Source of truth for LensPrompt Pro: offers, purchase flow, entitlement. */
interface ProRepository {
    val availability: StateFlow<BillingAvailability>
    val offers: StateFlow<List<ProOffer>>
    val entitlement: StateFlow<ProEntitlement>

    /** Reconnect, reload offers and re-check owned purchases ("Restore purchases"). */
    fun refresh()

    /** Starts the Google Play purchase sheet; false if it could not be shown. */
    fun purchase(activity: Activity, plan: ProPlan): Boolean

    /** Debug builds only: pretend Pro to test gated UI. Ignored in release. */
    fun setDebugOverride(enabled: Boolean)
}
