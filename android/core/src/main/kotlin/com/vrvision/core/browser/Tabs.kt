package com.vrvision.core.browser

/** One browser tab as persisted for session restore (never contains cookies or form data). */
data class BrowserTab(
    val id: Long,
    val url: String,
    val title: String = "",
    val createdAt: Long = 0,
)

data class TabState(val tabs: List<BrowserTab> = emptyList(), val activeId: Long? = null) {
    val active: BrowserTab? get() = tabs.firstOrNull { it.id == activeId }
}

/**
 * Pure tab bookkeeping. There is always at least one tab after [ensureOne]; closing the active
 * tab activates its right neighbour (or the left one at the end), like desktop browsers.
 */
object TabManager {
    const val MAX_TABS = 16

    fun ensureOne(s: TabState, newId: () -> Long, homeUrl: String = UrlPolicy.HOME_URL): TabState =
        if (s.tabs.isEmpty()) open(s, homeUrl, newId()) else if (s.active == null) s.copy(activeId = s.tabs.last().id) else s

    /** Opens a tab and makes it active. Returns the state unchanged when the limit is reached. */
    fun open(s: TabState, url: String, id: Long, now: Long = 0): TabState {
        if (s.tabs.size >= MAX_TABS) return s
        require(s.tabs.none { it.id == id }) { "Duplicate tab id $id" }
        return TabState(s.tabs + BrowserTab(id, url, createdAt = now), id)
    }

    fun close(s: TabState, id: Long): TabState {
        val idx = s.tabs.indexOfFirst { it.id == id }
        if (idx < 0) return s
        val remaining = s.tabs.toMutableList().apply { removeAt(idx) }
        val active = when {
            s.activeId != id -> s.activeId
            remaining.isEmpty() -> null
            idx < remaining.size -> remaining[idx].id
            else -> remaining.last().id
        }
        return TabState(remaining, active)
    }

    fun select(s: TabState, id: Long): TabState = if (s.tabs.any { it.id == id }) s.copy(activeId = id) else s

    fun update(s: TabState, id: Long, url: String? = null, title: String? = null): TabState =
        s.copy(tabs = s.tabs.map { if (it.id == id) it.copy(url = url ?: it.url, title = title ?: it.title) else it })

    fun canOpen(s: TabState) = s.tabs.size < MAX_TABS
}
