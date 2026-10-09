package com.vrvision.core.enhance

import com.vrvision.core.stereo.StereoLayout
import kotlin.math.roundToInt

/** A super-resolution network with a fixed square input window. */
interface SrEngine {
    /** Native upscale factor of the network (e.g. 4). */
    val scale: Int
    /** Input window size in pixels (fixed tensor shape). */
    val window: Int
    /**
     * Runs the network on a CHW float tensor of [window]² pixels in 0..1 and returns
     * CHW floats of (window·scale)² pixels in 0..1.
     */
    fun run(input: FloatArray): FloatArray
}

/**
 * Upscales one RGB frame with tiled inference:
 * windows are cut per eye region (no cross-eye context), each window is run through the
 * network, only its core is kept, and the core is area-resampled from the network's native
 * scale to the requested output scale before being written into the output frame.
 */
class FrameUpscaler(private val engine: SrEngine, private val overlap: Int = 16) {

    private val windowBuf = FloatArray(3 * engine.window * engine.window)

    fun tileCount(srcW: Int, srcH: Int, layout: StereoLayout): Int =
        TilePlanner.tiles(srcW, srcH, layout, engine.window, overlap).size

    /**
     * @param src packed RGB of srcW×srcH
     * @param out packed RGB of outW×outH (written completely)
     * @param beforeTile called before each tile, e.g. to check for cancellation
     */
    fun upscale(
        src: ByteArray, srcW: Int, srcH: Int, layout: StereoLayout,
        out: ByteArray, outW: Int, outH: Int,
        beforeTile: (index: Int, total: Int) -> Unit = { _, _ -> },
    ) {
        require(outW <= srcW * engine.scale && outH <= srcH * engine.scale) { "Output exceeds the model's native scale" }
        require(outW >= srcW && outH >= srcH) { "Output must not be smaller than the source" }
        val s = engine.scale
        val sx = outW.toDouble() / srcW
        val sy = outH.toDouble() / srcH
        val tiles = TilePlanner.tiles(srcW, srcH, layout, engine.window, overlap)
        tiles.forEachIndexed { i, t ->
            beforeTile(i, tiles.size)
            PixelOps.extractWindow(src, srcW, t.window, t.region, windowBuf)
            val sr = engine.run(windowBuf)
            val nativeSize = engine.window * s
            val core = PixelOps.crop(sr, nativeSize, nativeSize, (t.core.x - t.window.x) * s, (t.core.y - t.window.y) * s, t.core.w * s, t.core.h * s)
            val x0 = (t.core.x * sx).roundToInt(); val x1 = (t.core.right * sx).roundToInt()
            val y0 = (t.core.y * sy).roundToInt(); val y1 = (t.core.bottom * sy).roundToInt()
            val tw = x1 - x0; val th = y1 - y0
            if (tw <= 0 || th <= 0) return@forEachIndexed
            val placed = if (tw == t.core.w * s && th == t.core.h * s) core
            else PixelOps.areaResize(core, t.core.w * s, t.core.h * s, tw, th)
            PixelOps.writePlanarToPacked(placed, tw, th, out, outW, x0, y0)
        }
    }
}

/** Reference engine: exact nearest-neighbour upscale. Used in tests and as a pipeline self-check. */
class NearestEngine(override val scale: Int = 4, override val window: Int = 64) : SrEngine {
    override fun run(input: FloatArray): FloatArray {
        val n = window; val o = n * scale
        val out = FloatArray(3 * o * o)
        for (c in 0 until 3) for (y in 0 until o) for (x in 0 until o) {
            out[c * o * o + y * o + x] = input[c * n * n + (y / scale) * n + (x / scale)]
        }
        return out
    }
}
