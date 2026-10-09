package com.vrvision.app.browser

import android.annotation.SuppressLint
import android.app.Application
import android.content.Context
import android.content.Intent
import android.content.MutableContextWrapper
import android.graphics.Bitmap
import android.net.Uri
import android.net.http.SslError
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebStorage
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebViewDatabase
import com.vrvision.core.browser.AddressInput
import com.vrvision.core.browser.DownloadDecision
import com.vrvision.core.browser.DownloadPolicy
import com.vrvision.core.browser.DownloadRequest
import com.vrvision.core.browser.MediaCandidate
import com.vrvision.core.browser.MediaDetector
import com.vrvision.core.browser.MediaOrigin
import com.vrvision.core.browser.NavigationDecision
import com.vrvision.core.browser.TabManager
import com.vrvision.core.browser.TabState
import com.vrvision.core.browser.UrlPolicy
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONTokener
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

/** Live, per-tab UI state. */
data class TabUi(
    val id: Long,
    val url: String = "",
    val title: String = "",
    val progress: Int = 0,
    val loading: Boolean = false,
    val canGoBack: Boolean = false,
    val canGoForward: Boolean = false,
    val error: String? = null,
    val media: List<MediaCandidate> = emptyList(),
) {
    val secure: Boolean get() = UrlPolicy.isSecure(url)
}

/** Something the user must decide; the UI shows it and calls back. */
sealed interface BrowserPrompt {
    data class External(val url: String, val scheme: String) : BrowserPrompt
    data class Download(val request: DownloadRequest, val decision: DownloadDecision) : BrowserPrompt
    data class ProtectedMedia(val origin: String, val request: PermissionRequest) : BrowserPrompt
    data class FileChooser(val params: WebChromeClient.FileChooserParams, val callback: ValueCallback<Array<Uri>>) : BrowserPrompt
    data class Message(val title: String, val text: String) : BrowserPrompt
}

/**
 * Owns the browser tabs and their WebViews for the app process. WebViews are created with a
 * MutableContextWrapper so they can be re-parented between the normal browser and the VR
 * capture surface, and so dialogs use the current Activity.
 */
class BrowserController(
    private val app: Application,
    private val dao: BrowserDao,
    private val scope: CoroutineScope,
    private val searchTemplate: () -> String,
) {
    private val ctx = MutableContextWrapper(app)
    private val webViews = ConcurrentHashMap<Long, WebView>()
    private val nextId = AtomicLong(System.currentTimeMillis())
    private val observedMedia = ConcurrentHashMap<Long, MutableSet<String>>()
    private var restored = false
    private var saveJob: Job? = null

    private val _tabs = MutableStateFlow(TabState())
    val tabs: StateFlow<TabState> = _tabs.asStateFlow()
    private val _ui = MutableStateFlow<Map<Long, TabUi>>(emptyMap())
    val ui: StateFlow<Map<Long, TabUi>> = _ui.asStateFlow()
    private val _prompt = MutableStateFlow<BrowserPrompt?>(null)
    val prompt: StateFlow<BrowserPrompt?> = _prompt.asStateFlow()
    private val _fullscreen = MutableStateFlow<View?>(null)
    val fullscreen: StateFlow<View?> = _fullscreen.asStateFlow()
    private var fullscreenCallback: WebChromeClient.CustomViewCallback? = null

    fun attach(activityContext: Context) { ctx.baseContext = activityContext }
    fun detach() { ctx.baseContext = app }

    /** Restores the previous session's tabs (URL and title only) or opens a blank tab. */
    suspend fun restore(restoreSession: Boolean) {
        if (restored) return
        restored = true
        val saved = if (restoreSession) dao.sessionTabs() else emptyList()
        var s = TabState()
        saved.forEach { t -> s = TabManager.open(s, t.url, t.id) }
        s = saved.firstOrNull { it.active }?.let { TabManager.select(s, it.id) } ?: s
        s = TabManager.ensureOne(s, { nextId.incrementAndGet() })
        saved.forEach { nextId.updateAndGet { cur -> maxOf(cur, it.id + 1) } }
        _tabs.value = s
        _ui.value = s.tabs.associate { it.id to TabUi(it.id, url = it.url, title = saved.firstOrNull { x -> x.id == it.id }?.title.orEmpty()) }
    }

    /** The WebView for a tab, created (and its URL loaded) on first use. */
    fun webView(tabId: Long): WebView = webViews.getOrPut(tabId) { create(tabId) }

    val activeId: Long? get() = _tabs.value.activeId

    @SuppressLint("ClickableViewAccessibility")
    private fun create(tabId: Long): WebView {
        val wv = WebView(ctx)
        WebViewSecurity.configure(wv)
        wv.webViewClient = Client(tabId)
        wv.webChromeClient = Chrome(tabId)
        wv.setDownloadListener { url, _, contentDisposition, mimeType, contentLength ->
            // WebView reports a download when a navigation returns a file. Nothing is fetched
            // until the user confirms the dialog, which is the authorization step.
            val req = DownloadRequest(url, mimeType, contentDisposition, contentLength, userInitiated = true)
            _prompt.value = BrowserPrompt.Download(req, DownloadPolicy.evaluate(req))
        }
        _tabs.value.tabs.firstOrNull { it.id == tabId }?.url?.takeIf { it.isNotBlank() }?.let { loadChecked(wv, tabId, it) }
        return wv
    }

    // ---------- navigation ----------

    /** Address bar submit. Returns an error message for rejected input. */
    fun submit(text: String): String? {
        val id = activeId ?: return null
        return when (val r = UrlPolicy.resolveInput(text, searchTemplate())) {
            is AddressInput.Url -> { loadChecked(webView(id), id, r.url); null }
            is AddressInput.Search -> { loadChecked(webView(id), id, r.url); null }
            is AddressInput.Rejected -> r.reason
        }
    }

    fun load(url: String) { activeId?.let { loadChecked(webView(it), it, url) } }

    private fun loadChecked(wv: WebView, tabId: Long, url: String) {
        when (val d = UrlPolicy.decide(url)) {
            is NavigationDecision.Allow -> wv.loadUrl(d.url)
            is NavigationDecision.Upgrade -> { upgraded[tabId] = d.url; wv.loadUrl(d.url) }
            is NavigationDecision.External -> _prompt.value = BrowserPrompt.External(d.url, d.scheme)
            is NavigationDecision.Block -> setUi(tabId) { it.copy(error = d.reason) }
        }
    }

    private val upgraded = ConcurrentHashMap<Long, String>()

    fun back() { activeId?.let { id -> webViews[id]?.takeIf { it.canGoBack() }?.goBack() } }
    fun forward() { activeId?.let { id -> webViews[id]?.takeIf { it.canGoForward() }?.goForward() } }
    fun reload() { activeId?.let { id -> setUi(id) { it.copy(error = null) }; webViews[id]?.reload() } }
    fun stop() { activeId?.let { webViews[it]?.stopLoading() } }
    fun home() { load(UrlPolicy.HOME_URL) }
    fun canGoBack(): Boolean = activeId?.let { webViews[it]?.canGoBack() } == true

    /** Scrolls the active page with a script that only scrolls (no data leaves the page). */
    fun scrollBy(dx: Int, dy: Int) { activeId?.let { webViews[it]?.evaluateJavascript("window.scrollBy($dx,$dy);", null) } }

    // ---------- tabs ----------

    fun newTab(url: String = UrlPolicy.HOME_URL): Boolean {
        val s = _tabs.value
        if (!TabManager.canOpen(s)) return false
        val id = nextId.incrementAndGet()
        _tabs.value = TabManager.open(s, url, id, System.currentTimeMillis())
        setUi(id) { it.copy(url = url) }
        webView(id)
        persistSoon()
        return true
    }

    fun select(id: Long) { _tabs.value = TabManager.select(_tabs.value, id); persistSoon() }

    fun close(id: Long) {
        webViews.remove(id)?.let { wv -> (wv.parent as? ViewGroup)?.removeView(wv); wv.destroy() }
        observedMedia.remove(id)
        _ui.update { it - id }
        _tabs.value = TabManager.ensureOne(TabManager.close(_tabs.value, id), { nextId.incrementAndGet() })
        _tabs.value.tabs.forEach { t -> if (_ui.value[t.id] == null) setUi(t.id) { it.copy(url = t.url) } }
        persistSoon()
    }

    // ---------- media ----------

    /** Runs the read-only detection script on the active page and merges network observations. */
    fun detectMedia() {
        val id = activeId ?: return
        val wv = webViews[id] ?: return
        val pageUrl = wv.url.orEmpty()
        wv.evaluateJavascript(MediaDetector.DETECTION_SCRIPT) { json ->
            val raw = try { JSONTokener(json).nextValue() as? String } catch (_: Exception) { null }.orEmpty()
            val fromScript = MediaDetector.parseScriptResult(raw, pageUrl)
            val fromNetwork = observedMedia[id].orEmpty().map {
                MediaCandidate(it, MediaDetector.kindOf(it), pageUrl, fromScript.firstOrNull()?.pageTitle.orEmpty(), origin = MediaOrigin.NETWORK_REQUEST)
            }
            setUi(id) { it.copy(media = MediaDetector.merge(fromScript + fromNetwork)) }
        }
    }

    // ---------- prompts ----------

    fun dismissPrompt() { _prompt.value = null }

    fun openExternal(url: String) {
        _prompt.value = null
        try {
            app.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: Exception) {
            _prompt.value = BrowserPrompt.Message("Can't open link", "No app on this phone handles this link.")
        }
    }

    fun answerProtectedMedia(p: BrowserPrompt.ProtectedMedia, allow: Boolean) {
        if (allow) p.request.grant(arrayOf(PermissionRequest.RESOURCE_PROTECTED_MEDIA_ID)) else p.request.deny()
        _prompt.value = null
    }

    fun answerFileChooser(p: BrowserPrompt.FileChooser, uris: List<Uri>?) {
        p.callback.onReceiveValue(uris?.toTypedArray())
        _prompt.value = null
    }

    fun exitFullscreen() { fullscreenCallback?.onCustomViewHidden(); fullscreenCallback = null; _fullscreen.value = null }

    // ---------- lifecycle ----------

    fun onPause() { webViews.values.forEach { it.onPause() }; persistSoon() }
    fun onResume() { webViews.values.forEach { it.onResume() } }

    /** Clears cookies, site storage, cache, history, saved session and form/auth data. */
    suspend fun clearBrowsingData() {
        withContext(Dispatchers.Main) {
            CookieManager.getInstance().removeAllCookies(null)
            CookieManager.getInstance().flush()
            WebStorage.getInstance().deleteAllData()
            webViews.values.forEach { it.clearCache(true); it.clearHistory(); it.clearFormData() }
            @Suppress("DEPRECATION")
            WebViewDatabase.getInstance(app).clearHttpAuthUsernamePassword()
        }
        dao.clearHistory()
        dao.clearSession()
    }

    private fun persistSoon() {
        saveJob?.cancel()
        saveJob = scope.launch {
            delay(500)
            val s = _tabs.value
            val tabs = s.tabs.mapIndexed { i, t ->
                val u = _ui.value[t.id]
                SessionTabEntity(t.id, u?.url?.ifBlank { null } ?: t.url, u?.title ?: t.title, i, t.id == s.activeId)
            }.filter { it.url.startsWith("https://") || it.url == UrlPolicy.HOME_URL }
            dao.clearSession()
            dao.saveSession(tabs)
        }
    }

    private fun setUi(id: Long, f: (TabUi) -> TabUi) {
        _ui.update { m -> m + (id to f(m[id] ?: TabUi(id))) }
    }

    private fun refreshNav(id: Long, wv: WebView) = setUi(id) { it.copy(canGoBack = wv.canGoBack(), canGoForward = wv.canGoForward()) }

    // ---------- WebView clients ----------

    private inner class Client(private val tabId: Long) : WebViewClient() {

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val url = request.url.toString()
            return when (val d = UrlPolicy.decide(url)) {
                is NavigationDecision.Allow -> false
                is NavigationDecision.Upgrade -> { upgraded[tabId] = d.url; view.loadUrl(d.url); true }
                is NavigationDecision.External -> {
                    // Only a user's top-level click may offer another app; frames can't.
                    if (request.isForMainFrame && request.hasGesture()) _prompt.value = BrowserPrompt.External(d.url, d.scheme)
                    true
                }
                is NavigationDecision.Block -> {
                    if (request.isForMainFrame) setUi(tabId) { it.copy(error = d.reason) }
                    true
                }
            }
        }

        override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
            observedMedia[tabId]?.clear()
            setUi(tabId) { it.copy(url = url, loading = true, error = null, media = emptyList()) }
            refreshNav(tabId, view)
        }

        override fun onPageFinished(view: WebView, url: String) {
            setUi(tabId) { it.copy(url = url, loading = false, progress = 100) }
            refreshNav(tabId, view)
            _tabs.value = TabManager.update(_tabs.value, tabId, url = url, title = view.title)
            persistSoon()
            if (url.startsWith("https://")) {
                val title = view.title.orEmpty()
                scope.launch {
                    if (dao.lastHistory()?.url != url) { dao.addHistory(HistoryEntity(url = url, title = title)); dao.trimHistory() }
                }
            }
            if (tabId == activeId) detectMedia()
        }

        override fun doUpdateVisitedHistory(view: WebView, url: String, isReload: Boolean) = refreshNav(tabId, view)

        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
            // Observe only (never modify or read bodies/headers): note media-looking request URLs.
            val url = request.url.toString()
            if (MediaDetector.isMediaRequest(url)) observedMedia.getOrPut(tabId) { ConcurrentHashMap.newKeySet() }.add(url)
            return null
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (!request.isForMainFrame) return
            val url = request.url.toString()
            val msg = if (upgraded[tabId] == url) {
                "This site could not be reached over HTTPS. VRVision only loads encrypted (HTTPS) pages."
            } else "The page could not be loaded: ${error.description}"
            setUi(tabId) { it.copy(error = msg, loading = false) }
        }

        @SuppressLint("WebViewClientOnReceivedSslError")
        override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
            // Never proceed on certificate errors.
            handler.cancel()
            setUi(tabId) { it.copy(error = "This site's security certificate is not valid, so the connection was stopped.", loading = false) }
        }

        override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
            // Keep the app alive: drop this tab's WebView; it is recreated on next use.
            webViews.remove(tabId)?.let { (it.parent as? ViewGroup)?.removeView(it); it.destroy() }
            setUi(tabId) { it.copy(error = "The page stopped unexpectedly. Reload to try again.", loading = false) }
            return true
        }
    }

    private inner class Chrome(private val tabId: Long) : WebChromeClient() {
        override fun onProgressChanged(view: WebView, newProgress: Int) = setUi(tabId) { it.copy(progress = newProgress, loading = newProgress < 100) }

        override fun onReceivedTitle(view: WebView, title: String?) {
            setUi(tabId) { it.copy(title = title.orEmpty()) }
            _tabs.value = TabManager.update(_tabs.value, tabId, title = title.orEmpty())
        }

        override fun onShowCustomView(view: View, callback: CustomViewCallback) {
            fullscreenCallback?.onCustomViewHidden()
            fullscreenCallback = callback
            _fullscreen.value = view
        }

        override fun onHideCustomView() { fullscreenCallback = null; _fullscreen.value = null }

        override fun onPermissionRequest(request: PermissionRequest) {
            // Camera/microphone/MIDI are never granted (the app holds no such permissions).
            // Protected media (DRM playback inside the page) is asked per request.
            if (request.resources.contains(PermissionRequest.RESOURCE_PROTECTED_MEDIA_ID) && request.resources.size == 1) {
                _prompt.value = BrowserPrompt.ProtectedMedia(request.origin.host ?: request.origin.toString(), request)
            } else request.deny()
        }

        override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
            callback.invoke(origin, false, false)
        }

        override fun onShowFileChooser(webView: WebView, filePathCallback: ValueCallback<Array<Uri>>, fileChooserParams: FileChooserParams): Boolean {
            (_prompt.value as? BrowserPrompt.FileChooser)?.callback?.onReceiveValue(null)
            _prompt.value = BrowserPrompt.FileChooser(fileChooserParams, filePathCallback)
            return true
        }
    }
}
