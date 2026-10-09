package com.vrvision.core.calibration

/**
 * JSON export/import of calibration profiles so users can share or back up headset setups.
 * Self-contained (no JSON library) because :core is a plain JVM module. Handles exactly
 * the flat object this class writes; unknown keys are ignored, missing keys use defaults,
 * and every imported value is clamped through [HeadsetCalibration.validated].
 */
object CalibrationCodec {

    const val FORMAT_VERSION = 1

    fun encode(c: HeadsetCalibration): String = buildString {
        append('{')
        append("\"format\":").append(FORMAT_VERSION)
        append(",\"name\":").append(quote(c.name))
        num("lensSeparationMm", c.lensSeparationMm)
        num("lensToBottomMm", c.lensToBottomMm)
        append(",\"distortionEnabled\":").append(c.distortionEnabled)
        num("k1", c.k1); num("k2", c.k2)
        num("leftCenterOffsetX", c.leftCenterOffsetX); num("leftCenterOffsetY", c.leftCenterOffsetY)
        num("rightCenterOffsetX", c.rightCenterOffsetX); num("rightCenterOffsetY", c.rightCenterOffsetY)
        num("imageOffsetX", c.imageOffsetX); num("imageOffsetY", c.imageOffsetY)
        num("zoom", c.zoom); num("fovDegrees", c.fovDegrees); num("viewportMargin", c.viewportMargin)
        append('}')
    }

    /** @throws IllegalArgumentException for malformed input or an unsupported format version. */
    fun decode(json: String): HeadsetCalibration {
        val map = parseFlatObject(json)
        val format = (map["format"] as? Double)?.toInt() ?: throw IllegalArgumentException("Missing format version")
        require(format == FORMAT_VERSION) { "Unsupported calibration format $format" }
        val d = HeadsetCalibration()
        fun f(key: String, def: Float): Float = (map[key] as? Double)?.toFloat()?.takeIf { it.isFinite() } ?: def
        return HeadsetCalibration(
            name = (map["name"] as? String) ?: d.name,
            lensSeparationMm = f("lensSeparationMm", d.lensSeparationMm),
            lensToBottomMm = f("lensToBottomMm", d.lensToBottomMm),
            distortionEnabled = (map["distortionEnabled"] as? Boolean) ?: d.distortionEnabled,
            k1 = f("k1", d.k1), k2 = f("k2", d.k2),
            leftCenterOffsetX = f("leftCenterOffsetX", 0f), leftCenterOffsetY = f("leftCenterOffsetY", 0f),
            rightCenterOffsetX = f("rightCenterOffsetX", 0f), rightCenterOffsetY = f("rightCenterOffsetY", 0f),
            imageOffsetX = f("imageOffsetX", 0f), imageOffsetY = f("imageOffsetY", 0f),
            zoom = f("zoom", d.zoom), fovDegrees = f("fovDegrees", d.fovDegrees),
            viewportMargin = f("viewportMargin", d.viewportMargin),
        ).validated()
    }

    private fun StringBuilder.num(key: String, value: Float) {
        append(",\"").append(key).append("\":").append(value.toString())
    }

    private fun quote(s: String): String = buildString {
        append('"')
        for (ch in s) when {
            ch == '"' -> append("\\\"")
            ch == '\\' -> append("\\\\")
            ch == '\n' -> append("\\n")
            ch == '\r' -> append("\\r")
            ch == '\t' -> append("\\t")
            ch < ' ' -> append("\\u").append(ch.code.toString(16).padStart(4, '0'))
            else -> append(ch)
        }
        append('"')
    }

    /** Parses `{"k": number|string|true|false|null, ...}`; nested values are rejected. */
    internal fun parseFlatObject(json: String): Map<String, Any?> {
        val p = Parser(json)
        val out = LinkedHashMap<String, Any?>()
        p.ws(); p.expect('{'); p.ws()
        if (p.peek() == '}') { p.pos++; return out }
        while (true) {
            p.ws(); val key = p.string(); p.ws(); p.expect(':'); p.ws()
            out[key] = p.value()
            p.ws()
            when (p.next()) {
                ',' -> continue
                '}' -> break
                else -> throw IllegalArgumentException("Expected , or } at ${p.pos}")
            }
        }
        p.ws()
        require(p.pos == json.length) { "Trailing characters" }
        return out
    }

    private class Parser(val s: String) {
        var pos = 0
        fun peek(): Char = if (pos < s.length) s[pos] else throw IllegalArgumentException("Unexpected end")
        fun next(): Char = peek().also { pos++ }
        fun ws() { while (pos < s.length && s[pos].isWhitespace()) pos++ }
        fun expect(c: Char) { if (next() != c) throw IllegalArgumentException("Expected $c at ${pos - 1}") }

        fun value(): Any? = when (val c = peek()) {
            '"' -> string()
            't' -> literal("true", true)
            'f' -> literal("false", false)
            'n' -> literal("null", null)
            '{', '[' -> throw IllegalArgumentException("Nested values are not supported")
            else -> if (c == '-' || c.isDigit()) number() else throw IllegalArgumentException("Bad value at $pos")
        }

        fun literal(word: String, v: Any?): Any? {
            require(s.startsWith(word, pos)) { "Bad literal at $pos" }
            pos += word.length
            return v
        }

        fun number(): Double {
            val start = pos
            while (pos < s.length && (s[pos].isDigit() || s[pos] in "+-.eE")) pos++
            return s.substring(start, pos).toDoubleOrNull() ?: throw IllegalArgumentException("Bad number at $start")
        }

        fun string(): String {
            expect('"')
            val sb = StringBuilder()
            while (true) {
                val c = next()
                when {
                    c == '"' -> return sb.toString()
                    c == '\\' -> when (val e = next()) {
                        '"' -> sb.append('"'); '\\' -> sb.append('\\'); '/' -> sb.append('/')
                        'n' -> sb.append('\n'); 'r' -> sb.append('\r'); 't' -> sb.append('\t')
                        'b' -> sb.append('\b'); 'f' -> sb.append('\u000C')
                        'u' -> {
                            require(pos + 4 <= s.length) { "Bad escape" }
                            sb.append(s.substring(pos, pos + 4).toInt(16).toChar()); pos += 4
                        }
                        else -> throw IllegalArgumentException("Bad escape \\$e")
                    }
                    else -> sb.append(c)
                }
            }
        }
    }
}
