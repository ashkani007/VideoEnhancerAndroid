package com.vrvision.core.math

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

data class Vec3(val x: Float, val y: Float, val z: Float) {
    operator fun plus(o: Vec3) = Vec3(x + o.x, y + o.y, z + o.z)
    operator fun minus(o: Vec3) = Vec3(x - o.x, y - o.y, z - o.z)
    operator fun times(s: Float) = Vec3(x * s, y * s, z * s)
    fun dot(o: Vec3) = x * o.x + y * o.y + z * o.z
    fun cross(o: Vec3) = Vec3(y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x)
    fun length() = sqrt(dot(this))
    fun normalized(): Vec3 { val l = length(); return if (l == 0f) this else this * (1f / l) }
    fun approx(o: Vec3, eps: Float = 1e-4f) = abs(x - o.x) < eps && abs(y - o.y) < eps && abs(z - o.z) < eps
}

/** Unit quaternion (w + xi + yj + zk) describing a rotation. Hamilton convention. */
data class Quaternion(val w: Float, val x: Float, val y: Float, val z: Float) {

    operator fun times(o: Quaternion) = Quaternion(
        w * o.w - x * o.x - y * o.y - z * o.z,
        w * o.x + x * o.w + y * o.z - z * o.y,
        w * o.y - x * o.z + y * o.w + z * o.x,
        w * o.z + x * o.y - y * o.x + z * o.w,
    )

    fun conjugate() = Quaternion(w, -x, -y, -z)

    fun normalized(): Quaternion {
        val n = sqrt(w * w + x * x + y * y + z * z)
        return if (n == 0f) IDENTITY else Quaternion(w / n, x / n, y / n, z / n)
    }

    fun rotate(v: Vec3): Vec3 {
        val r = this * Quaternion(0f, v.x, v.y, v.z) * conjugate()
        return Vec3(r.x, r.y, r.z)
    }

    /** Column-major 4x4 rotation matrix (OpenGL layout). */
    fun toMatrix(out: FloatArray = FloatArray(16)): FloatArray {
        val q = normalized()
        val xx = q.x * q.x; val yy = q.y * q.y; val zz = q.z * q.z
        val xy = q.x * q.y; val xz = q.x * q.z; val yz = q.y * q.z
        val wx = q.w * q.x; val wy = q.w * q.y; val wz = q.w * q.z
        out[0] = 1 - 2 * (yy + zz); out[1] = 2 * (xy + wz); out[2] = 2 * (xz - wy); out[3] = 0f
        out[4] = 2 * (xy - wz); out[5] = 1 - 2 * (xx + zz); out[6] = 2 * (yz + wx); out[7] = 0f
        out[8] = 2 * (xz + wy); out[9] = 2 * (yz - wx); out[10] = 1 - 2 * (xx + yy); out[11] = 0f
        out[12] = 0f; out[13] = 0f; out[14] = 0f; out[15] = 1f
        return out
    }

    companion object {
        val IDENTITY = Quaternion(1f, 0f, 0f, 0f)

        fun fromAxisAngle(axis: Vec3, radians: Float): Quaternion {
            val a = axis.normalized()
            val s = sin(radians / 2)
            return Quaternion(cos(radians / 2), a.x * s, a.y * s, a.z * s)
        }

        /** Builds a rotation whose columns are the given orthonormal basis vectors. */
        fun fromBasis(xAxis: Vec3, yAxis: Vec3, zAxis: Vec3): Quaternion {
            val m00 = xAxis.x; val m10 = xAxis.y; val m20 = xAxis.z
            val m01 = yAxis.x; val m11 = yAxis.y; val m21 = yAxis.z
            val m02 = zAxis.x; val m12 = zAxis.y; val m22 = zAxis.z
            val trace = m00 + m11 + m22
            return when {
                trace > 0 -> {
                    val s = sqrt(trace + 1f) * 2
                    Quaternion(0.25f * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
                }
                m00 > m11 && m00 > m22 -> {
                    val s = sqrt(1f + m00 - m11 - m22) * 2
                    Quaternion((m21 - m12) / s, 0.25f * s, (m01 + m10) / s, (m02 + m20) / s)
                }
                m11 > m22 -> {
                    val s = sqrt(1f + m11 - m00 - m22) * 2
                    Quaternion((m02 - m20) / s, (m01 + m10) / s, 0.25f * s, (m12 + m21) / s)
                }
                else -> {
                    val s = sqrt(1f + m22 - m00 - m11) * 2
                    Quaternion((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25f * s)
                }
            }.normalized()
        }

        /** Yaw (radians, about +Y) of a forward (-Z) direction. 0 = looking along -Z. */
        fun yawOf(forward: Vec3): Float = atan2(-forward.x, -forward.z)
    }
}
