package com.vrvision.app.player

import android.graphics.SurfaceTexture
import android.opengl.GLES11Ext
import android.opengl.GLES30
import android.opengl.GLSurfaceView
import android.opengl.Matrix
import android.view.Surface
import com.vrvision.core.calibration.EyeViewport
import com.vrvision.core.calibration.HeadsetCalibration
import com.vrvision.core.calibration.ViewportLayout
import com.vrvision.core.math.Quaternion
import com.vrvision.core.projection.FlatScreenConfig
import com.vrvision.core.projection.Mesh
import com.vrvision.core.projection.MeshFactory
import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.Eye
import com.vrvision.core.stereo.StereoLayout
import com.vrvision.core.stereo.StereoMapper
import com.vrvision.core.stereo.StereoPacking
import java.util.concurrent.atomic.AtomicBoolean
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10

enum class TestPattern { NONE, GRID, CHECKERBOARD }

/** Everything the renderer needs; replaced atomically from the UI thread. */
data class RenderConfig(
    val layout: StereoLayout = StereoLayout.MONO,
    val packing: StereoPacking = StereoPacking.HALF,
    val projection: ProjectionType = ProjectionType.FLAT,
    val swapEyes: Boolean = false,
    val calibration: HeadsetCalibration = HeadsetCalibration(),
    val headsetMode: Boolean = true,
    val flatScreen: FlatScreenConfig = FlatScreenConfig(),
    val pattern: TestPattern = TestPattern.NONE,
    /** Gaze reticle at the lens center (VR browser). Progress 0..1 fills it during a dwell. */
    val reticle: Boolean = false,
    val reticleProgress: Float = 0f,
    val xdpi: Float = 0f,
    val ydpi: Float = 0f,
    /** Symmetric horizontal inset protecting against the camera cutout. */
    val horizontalInsetPx: Int = 0,
)

/**
 * Renders decoded video frames for one or two eyes.
 *
 * Pass 1 renders each eye's undistorted view into its own framebuffer (video on the
 * projection mesh, or a calibration pattern). Pass 2 draws each eye's framebuffer into its
 * screen viewport with radial pre-distortion around that eye's lens center.
 */
class VrRenderer(
    private val onSurfaceReady: (Surface) -> Unit,
    private val orientation: () -> Quaternion,
    /** For producers that draw with a Canvas (the VR browser), the buffer size to allocate. */
    private val sourceBufferSize: Pair<Int, Int>? = null,
) : GLSurfaceView.Renderer, SurfaceTexture.OnFrameAvailableListener {

    @Volatile var config = RenderConfig()
    @Volatile var videoWidth = 0
    @Volatile var videoHeight = 0

    private var surfaceTexture: SurfaceTexture? = null
    private var surface: Surface? = null
    private var oesTexture = 0
    private val frameAvailable = AtomicBoolean(false)
    private val stMatrix = FloatArray(16).also { Matrix.setIdentityM(it, 0) }

    private var sceneProgram = 0
    private var distortProgram = 0
    private var patternProgram = 0
    private val vao = IntArray(2)
    private val vbo = IntArray(4)
    private var meshIndexCount = 0
    private var builtMeshKey: Any? = null

    private val eyeTargets = arrayOf(EyeTarget(), EyeTarget())
    private var surfaceW = 0
    private var surfaceH = 0

    private val proj = FloatArray(16)
    private val view = FloatArray(16)
    private val mvp = FloatArray(16)
    private val shift = FloatArray(16)
    private val shifted = FloatArray(16)
    private val quadBuffer = GlUtil.floats(floatArrayOf(-1f, -1f, 1f, -1f, -1f, 1f, 1f, 1f))

    override fun onSurfaceCreated(gl: GL10?, cfg: EGLConfig?) {
        sceneProgram = GlUtil.program(Shaders.SCENE_VS, Shaders.SCENE_FS)
        distortProgram = GlUtil.program(Shaders.QUAD_VS, Shaders.DISTORT_FS)
        patternProgram = GlUtil.program(Shaders.QUAD_VS, Shaders.PATTERN_FS)

        val tex = IntArray(1)
        GLES30.glGenTextures(1, tex, 0)
        oesTexture = tex[0]
        GLES30.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, oesTexture)
        GLES30.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES30.GL_TEXTURE_MIN_FILTER, GLES30.GL_LINEAR)
        GLES30.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES30.GL_TEXTURE_MAG_FILTER, GLES30.GL_LINEAR)
        GLES30.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES30.GL_TEXTURE_WRAP_S, GLES30.GL_CLAMP_TO_EDGE)
        GLES30.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES30.GL_TEXTURE_WRAP_T, GLES30.GL_CLAMP_TO_EDGE)

        GLES30.glGenVertexArrays(2, vao, 0)
        GLES30.glGenBuffers(4, vbo, 0)
        // Full-screen quad VAO (index 1).
        GLES30.glBindVertexArray(vao[1])
        GLES30.glBindBuffer(GLES30.GL_ARRAY_BUFFER, vbo[3])
        GLES30.glBufferData(GLES30.GL_ARRAY_BUFFER, 8 * 4, quadBuffer, GLES30.GL_STATIC_DRAW)
        GLES30.glEnableVertexAttribArray(0)
        GLES30.glVertexAttribPointer(0, 2, GLES30.GL_FLOAT, false, 0, 0)
        GLES30.glBindVertexArray(0)
        builtMeshKey = null

        val st = SurfaceTexture(oesTexture)
        sourceBufferSize?.let { (w, h) -> st.setDefaultBufferSize(w, h) }
        st.setOnFrameAvailableListener(this)
        surfaceTexture = st
        val s = Surface(st)
        surface = s
        onSurfaceReady(s)
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        surfaceW = width
        surfaceH = height
    }

    override fun onFrameAvailable(st: SurfaceTexture?) {
        frameAvailable.set(true)
    }

    override fun onDrawFrame(gl: GL10?) {
        val st = surfaceTexture ?: return
        if (frameAvailable.getAndSet(false)) {
            st.updateTexImage()
            st.getTransformMatrix(stMatrix)
        }
        val c = config
        GLES30.glBindFramebuffer(GLES30.GL_FRAMEBUFFER, 0)
        GLES30.glViewport(0, 0, surfaceW, surfaceH)
        GLES30.glClearColor(0f, 0f, 0f, 1f)
        GLES30.glClear(GLES30.GL_COLOR_BUFFER_BIT)
        if (surfaceW < 2 || surfaceH < 2) return

        val eyes: List<Pair<Eye, EyeViewport>> = if (c.headsetMode) {
            val (l, r) = ViewportLayout.compute(surfaceW, surfaceH, c.xdpi, c.ydpi, c.calibration, c.horizontalInsetPx)
            listOf(Eye.LEFT to l, Eye.RIGHT to r)
        } else {
            listOf(Eye.LEFT to EyeViewport(0, 0, surfaceW, surfaceH, 0.5f, 0.5f))
        }

        ensureMesh(c)
        val camera = orientation()
        Matrix.setIdentityM(view, 0)
        camera.conjugate().toMatrix(view)

        for ((index, pair) in eyes.withIndex()) {
            val (eye, vp) = pair
            val target = eyeTargets[index]
            target.ensure(vp.width, vp.height)
            renderEye(c, eye, vp, target)
            // Pass 2: into the screen viewport (GL viewport origin is bottom-left).
            GLES30.glBindFramebuffer(GLES30.GL_FRAMEBUFFER, 0)
            GLES30.glViewport(vp.x, surfaceH - vp.y - vp.height, vp.width, vp.height)
            drawDistorted(c, vp, target)
        }
        GlUtil.checkError("frame")
    }

    private fun renderEye(c: RenderConfig, eye: Eye, vp: EyeViewport, target: EyeTarget) {
        GLES30.glBindFramebuffer(GLES30.GL_FRAMEBUFFER, target.fbo)
        GLES30.glViewport(0, 0, target.width, target.height)
        GLES30.glClearColor(0f, 0f, 0f, 1f)
        GLES30.glClear(GLES30.GL_COLOR_BUFFER_BIT)
        val aspect = vp.width.toFloat() / vp.height

        if (c.pattern != TestPattern.NONE) {
            GLES30.glUseProgram(patternProgram)
            GLES30.glUniform2f(GLES30.glGetUniformLocation(patternProgram, "uCenter"), vp.centerU, vp.centerV)
            GLES30.glUniform1f(GLES30.glGetUniformLocation(patternProgram, "uAspect"), aspect)
            GLES30.glUniform1f(GLES30.glGetUniformLocation(patternProgram, "uEye"), if (eye == Eye.LEFT) 0f else 1f)
            GLES30.glUniform1f(GLES30.glGetUniformLocation(patternProgram, "uPattern"), if (c.pattern == TestPattern.GRID) 1f else 2f)
            drawQuad()
            return
        }
        if (meshIndexCount == 0) return

        val fov = (c.calibration.fovDegrees / c.calibration.zoom).coerceIn(20f, 140f)
        Matrix.perspectiveM(proj, 0, fov, aspect, 0.1f, 100f)
        // Off-axis projection: "straight ahead" must land on this eye's lens center (where the
        // pre-distortion is centered), not on the middle of the eye viewport.
        Matrix.setIdentityM(shift, 0)
        Matrix.translateM(shift, 0, 2f * vp.centerU - 1f, 1f - 2f * vp.centerV, 0f)
        Matrix.multiplyMM(shifted, 0, shift, 0, proj, 0)
        Matrix.multiplyMM(mvp, 0, shifted, 0, view, 0)

        val rect = StereoMapper.eyeRect(c.layout, eye, c.swapEyes)
        GLES30.glUseProgram(sceneProgram)
        GLES30.glUniformMatrix4fv(GLES30.glGetUniformLocation(sceneProgram, "uMvp"), 1, false, mvp, 0)
        GLES30.glUniformMatrix4fv(GLES30.glGetUniformLocation(sceneProgram, "uStMatrix"), 1, false, stMatrix, 0)
        GLES30.glUniform4f(GLES30.glGetUniformLocation(sceneProgram, "uEyeRect"), rect.u0, rect.v0, rect.u1, rect.v1)
        val fw = videoWidth.coerceAtLeast(1); val fh = videoHeight.coerceAtLeast(1)
        GLES30.glUniform2f(GLES30.glGetUniformLocation(sceneProgram, "uHalfTexel"), 0.5f / fw, 0.5f / fh)
        GLES30.glActiveTexture(GLES30.GL_TEXTURE0)
        GLES30.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, oesTexture)
        GLES30.glUniform1i(GLES30.glGetUniformLocation(sceneProgram, "uTex"), 0)
        GLES30.glDisable(GLES30.GL_CULL_FACE)
        GLES30.glBindVertexArray(vao[0])
        GLES30.glDrawElements(GLES30.GL_TRIANGLES, meshIndexCount, GLES30.GL_UNSIGNED_SHORT, 0)
        GLES30.glBindVertexArray(0)
    }

    private fun drawDistorted(c: RenderConfig, vp: EyeViewport, target: EyeTarget) {
        val cal = c.calibration
        val distort = c.headsetMode && cal.distortionEnabled
        GLES30.glUseProgram(distortProgram)
        GLES30.glActiveTexture(GLES30.GL_TEXTURE0)
        GLES30.glBindTexture(GLES30.GL_TEXTURE_2D, target.texture)
        GLES30.glUniform1i(GLES30.glGetUniformLocation(distortProgram, "uEye"), 0)
        GLES30.glUniform2f(GLES30.glGetUniformLocation(distortProgram, "uCenter"), vp.centerU, vp.centerV)
        GLES30.glUniform1f(GLES30.glGetUniformLocation(distortProgram, "uAspect"), vp.width.toFloat() / vp.height)
        GLES30.glUniform1f(GLES30.glGetUniformLocation(distortProgram, "uK1"), if (distort) cal.k1 else 0f)
        GLES30.glUniform1f(GLES30.glGetUniformLocation(distortProgram, "uK2"), if (distort) cal.k2 else 0f)
        GLES30.glUniform2f(GLES30.glGetUniformLocation(distortProgram, "uImageOffset"),
            if (c.headsetMode) cal.imageOffsetX else 0f, if (c.headsetMode) cal.imageOffsetY else 0f)
        GLES30.glUniform1f(GLES30.glGetUniformLocation(distortProgram, "uMargin"), if (c.headsetMode) cal.viewportMargin else 0f)
        GLES30.glUniform2f(GLES30.glGetUniformLocation(distortProgram, "uReticle"), if (c.reticle) 0.012f else 0f, c.reticleProgress)
        drawQuad()
    }

    private fun drawQuad() {
        GLES30.glBindVertexArray(vao[1])
        GLES30.glDrawArrays(GLES30.GL_TRIANGLE_STRIP, 0, 4)
        GLES30.glBindVertexArray(0)
    }

    private fun ensureMesh(c: RenderConfig) {
        val vw = videoWidth; val vh = videoHeight
        val eyeAspect = if (vw > 0 && vh > 0) StereoMapper.eyeAspect(vw, vh, c.layout, c.packing) else 16f / 9f
        val key = listOf(c.projection, eyeAspect, c.flatScreen)
        if (key == builtMeshKey) return
        val mesh: Mesh = MeshFactory.build(c.projection, eyeAspect, c.flatScreen)
        GLES30.glBindVertexArray(vao[0])
        GLES30.glBindBuffer(GLES30.GL_ARRAY_BUFFER, vbo[0])
        GLES30.glBufferData(GLES30.GL_ARRAY_BUFFER, mesh.positions.size * 4, GlUtil.floats(mesh.positions), GLES30.GL_STATIC_DRAW)
        GLES30.glEnableVertexAttribArray(0)
        GLES30.glVertexAttribPointer(0, 3, GLES30.GL_FLOAT, false, 0, 0)
        GLES30.glBindBuffer(GLES30.GL_ARRAY_BUFFER, vbo[1])
        GLES30.glBufferData(GLES30.GL_ARRAY_BUFFER, mesh.uvs.size * 4, GlUtil.floats(mesh.uvs), GLES30.GL_STATIC_DRAW)
        GLES30.glEnableVertexAttribArray(1)
        GLES30.glVertexAttribPointer(1, 2, GLES30.GL_FLOAT, false, 0, 0)
        GLES30.glBindBuffer(GLES30.GL_ELEMENT_ARRAY_BUFFER, vbo[2])
        GLES30.glBufferData(GLES30.GL_ELEMENT_ARRAY_BUFFER, mesh.indices.size * 2, GlUtil.shorts(mesh.indices), GLES30.GL_STATIC_DRAW)
        GLES30.glBindVertexArray(0)
        meshIndexCount = mesh.indices.size
        builtMeshKey = key
    }

    /** Called from the GL thread via queueEvent when the view is torn down. */
    fun release() {
        eyeTargets.forEach { it.release() }
        surface?.release(); surface = null
        surfaceTexture?.release(); surfaceTexture = null
    }
}
