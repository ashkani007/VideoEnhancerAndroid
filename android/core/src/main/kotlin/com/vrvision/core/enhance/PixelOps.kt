package com.vrvision.core.enhance

import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/** YCbCr ↔ RGB matrix (limited/"video" range, 8-bit). */
enum class ColorMatrix(val kr: Float, val kb: Float) {
    BT601(0.299f, 0.114f),
    BT709(0.2126f, 0.0722f);

    companion object {
        /** Convention when the stream does not signal it: HD and larger use BT.709. */
        fun forHeight(height: Int) = if (height >= 720) BT709 else BT601
    }
}

/**
 * A YUV 4:2:0 image described by plane buffers and strides, matching android.media.Image
 * (I420, NV12 and NV21 all fit: NV12 is U/V sharing one buffer with pixelStride 2).
 */
class Yuv420(
    val width: Int,
    val height: Int,
    val y: ByteArray, val yOffset: Int, val yRowStride: Int,
    val u: ByteArray, val uOffset: Int, val uRowStride: Int, val uPixelStride: Int,
    val v: ByteArray, val vOffset: Int, val vRowStride: Int, val vPixelStride: Int,
) {
    companion object {
        /** Tightly packed I420 in one array. */
        fun i420(width: Int, height: Int, data: ByteArray = ByteArray(width * height * 3 / 2)): Yuv420 {
            val cw = (width + 1) / 2; val ch = (height + 1) / 2
            return Yuv420(width, height, data, 0, width, data, width * height, cw, 1, data, width * height + cw * ch, cw, 1)
        }
    }
}

object PixelOps {

    private fun clamp8(v: Float): Int = v.roundToInt().coerceIn(0, 255)

    /** Converts a full YUV frame to packed 8-bit RGB (3 bytes per pixel). */
    fun yuvToRgb(src: Yuv420, m: ColorMatrix, out: ByteArray = ByteArray(src.width * src.height * 3)): ByteArray {
        val kg = 1f - m.kr - m.kb
        val crR = 2f * (1f - m.kr)
        val cbB = 2f * (1f - m.kb)
        val cbG = -2f * m.kb * (1f - m.kb) / kg
        val crG = -2f * m.kr * (1f - m.kr) / kg
        val ys = 255f / 219f; val cs = 255f / 224f
        var o = 0
        for (row in 0 until src.height) {
            val yRow = src.yOffset + row * src.yRowStride
            val cRow = row / 2
            for (col in 0 until src.width) {
                val yv = ((src.y[yRow + col].toInt() and 0xFF) - 16) * ys
                val ci = col / 2
                val cb = ((src.u[src.uOffset + cRow * src.uRowStride + ci * src.uPixelStride].toInt() and 0xFF) - 128) * cs
                val cr = ((src.v[src.vOffset + cRow * src.vRowStride + ci * src.vPixelStride].toInt() and 0xFF) - 128) * cs
                out[o++] = clamp8(yv + crR * cr).toByte()
                out[o++] = clamp8(yv + cbG * cb + crG * cr).toByte()
                out[o++] = clamp8(yv + cbB * cb).toByte()
            }
        }
        return out
    }

    /**
     * Writes RGB (float, 0..1, CHW planes of [w]×[h]) into a YUV 4:2:0 destination at
     * ([dx], [dy]). Chroma is averaged over each 2×2 block; [dx]/[dy]/[w]/[h] must be even
     * except at the right/bottom frame edge.
     */
    fun rgbPlanarToYuv(rgb: FloatArray, w: Int, h: Int, dst: Yuv420, dx: Int, dy: Int, m: ColorMatrix) {
        val kg = 1f - m.kr - m.kb
        val plane = w * h
        for (row in 0 until h) {
            val yRow = dst.yOffset + (dy + row) * dst.yRowStride + dx
            for (col in 0 until w) {
                val i = row * w + col
                val yv = m.kr * rgb[i] + kg * rgb[plane + i] + m.kb * rgb[2 * plane + i]
                dst.y[yRow + col] = clamp8(16f + 219f * yv.coerceIn(0f, 1f)).toByte()
            }
        }
        var row = 0
        while (row < h) {
            var col = 0
            while (col < w) {
                var r = 0f; var g = 0f; var b = 0f; var n = 0
                for (yy in row until min(row + 2, h)) for (xx in col until min(col + 2, w)) {
                    val i = yy * w + xx
                    r += rgb[i]; g += rgb[plane + i]; b += rgb[2 * plane + i]; n++
                }
                r /= n; g /= n; b /= n
                val yv = m.kr * r + kg * g + m.kb * b
                val cb = (b - yv) / (2f * (1f - m.kb))
                val cr = (r - yv) / (2f * (1f - m.kr))
                val cx = (dx + col) / 2; val cy = (dy + row) / 2
                dst.u[dst.uOffset + cy * dst.uRowStride + cx * dst.uPixelStride] = clamp8(128f + 224f * cb.coerceIn(-0.5f, 0.5f)).toByte()
                dst.v[dst.vOffset + cy * dst.vRowStride + cx * dst.vPixelStride] = clamp8(128f + 224f * cr.coerceIn(-0.5f, 0.5f)).toByte()
                col += 2
            }
            row += 2
        }
    }

    /**
     * Copies a window of a packed RGB frame into a float CHW tensor (0..1). Pixels outside
     * [region] are filled by replicating the nearest region pixel, so the model never sees
     * data from another eye or outside the frame.
     */
    fun extractWindow(rgb: ByteArray, frameW: Int, window: Rect, region: Rect, out: FloatArray = FloatArray(3 * window.w * window.h)): FloatArray {
        val plane = window.w * window.h
        for (row in 0 until window.h) {
            val sy = (window.y + row).coerceIn(region.y, region.bottom - 1)
            for (col in 0 until window.w) {
                val sx = (window.x + col).coerceIn(region.x, region.right - 1)
                val s = (sy * frameW + sx) * 3
                val i = row * window.w + col
                out[i] = (rgb[s].toInt() and 0xFF) / 255f
                out[plane + i] = (rgb[s + 1].toInt() and 0xFF) / 255f
                out[2 * plane + i] = (rgb[s + 2].toInt() and 0xFF) / 255f
            }
        }
        return out
    }

    /** Crops a CHW float tensor. */
    fun crop(src: FloatArray, srcW: Int, srcH: Int, x: Int, y: Int, w: Int, h: Int): FloatArray {
        val out = FloatArray(3 * w * h)
        val sp = srcW * srcH; val dp = w * h
        for (c in 0 until 3) for (row in 0 until h) {
            System.arraycopy(src, c * sp + (y + row) * srcW + x, out, c * dp + row * w, w)
        }
        return out
    }

    /**
     * Area-weighted (box) resampling of a CHW float image by an arbitrary factor ≤ 1 per axis
     * (downscaling). Each output pixel is the exact coverage-weighted mean of the input
     * pixels it overlaps, which avoids aliasing when reducing the model's 4× output to the
     * requested scale.
     */
    fun areaResize(src: FloatArray, sw: Int, sh: Int, dw: Int, dh: Int): FloatArray {
        require(dw in 1..sw && dh in 1..sh) { "areaResize only downsamples" }
        val tmp = FloatArray(3 * dw * sh)
        val fx = sw.toDouble() / dw
        for (c in 0 until 3) for (y in 0 until sh) {
            val rowIn = c * sw * sh + y * sw
            val rowOut = c * dw * sh + y * dw
            for (x in 0 until dw) tmp[rowOut + x] = coverage(src, rowIn, 1, x * fx, (x + 1) * fx, sw)
        }
        val out = FloatArray(3 * dw * dh)
        val fy = sh.toDouble() / dh
        for (c in 0 until 3) for (x in 0 until dw) {
            val colIn = c * dw * sh + x
            for (y in 0 until dh) out[c * dw * dh + y * dw + x] = coverage(tmp, colIn, dw, y * fy, (y + 1) * fy, sh)
        }
        return out
    }

    private fun coverage(a: FloatArray, base: Int, step: Int, start: Double, end: Double, n: Int): Float {
        var sum = 0.0
        var i = floor(start).toInt()
        while (i < end && i < n) {
            val w = min(end, i + 1.0) - max(start, i.toDouble())
            if (w > 0) sum += a[base + i * step] * w
            i++
        }
        return (sum / (end - start)).toFloat()
    }

    /**
     * Conservative unsharp mask on the luma plane (conventional filter, not AI):
     * Y' = Y + amount·(Y − blur3x3(Y)) where the difference exceeds [threshold] (to avoid
     * amplifying noise). [amount] is clamped to 0..1.
     */
    fun unsharpLuma(img: Yuv420, amount: Float, threshold: Int = 3) {
        val a = amount.coerceIn(0f, 1f)
        if (a == 0f) return
        val w = img.width; val h = img.height
        val src = ByteArray(w * h)
        for (row in 0 until h) System.arraycopy(img.y, img.yOffset + row * img.yRowStride, src, row * w, w)
        for (row in 0 until h) {
            for (col in 0 until w) {
                var sum = 0
                for (dy in -1..1) {
                    val yy = (row + dy).coerceIn(0, h - 1)
                    for (dx in -1..1) {
                        val xx = (col + dx).coerceIn(0, w - 1)
                        sum += (src[yy * w + xx].toInt() and 0xFF) * (if (dx == 0 && dy == 0) 4 else if (dx == 0 || dy == 0) 2 else 1)
                    }
                }
                val orig = src[row * w + col].toInt() and 0xFF
                val diff = orig - sum / 16f
                if (kotlin.math.abs(diff) > threshold) {
                    img.y[img.yOffset + row * img.yRowStride + col] = (orig + a * diff).roundToInt().coerceIn(16, 235).toByte()
                }
            }
        }
    }
}
