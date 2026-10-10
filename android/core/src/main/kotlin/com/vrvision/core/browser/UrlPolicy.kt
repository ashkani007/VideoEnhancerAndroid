package com.vrvision.core.browser

import java.net.URI
import java.net.URLEncoder

/** What the address bar should do with the user's text. */
sealed interface AddressInput {
    data class Url(val url: String) : AddressInput
    data class Search(val url: String, val query: String) : AddressInput
    data class Rejected(val reason: String) : AddressInput
}

/** Decision for a navigation (typed, link click or redirect). */
sealed interface NavigationDecision {
    /** Load in the WebView. */
    data class Allow(val url: String) : NavigationDecision

    /** HTTPS-first: load this https:// URL instead of the requested http:// one. */
    data class Upgrade(val url: String) : NavigationDecision

    /** Hand to another app only after the user confirms (tel:, mailto:, …). */
    data class External(val url: String, val scheme: String) : NavigationDecision

    data class Block(val reason: String) : NavigationDecision
}

/**
 * Address-bar parsing and navigation rules. Only http(s) is loaded in the WebView; a small set
 * of well-known schemes may open another app after confirmation; everything else (javascript:,
 * file:, content:, data:, intent:, …) is blocked.
 */
object UrlPolicy {

    const val DEFAULT_SEARCH = "https://duckduckgo.com/?q=%s"
    const val HOME_URL = "about:blank"

    private val externalSchemes = setOf("tel", "mailto", "sms", "smsto", "geo", "market")
    private val knownSchemes get() = setOf("http", "https", "about") + externalSchemes + blockedReasons.keys
    private val blockedReasons = mapOf(
        "javascript" to "JavaScript URLs can't be opened from the address bar or links.",
        "file" to "Local files can't be opened in the browser.",
        "content" to "App content URLs can't be opened in the browser.",
        "data" to "data: URLs can't be opened as pages.",
        "intent" to "Links that launch other apps directly are blocked.",
        "chrome" to "Browser-internal URLs aren't supported.",
    )

    /** Interprets address-bar text as a URL or a web search. */
    fun resolveInput(text: String, searchTemplate: String = DEFAULT_SEARCH, allowInsecure: Boolean = false): AddressInput {
        val t = text.trim()
        if (t.isEmpty()) return AddressInput.Rejected("Enter an address or search terms.")
        val scheme = schemeOf(t)
        if (scheme != null && scheme !in setOf("http", "https")) {
            return blockedReasons[scheme]?.let { AddressInput.Rejected(it) }
                ?: if (scheme in externalSchemes) AddressInput.Rejected("Open $scheme: links from a web page.")
                else AddressInput.Rejected("Unsupported address type \"$scheme:\".")
        }
        if (scheme != null) {
            return if (isValidHttpUrl(t)) AddressInput.Url(if (!allowInsecure) upgrade(t) else t)
            else AddressInput.Rejected("That address is not valid.")
        }
        if (!t.contains(' ') && looksLikeHost(t)) {
            val url = "https://$t"
            if (isValidHttpUrl(url)) return AddressInput.Url(url)
        }
        return AddressInput.Search(searchTemplate.replace("%s", URLEncoder.encode(t, "UTF-8")), t)
    }

    /**
     * Rules for top-level navigations. [httpAllowedHosts] are hosts the user explicitly chose to
     * visit over plain HTTP after the HTTPS attempt failed.
     */
    fun decide(url: String, httpAllowedHosts: Set<String> = emptySet()): NavigationDecision {
        if (url == HOME_URL) return NavigationDecision.Allow(url)
        val scheme = schemeOf(url) ?: return NavigationDecision.Block("Missing address scheme.")
        return when {
            scheme == "https" -> if (isValidHttpUrl(url)) NavigationDecision.Allow(url) else NavigationDecision.Block("Invalid address.")
            scheme == "http" -> {
                if (!isValidHttpUrl(url)) NavigationDecision.Block("Invalid address.")
                else if (hostOf(url)?.lowercase() in httpAllowedHosts) NavigationDecision.Allow(url)
                else NavigationDecision.Upgrade(upgrade(url))
            }
            scheme in externalSchemes -> NavigationDecision.External(url, scheme)
            else -> NavigationDecision.Block(blockedReasons[scheme] ?: "Unsupported address type \"$scheme:\".")
        }
    }

    fun upgrade(url: String): String = if (url.startsWith("http://", ignoreCase = true)) "https://" + url.substring(7) else url

    fun hostOf(url: String): String? = try { URI(url).host } catch (_: Exception) { null }

    fun isSecure(url: String): Boolean = url.startsWith("https://", ignoreCase = true)

    fun schemeOf(text: String): String? {
        val i = text.indexOf(':')
        if (i <= 0) return null
        val s = text.substring(0, i)
        if (!s.all { it.isLetterOrDigit() || it == '+' || it == '-' || it == '.' } || !s[0].isLetter()) return null
        val lower = s.lowercase()
        if (lower in knownSchemes) return lower
        // "localhost:8080" or "example.com:443/path" are host:port, not schemes.
        if (text.length > i + 1 && text[i + 1].isDigit() && !text.startsWith("$s://")) return null
        return lower
    }

    private fun isValidHttpUrl(url: String): Boolean = try {
        val u = URI(url)
        (u.scheme.equals("http", true) || u.scheme.equals("https", true)) && !u.host.isNullOrBlank() && u.userInfo == null
    } catch (_: Exception) {
        false
    }

    private fun looksLikeHost(t: String): Boolean {
        val host = t.substringBefore('/').substringBefore('?').substringBefore('#').substringBefore(':')
        if (host.equals("localhost", true)) return true
        if (Regex("""\d{1,3}(\.\d{1,3}){3}""").matches(host)) return true
        val labels = host.split('.')
        return labels.size >= 2 && labels.all { it.isNotEmpty() && it.all { c -> c.isLetterOrDigit() || c == '-' } } &&
            labels.last().length >= 2 && labels.last().all { it.isLetter() }
    }
}
