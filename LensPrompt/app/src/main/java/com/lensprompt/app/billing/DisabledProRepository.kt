package com.lensprompt.app.billing

import android.app.Activity
import com.lensprompt.app.BuildConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Used while billing is switched off (BuildConfig.BILLING_ENABLED = false, the
 * 1.0 default). Never contacts Google Play and never grants Pro, except the
 * debug-build-only override for testing.
 */
class DisabledProRepository : ProRepository {
    private val _entitlement = MutableStateFlow(ProEntitlement())
    override val availability: StateFlow<BillingAvailability> = MutableStateFlow(BillingAvailability.NOT_LAUNCHED)
    override val offers: StateFlow<List<ProOffer>> = MutableStateFlow(emptyList())
    override val entitlement: StateFlow<ProEntitlement> = _entitlement.asStateFlow()

    override fun refresh() = Unit
    override fun purchase(activity: Activity, plan: ProPlan): Boolean = false

    override fun setDebugOverride(enabled: Boolean) {
        _entitlement.value = Entitlements.compute(emptyList(), enabled, BuildConfig.DEBUG)
    }
}
