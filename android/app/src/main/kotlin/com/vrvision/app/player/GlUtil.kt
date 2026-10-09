package com.vrvision.app.player

import android.opengl.GLES30
import android.util.Log
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.nio.ShortBuffer

internal object GlUtil {
    private const val TAG = "VRVisionGL"

    fun program(vertex: String, fragment: String): Int {
        val vs = shader(GLES30.GL_VERTEX_SHADER, vertex)
        val fs = shader(GLES30.GL_FRAGMENT_SHADER, fragment)
        val p = GLES30.glCreateProgram()
        GLES30.glAttachShader(p, vs)
        GLES30.glAttachShader(p, fs)
        GLES30.glLinkProgram(p)
        val ok = IntArray(1)
        GLES30.glGetProgramiv(p, GLES30.GL_LINK_STATUS, ok, 0)
        if (ok[0] == 0) {
            val log = GLES30.glGetProgramInfoLog(p)
            GLES30.glDeleteProgram(p)
            throw IllegalStateException("Program link failed: $log")
        }
        GLES30.glDeleteShader(vs)
        GLES30.glDeleteShader(fs)
        return p
    }

    private fun shader(type: Int, src: String): Int {
        val s = GLES30.glCreateShader(type)
        GLES30.glShaderSource(s, src)
        GLES30.glCompileShader(s)
        val ok = IntArray(1)
        GLES30.glGetShaderiv(s, GLES30.GL_COMPILE_STATUS, ok, 0)
        if (ok[0] == 0) {
            val log = GLES30.glGetShaderInfoLog(s)
            GLES30.glDeleteShader(s)
            throw IllegalStateException("Shader compile failed: $log")
        }
        return s
    }

    fun floats(a: FloatArray): FloatBuffer =
        ByteBuffer.allocateDirect(a.size * 4).order(ByteOrder.nativeOrder()).asFloatBuffer().apply { put(a); position(0) }

    fun shorts(a: ShortArray): ShortBuffer =
        ByteBuffer.allocateDirect(a.size * 2).order(ByteOrder.nativeOrder()).asShortBuffer().apply { put(a); position(0) }

    fun checkError(where: String) {
        val e = GLES30.glGetError()
        if (e != GLES30.GL_NO_ERROR) Log.w(TAG, "GL error 0x${Integer.toHexString(e)} at $where")
    }
}

/** Color texture + framebuffer for one eye's undistorted render. */
internal class EyeTarget {
    var fbo = 0; private set
    var texture = 0; private set
    var width = 0; private set
    var height = 0; private set

    fun ensure(w: Int, h: Int) {
        if (w == width && h == height && fbo != 0) return
        release()
        width = w; height = h
        val ids = IntArray(1)
        GLES30.glGenTextures(1, ids, 0); texture = ids[0]
        GLES30.glBindTexture(GLES30.GL_TEXTURE_2D, texture)
        GLES30.glTexImage2D(GLES30.GL_TEXTURE_2D, 0, GLES30.GL_RGBA8, w, h, 0, GLES30.GL_RGBA, GLES30.GL_UNSIGNED_BYTE, null)
        GLES30.glTexParameteri(GLES30.GL_TEXTURE_2D, GLES30.GL_TEXTURE_MIN_FILTER, GLES30.GL_LINEAR)
        GLES30.glTexParameteri(GLES30.GL_TEXTURE_2D, GLES30.GL_TEXTURE_MAG_FILTER, GLES30.GL_LINEAR)
        GLES30.glTexParameteri(GLES30.GL_TEXTURE_2D, GLES30.GL_TEXTURE_WRAP_S, GLES30.GL_CLAMP_TO_EDGE)
        GLES30.glTexParameteri(GLES30.GL_TEXTURE_2D, GLES30.GL_TEXTURE_WRAP_T, GLES30.GL_CLAMP_TO_EDGE)
        GLES30.glGenFramebuffers(1, ids, 0); fbo = ids[0]
        GLES30.glBindFramebuffer(GLES30.GL_FRAMEBUFFER, fbo)
        GLES30.glFramebufferTexture2D(GLES30.GL_FRAMEBUFFER, GLES30.GL_COLOR_ATTACHMENT0, GLES30.GL_TEXTURE_2D, texture, 0)
        val status = GLES30.glCheckFramebufferStatus(GLES30.GL_FRAMEBUFFER)
        GLES30.glBindFramebuffer(GLES30.GL_FRAMEBUFFER, 0)
        check(status == GLES30.GL_FRAMEBUFFER_COMPLETE) { "Eye framebuffer incomplete: $status" }
    }

    fun release() {
        if (fbo != 0) GLES30.glDeleteFramebuffers(1, intArrayOf(fbo), 0)
        if (texture != 0) GLES30.glDeleteTextures(1, intArrayOf(texture), 0)
        fbo = 0; texture = 0; width = 0; height = 0
    }
}

internal object Shaders {
    const val SCENE_VS = """#version 300 es
uniform mat4 uMvp;
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aUv;
out vec2 vUv;
void main() {
    vUv = aUv;
    gl_Position = uMvp * vec4(aPos, 1.0);
}
"""

    /**
     * Samples the eye's region of the decoded frame. vUv is eye-local image space (v down);
     * it is mapped into the frame, clamped half a texel inside the eye rectangle so linear
     * filtering never blends the other eye's pixels at the seam, then transformed by the
     * SurfaceTexture matrix (which expects GL texture space, v up).
     */
    const val SCENE_FS = """#version 300 es
#extension GL_OES_EGL_image_external_essl3 : require
precision mediump float;
uniform samplerExternalOES uTex;
uniform mat4 uStMatrix;
uniform vec4 uEyeRect;     // u0, v0, u1, v1 in image space
uniform vec2 uHalfTexel;   // 0.5 / frame size
in vec2 vUv;
out vec4 fragColor;
void main() {
    vec2 img = mix(uEyeRect.xy, uEyeRect.zw, vUv);
    img = clamp(img, uEyeRect.xy + uHalfTexel, uEyeRect.zw - uHalfTexel);
    vec2 tex = (uStMatrix * vec4(img.x, 1.0 - img.y, 0.0, 1.0)).xy;
    fragColor = texture(uTex, tex);
}
"""

    const val QUAD_VS = """#version 300 es
layout(location = 0) in vec2 aPos;
out vec2 vUv;
void main() {
    // vUv in viewport space with v pointing down, matching core DistortionModel.
    vUv = vec2(aPos.x * 0.5 + 0.5, 0.5 - aPos.y * 0.5);
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

    /** Mirrors com.vrvision.core.calibration.DistortionModel.sourceCoord. */
    const val DISTORT_FS = """#version 300 es
precision highp float;
uniform sampler2D uEye;
uniform vec2 uCenter;
uniform float uAspect;
uniform float uK1;
uniform float uK2;
uniform vec2 uImageOffset;
uniform float uMargin;
in vec2 vUv;
out vec4 fragColor;
void main() {
    if (vUv.x < uMargin || vUv.x > 1.0 - uMargin || vUv.y < uMargin || vUv.y > 1.0 - uMargin) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    vec2 d = vUv - uCenter;
    vec2 da = vec2(d.x * uAspect, d.y);
    float r2 = dot(da, da);
    float s = 1.0 + uK1 * r2 + uK2 * r2 * r2;
    vec2 src = uCenter + d * s - uImageOffset;
    if (src.x < 0.0 || src.x > 1.0 || src.y < 0.0 || src.y > 1.0) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    fragColor = texture(uEye, vec2(src.x, 1.0 - src.y));
}
"""

    /**
     * Calibration pattern drawn into each eye's undistorted image: a 10x10 grid, a cross
     * at the lens center and an eye marker (left: red dot on the left, right: blue dot on
     * the right) so users can verify that eyes are not swapped by closing one eye.
     */
    const val PATTERN_FS = """#version 300 es
precision highp float;
uniform vec2 uCenter;
uniform float uAspect;
uniform float uEye;        // 0 = left, 1 = right
uniform float uPattern;    // 1 = grid, 2 = checkerboard
in vec2 vUv;
out vec4 fragColor;
float line(float c, float w) { float f = abs(fract(c) - 0.5); return smoothstep(0.5 - w, 0.5, f); }
void main() {
    vec2 p = vec2((vUv.x - uCenter.x) * uAspect, vUv.y - uCenter.y);
    vec3 col = vec3(0.05);
    if (uPattern > 1.5) {
        vec2 c = floor(p * 10.0);
        col = mod(c.x + c.y, 2.0) < 0.5 ? vec3(0.85) : vec3(0.1);
    } else {
        float g = max(line(p.x * 10.0 + 0.5, 0.04), line(p.y * 10.0 + 0.5, 0.04));
        col = mix(col, vec3(0.75), g);
    }
    float cr = (abs(p.x) < 0.003 || abs(p.y) < 0.003) && length(p) < 0.08 ? 1.0 : 0.0;
    col = mix(col, vec3(0.2, 1.0, 0.3), cr);
    vec2 marker = vec2(uEye < 0.5 ? -0.3 : 0.3, 0.0);
    if (length(p - marker) < 0.04) col = uEye < 0.5 ? vec3(1.0, 0.2, 0.2) : vec3(0.2, 0.4, 1.0);
    fragColor = vec4(col, 1.0);
}
"""
}
