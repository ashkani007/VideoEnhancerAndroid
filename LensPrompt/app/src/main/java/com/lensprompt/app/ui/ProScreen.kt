package com.lensprompt.app.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lensprompt.app.BuildConfig
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.billing.BillingAvailability
import com.lensprompt.app.billing.EntitlementSource
import com.lensprompt.app.billing.ProPlan

/**
 * LensPrompt Pro. Shows the plans with prices exactly as Google Play reports
 * them (never hard-coded). While billing is switched off for 1.0 it says so
 * and offers no purchase.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val pro = (context.applicationContext as LensPromptApplication).pro
    val availability by pro.availability.collectAsState()
    val offers by pro.offers.collectAsState()
    val entitlement by pro.entitlement.collectAsState()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } },
                title = { Text("LensPrompt Pro") },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp)) {
            when {
                entitlement.isPro && entitlement.source == EntitlementSource.GOOGLE_PLAY ->
                    Text("You have LensPrompt Pro. Thank you!", color = LensColors.Accent, fontWeight = FontWeight.SemiBold)
                entitlement.isPro && entitlement.source == EntitlementSource.DEBUG_OVERRIDE ->
                    Text("Debug build: Pro is simulated for testing only.", color = LensColors.Muted)
            }
            when (availability) {
                BillingAvailability.NOT_LAUNCHED -> Text(
                    "LensPrompt Pro is coming soon. Everything in LensPrompt is available to you now, free.",
                    color = LensColors.Muted,
                )
                BillingAvailability.CONNECTING -> Text("Connecting to Google Play…", color = LensColors.Muted)
                BillingAvailability.UNAVAILABLE -> Text(
                    "Google Play purchases are not available on this device right now.",
                    color = LensColors.Muted,
                )
                BillingAvailability.READY -> Unit
            }
            Spacer(Modifier.height(12.dp))
            ProPlan.entries.forEach { plan ->
                val offer = offers.firstOrNull { it.plan == plan }
                Card(
                    colors = CardDefaults.cardColors(containerColor = LensColors.Surface),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Text(
                            when (plan) {
                                ProPlan.MONTHLY -> "Monthly"
                                ProPlan.YEARLY -> "Yearly"
                                ProPlan.LIFETIME -> "Lifetime (one-time purchase)"
                            },
                            style = MaterialTheme.typography.titleMedium,
                        )
                        // Price text comes from Google Play only.
                        Text(offer?.formattedPrice ?: "Price shown by Google Play", color = LensColors.Muted)
                        Spacer(Modifier.height(8.dp))
                        Button(
                            enabled = availability == BillingAvailability.READY && offer != null && !entitlement.isPro,
                            onClick = { context.findActivity()?.let { pro.purchase(it, plan) } },
                        ) { Text(if (plan == ProPlan.LIFETIME) "Buy" else "Subscribe") }
                    }
                }
            }
            if (availability == BillingAvailability.READY) {
                OutlinedButton(onClick = { pro.refresh() }) { Text("Restore purchases") }
                Text(
                    "Subscriptions renew automatically until cancelled in Google Play → Payments & subscriptions.",
                    color = LensColors.Muted, style = MaterialTheme.typography.bodySmall,
                )
            }
            if (BuildConfig.DEBUG) {
                Spacer(Modifier.height(16.dp))
                LabeledSwitch("Debug build only: simulate Pro", entitlement.source == EntitlementSource.DEBUG_OVERRIDE) {
                    pro.setDebugOverride(it)
                }
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}
