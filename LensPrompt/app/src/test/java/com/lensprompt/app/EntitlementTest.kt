package com.lensprompt.app

import com.lensprompt.app.billing.EntitlementSource
import com.lensprompt.app.billing.Entitlements
import com.lensprompt.app.billing.FeatureGate
import com.lensprompt.app.billing.OwnedPurchase
import com.lensprompt.app.billing.ProEntitlement
import com.lensprompt.app.billing.ProFeature
import com.lensprompt.app.billing.ProProducts
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EntitlementTest {

    @Test
    fun noPurchasesMeansNoPro() {
        assertFalse(Entitlements.compute(emptyList(), debugOverride = false, isDebugBuild = false).isPro)
    }

    @Test
    fun releaseBuildIgnoresTheDebugOverride() {
        val e = Entitlements.compute(emptyList(), debugOverride = true, isDebugBuild = false)
        assertFalse("release must never grant Pro without a purchase", e.isPro)
        assertEquals(EntitlementSource.NONE, e.source)
        assertTrue(Entitlements.compute(emptyList(), debugOverride = true, isDebugBuild = true).isPro)
    }

    @Test
    fun onlyCompletedProPurchasesGrantPro() {
        val pending = OwnedPurchase(listOf(ProProducts.SUBSCRIPTION_ID), purchased = false)
        val other = OwnedPurchase(listOf("some_other_product"), purchased = true)
        assertFalse(Entitlements.compute(listOf(pending, other), false, false).isPro)
        val lifetime = OwnedPurchase(listOf(ProProducts.LIFETIME_ID), purchased = true)
        val e = Entitlements.compute(listOf(pending, lifetime), false, false)
        assertTrue(e.isPro)
        assertEquals(EntitlementSource.GOOGLE_PLAY, e.source)
        assertEquals(setOf(ProProducts.LIFETIME_ID), e.ownedProducts)
    }

    @Test
    fun noFeatureIsLockedInVersionOne() {
        for (f in ProFeature.entries) assertTrue(FeatureGate.isAvailable(f, ProEntitlement()))
    }
}
