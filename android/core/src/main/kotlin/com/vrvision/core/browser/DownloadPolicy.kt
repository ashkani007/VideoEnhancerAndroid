package com.vrvision.core.browser

import java.net.URI
import java.net.URLDecoder

/** A download the page asked for (from WebView's DownloadListener) or the user requested. */
data class DownloadRequest(
    val url: String,
    val mimeType: String?,
    val contentDisposition: String?,
    val contentLength: Long,
    /** True only when the user tapped something; downloads are never started automatically. */
    val userInitiated: Boolean,
)

enum class DownloadCategory { VIDEO, AUDIO, IMAGE, DOCUMENT, OTHER }

sealed interface DownloadDecision {
    /** May proceed only after the user confirms in a dialog showing these details. */
    data class Confirm(val fileName: String, val category: DownloadCategory, val host: String, val warnings: List<String>) : DownloadDecision
    data class Block(val reason: String) : DownloadDecision
}

/**
 * Download authorization. Nothing downloads without an explicit user action and confirmation;
 * executables and installers are refused; only http(s) URLs are fetched (blob:/data: are page
 * memory, not fetchable); file names are sanitized.
 */
object DownloadPolicy {
    const val MAX_BYTES = 8L * 1024 * 1024 * 1024

    private val dangerousExt = setOf(
        "apk", "apks", "xapk", "aab", "dex", "exe", "msi", "bat", "cmd", "com", "scr", "ps1", "sh", "jar",
        "dmg", "pkg", "deb", "rpm", "app", "vbs", "js", "jse", "wsf", "hta", "lnk", "so",
    )
    private val dangerousMime = setOf(
        "application/vnd.android.package-archive", "application/x-msdownload", "application/x-msdos-program",
        "application/x-sh", "application/java-archive", "application/x-executable",
    )

    fun evaluate(r: DownloadRequest): DownloadDecision {
        if (!r.userInitiated) return DownloadDecision.Block("Downloads only start when you choose them.")
        val scheme = UrlPolicy.schemeOf(r.url)
        if (scheme != "https" && scheme != "http") return DownloadDecision.Block("This file exists only inside the page (${scheme ?: "unknown"}:) and can't be downloaded.")
        val host = UrlPolicy.hostOf(r.url) ?: return DownloadDecision.Block("Invalid download address.")
        val mime = r.mimeType?.lowercase()?.substringBefore(';')?.trim()
        val name = fileName(r.url, r.contentDisposition, mime)
        val ext = name.substringAfterLast('.', "").lowercase()
        if (ext in dangerousExt || mime in dangerousMime) return DownloadDecision.Block("Apps and executable files can't be downloaded in VRVision.")
        if (r.contentLength > MAX_BYTES) return DownloadDecision.Block("The file is larger than 8 GB.")
        val warnings = mutableListOf<String>()
        if (scheme == "http") warnings += "This download is not encrypted (HTTP); it could be altered in transit."
        if (r.contentLength <= 0) warnings += "The size is unknown."
        return DownloadDecision.Confirm(name, category(mime, ext), host, warnings)
    }

    fun category(mime: String?, ext: String): DownloadCategory = when {
        mime?.startsWith("video/") == true || ext in setOf("mp4", "m4v", "mov", "webm", "mkv") -> DownloadCategory.VIDEO
        mime?.startsWith("audio/") == true || ext in setOf("mp3", "m4a", "aac", "ogg", "wav", "flac") -> DownloadCategory.AUDIO
        mime?.startsWith("image/") == true || ext in setOf("jpg", "jpeg", "png", "webp", "gif") -> DownloadCategory.IMAGE
        mime == "application/pdf" || ext in setOf("pdf", "txt", "srt", "vtt") -> DownloadCategory.DOCUMENT
        else -> DownloadCategory.OTHER
    }

    /** Safe file name from Content-Disposition (RFC 6266 incl. filename*), else from the URL path. */
    fun fileName(url: String, contentDisposition: String?, mime: String?): String {
        val fromHeader = contentDisposition?.let { cd ->
            Regex("""filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)""").find(cd)?.groupValues?.get(1)?.let { decode(it) }
                ?: Regex("""filename\s*=\s*"([^"]*)"""").find(cd)?.groupValues?.get(1)
                ?: Regex("""filename\s*=\s*([^;]+)""").find(cd)?.groupValues?.get(1)?.trim()
        }
        val fromUrl = try { URI(url).path?.substringAfterLast('/') } catch (_: Exception) { null }?.let { decode(it) }
        var name = sanitize(fromHeader?.takeIf { it.isNotBlank() } ?: fromUrl?.takeIf { it.isNotBlank() } ?: "download")
        if (!name.contains('.')) extensionFor(mime)?.let { name = "$name.$it" }
        return name
    }

    fun sanitize(name: String): String {
        val cleaned = name.substringAfterLast('/').substringAfterLast('\\')
            .filter { it >= ' ' && it !in "<>:\"|?*" }
            .trim().trimStart('.').ifBlank { "download" }
        if (cleaned.length <= 120) return cleaned
        val ext = cleaned.substringAfterLast('.', "").take(10)
        return cleaned.take(110) + if (ext.isNotEmpty()) ".$ext" else ""
    }

    private fun extensionFor(mime: String?): String? = when (mime) {
        "video/mp4" -> "mp4"; "video/webm" -> "webm"; "video/quicktime" -> "mov"
        "audio/mpeg" -> "mp3"; "image/jpeg" -> "jpg"; "image/png" -> "png"; "application/pdf" -> "pdf"
        else -> null
    }

    private fun decode(s: String) = try { URLDecoder.decode(s, "UTF-8") } catch (_: Exception) { s }
}
