package com.vrvision.core.browser

import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.FormatHints
import com.vrvision.core.stereo.FormatSuggestion
import com.vrvision.core.stereo.StereoLayout
import java.net.URI
import java.net.URLDecoder

enum class MediaKind(val label: String, val mime: String?) {
    MP4("MP4", "video/mp4"),
    WEBM("WebM", "video/webm"),
    HLS("HLS stream", "application/x-mpegURL"),
    DASH("DASH stream", "application/dash+xml"),
    BLOB("Page-generated stream (blob)", null),
    UNKNOWN("Unknown format", null);

    val isAdaptiveStream: Boolean get() = this == HLS || this == DASH
    val isProgressiveFile: Boolean get() = this == MP4 || this == WEBM
}

enum class MediaOrigin { VIDEO_ELEMENT, NETWORK_REQUEST, LINK }

/** A media source seen on a page. Contains only URLs the page itself exposes; never credentials. */
data class MediaCandidate(
    val url: String,
    val kind: MediaKind,
    val pageUrl: String,
    val pageTitle: String = "",
    val declaredType: String? = null,
    /** The page's video element has Encrypted Media Extensions keys attached (DRM). */
    val drmProtected: Boolean = false,
    val origin: MediaOrigin = MediaOrigin.VIDEO_ELEMENT,
)

/** What VRVision may do with a candidate and why. */
data class MediaAssessment(
    val candidate: MediaCandidate,
    val canPlay: Boolean,
    val playReason: String,
    val canEnhance: Boolean,
    val enhanceReason: String,
    val format: FormatSuggestion,
)

object MediaDetector {

    /** Script run with WebView.evaluateJavascript (no JavaScript bridge). Returns one line per source. */
    val DETECTION_SCRIPT: String = """
        (function(){
          var out=[]; var enc=encodeURIComponent;
          var vids=document.querySelectorAll('video');
          for (var i=0;i<vids.length;i++){
            var v=vids[i]; var drm=(v.mediaKeys?1:0);
            var srcs=[];
            if (v.currentSrc) srcs.push([v.currentSrc,'']);
            if (v.getAttribute('src')) srcs.push([v.src,'']);
            var s=v.querySelectorAll('source');
            for (var j=0;j<s.length;j++){ if (s[j].src) srcs.push([s[j].src, s[j].type||'']); }
            for (var k=0;k<srcs.length;k++){ out.push('V\t'+enc(srcs[k][0])+'\t'+enc(srcs[k][1])+'\t'+drm); }
          }
          var a=document.querySelectorAll('a[href]');
          for (var n=0;n<a.length && n<500;n++){
            var h=a[n].href||''; if (/\.(mp4|webm|m3u8|mpd)(\?|#|$)/i.test(h)) out.push('L\t'+enc(h)+'\t\t0');
          }
          return 'T\t'+enc(document.title||'')+'\n'+out.join('\n');
        })();
    """.trimIndent()

    fun kindOf(url: String, mime: String? = null): MediaKind {
        val m = mime?.lowercase()?.substringBefore(';')?.trim().orEmpty()
        if (url.startsWith("blob:", true)) return MediaKind.BLOB
        when {
            m == "video/mp4" || m == "video/quicktime" -> return MediaKind.MP4
            m == "video/webm" -> return MediaKind.WEBM
            m == "application/x-mpegurl" || m == "application/vnd.apple.mpegurl" || m == "audio/mpegurl" -> return MediaKind.HLS
            m == "application/dash+xml" -> return MediaKind.DASH
        }
        val path = try { URI(url).path.orEmpty().lowercase() } catch (_: Exception) { url.substringBefore('?').lowercase() }
        return when {
            path.endsWith(".mp4") || path.endsWith(".m4v") || path.endsWith(".mov") -> MediaKind.MP4
            path.endsWith(".webm") -> MediaKind.WEBM
            path.endsWith(".m3u8") -> MediaKind.HLS
            path.endsWith(".mpd") -> MediaKind.DASH
            else -> MediaKind.UNKNOWN
        }
    }

    /** Media-like network request (observed, not intercepted) worth listing. */
    fun isMediaRequest(url: String): Boolean = kindOf(url).let { it != MediaKind.UNKNOWN && it != MediaKind.BLOB }

    /** Parses the output of [DETECTION_SCRIPT] (as decoded from the JSON string evaluateJavascript returns). */
    fun parseScriptResult(raw: String, pageUrl: String): List<MediaCandidate> {
        var title = ""
        val out = mutableListOf<MediaCandidate>()
        for (line in raw.split('\n')) {
            val f = line.split('\t')
            when (f.firstOrNull()) {
                "T" -> title = dec(f.getOrNull(1))
                "V", "L" -> {
                    val url = dec(f.getOrNull(1))
                    if (url.isBlank()) continue
                    val type = dec(f.getOrNull(2)).ifBlank { null }
                    out += MediaCandidate(
                        url = url, kind = kindOf(url, type), pageUrl = pageUrl, declaredType = type,
                        drmProtected = f.getOrNull(3) == "1",
                        origin = if (f[0] == "V") MediaOrigin.VIDEO_ELEMENT else MediaOrigin.LINK,
                    )
                }
            }
        }
        return merge(out.map { it.copy(pageTitle = title) })
    }

    /** De-duplicates by URL, keeping the most informative entry (DRM flag and element origin win). */
    fun merge(candidates: List<MediaCandidate>): List<MediaCandidate> =
        candidates.groupBy { it.url }.map { (_, group) ->
            val best = group.firstOrNull { it.origin == MediaOrigin.VIDEO_ELEMENT } ?: group.first()
            best.copy(
                drmProtected = group.any { it.drmProtected },
                kind = group.map { it.kind }.firstOrNull { it != MediaKind.UNKNOWN } ?: best.kind,
            )
        }

    fun assess(c: MediaCandidate): MediaAssessment {
        val nameForHints = listOf(c.url.substringAfterLast('/').substringBefore('?'), c.pageTitle).joinToString(" ")
        val format = FormatHints.suggest(nameForHints, 0, 0).let {
            // Without dimensions only name hints count; fall back to flat mono.
            if (it.confident) it else FormatSuggestion(StereoLayout.MONO, ProjectionType.FLAT, false, listOf("No VR hints in the name or page title; assuming flat 2D."))
        }
        val secure = c.url.startsWith("https://", true)
        val (canPlay, playReason) = when {
            c.drmProtected -> false to "This video is DRM-protected. VRVision does not bypass DRM; watch it in the page."
            c.kind == MediaKind.BLOB -> false to "The page generates this stream in script (blob URL); it can only be played in the page."
            c.kind == MediaKind.UNKNOWN -> false to "The format can't be identified as MP4, WebM, HLS or DASH."
            !secure -> false to "Only HTTPS sources are opened in the player."
            else -> true to "${c.kind.label} can be played with the native player. Sites that require login or block other players may still refuse it."
        }
        val (canEnhance, enhanceReason) = when {
            !canPlay -> false to playReason
            c.kind.isAdaptiveStream -> false to "Adaptive streams (HLS/DASH) can be played but not enhanced: enhancement needs a single downloadable file."
            else -> true to "This file can be downloaded with your confirmation and then enhanced like a local video."
        }
        return MediaAssessment(c, canPlay, playReason, canEnhance, enhanceReason, format)
    }

    private fun dec(s: String?): String = try { URLDecoder.decode(s.orEmpty(), "UTF-8") } catch (_: Exception) { "" }
}
