package com.vrvision.app.browser

import android.annotation.SuppressLint
import android.webkit.CookieManager
import android.webkit.WebSettings
import android.webkit.WebView

/**
 * Hardened WebView configuration, applied to every tab.
 *
 * - JavaScript is on (modern video sites need it) but **no JavaScript interface is ever added**;
 *   the app only runs its own read-only detection script via evaluateJavascript.
 * - No file:// or content:// access, no universal access from file URLs.
 * - Mixed content is never allowed; Safe Browsing is on; certificate errors are never ignored
 *   (see BrowserController's WebViewClient).
 * - No third-party cookies, no geolocation, no automatic pop-up windows, no saved passwords.
 * - Media requires a user gesture to start with sound (WebView default kept).
 */
object WebViewSecurity {

    @SuppressLint("SetJavaScriptEnabled")
    fun configure(webView: WebView) {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            @Suppress("DEPRECATION")
            allowFileAccessFromFileURLs = false
            @Suppress("DEPRECATION")
            allowUniversalAccessFromFileURLs = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            safeBrowsingEnabled = true
            setGeolocationEnabled(false)
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
            mediaPlaybackRequiresUserGesture = true
            builtInZoomControls = true
            displayZoomControls = false
            useWideViewPort = true
            loadWithOverviewMode = true
            @Suppress("DEPRECATION")
            savePassword = false
            @Suppress("DEPRECATION")
            saveFormData = false
        }
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false)
        WebView.setWebContentsDebuggingEnabled(false)
    }
}
