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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lensprompt.app.BuildConfig
import com.lensprompt.app.LensPromptApplication
import com.lensprompt.app.R
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
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.common_back)) } },
                title = { Text(stringResource(R.string.pro_title)) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp)) {
            when {
                entitlement.isPro && entitlement.source == EntitlementSource.GOOGLE_PLAY ->
                    Text(stringResource(R.string.pro_owned), color = LensColors.Accent, fontWeight = FontWeight.SemiBold)
                entitlement.isPro && entitlement.source == EntitlementSource.DEBUG_OVERRIDE ->
                    Text("Debug build: Pro is simulated for testing only.", color = LensColors.Muted)
            }
            when (availability) {
                BillingAvailability.NOT_LAUNCHED -> Text(
                    stringResource(R.string.pro_coming_soon),
                    color = LensColors.Muted,
                )
                BillingAvailability.CONNECTING -> Text(stringResource(R.string.pro_connecting), color = LensColors.Muted)
                BillingAvailability.UNAVAILABLE -> Text(
                    stringResource(R.string.pro_unavailable),
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
                                ProPlan.MONTHLY -> stringResource(R.string.pro_plan_monthly)
                                ProPlan.YEARLY -> stringResource(R.string.pro_plan_yearly)
                                ProPlan.LIFETIME -> stringResource(R.string.pro_plan_lifetime)
                            },
                            style = MaterialTheme.typography.titleMedium,
                        )
                        // Price text comes from Google Play only.
                        Text(offer?.formattedPrice ?: stringResource(R.string.pro_price_placeholder), color = LensColors.Muted)
                        Spacer(Modifier.height(8.dp))
                        Button(
                            enabled = availability == BillingAvailability.READY && offer != null && !entitlement.isPro,
                            onClick = { context.findActivity()?.let { pro.purchase(it, plan) } },
                        ) { Text(if (plan == ProPlan.LIFETIME) stringResource(R.string.pro_buy) else stringResource(R.string.pro_subscribe)) }
                    }
                }
            }
            if (availability == BillingAvailability.READY) {
                OutlinedButton(onClick = { pro.refresh() }) { Text(stringResource(R.string.pro_restore)) }
                Text(
                    stringResource(R.string.pro_renew_note),
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
