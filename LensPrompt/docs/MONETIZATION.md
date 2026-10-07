# LensPrompt Pro: monetization architecture

Freemium. Status in 1.0: **architecture in place, purchases switched off.**

| | |
|---|---|
| Build flag | `BuildConfig.BILLING_ENABLED`, default **false**. Gradle property `-Plensprompt.billingEnabled=true` turns it on. |
| When off | `DisabledProRepository`: no connection to Google Play, Pro never granted. The Pro screen says "coming soon". |
| When on | `PlayBillingRepository` (Play Billing Library 8): loads products, shows **Play's own localized prices**, runs the purchase sheet, acknowledges purchases and restores them. |
| Prices | **Never hard-coded.** Set them in Play Console. |
| Entitlement | Derived from Google Play's purchase records on every refresh (`Entitlements.compute`, unit-tested). Only `PURCHASED` Pro products grant Pro. The "simulate Pro" switch exists **only in debug builds** and is ignored in release. |
| Locked features | **None in 1.0** (`FeatureGate.PRO_ONLY` is empty). Deciding which features are Pro is a product decision; nothing that works today is locked. |

## Products to create in Play Console (IDs must match `ProProducts`)

| Plan | Play product type | Product ID | Base plan ID |
|---|---|---|---|
| Monthly | Subscription | `lensprompt_pro` | `monthly` (auto-renewing, 1 month) |
| Yearly | Subscription | `lensprompt_pro` | `yearly` (auto-renewing, 1 year) |
| Lifetime | One-time product (in-app) | `lensprompt_pro_lifetime` | — |

These IDs are **placeholders chosen for the architecture**. Product IDs can't be reused once created in Play Console, so confirm or change them in `billing/ProModel.kt` **before** creating the products.

## Before turning billing on

1. Payments profile / merchant account in Play Console (owner; may need tax and bank details).
2. Create the products above, with prices per country.
3. Decide which features are Pro (`FeatureGate.PRO_ONLY`), and add the gated UI and upgrade prompts.
4. **Recommended:** server-side purchase verification and Real-time Developer Notifications (needs a backend; owner decision). Without a backend, entitlement relies on the Play Billing client, which is acceptable for launch but easier to tamper with.
5. Build with `-Plensprompt.billingEnabled=true` on an **internal testing** track with license testers.
6. Update the Privacy Policy (section 6) and Data safety ("Purchase history").
