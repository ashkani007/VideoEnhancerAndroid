package com.lensprompt.core

import java.text.Normalizer
import java.util.Locale

/**
 * A normalized word plus the character span it came from in the original text.
 * Several tokens may share a span (e.g. "25" expands to "twenty" "five").
 */
data class Token(val text: String, val start: Int, val end: Int)

/**
 * Turns displayed script text and recognizer output into comparable tokens.
 *
 * Normalization is deliberately language-light so it does not break non-English
 * text:
 *  - Unicode compatibility decomposition, then removal of non-spacing marks
 *    (accents, Arabic harakat, madda/hamza marks).
 *  - Lowercasing with [Locale.ROOT].
 *  - Persian/Arabic letter unification (ي→ی, ك→ک, ة→ه), tatweel removal.
 *  - Zero-width (non-)joiners and apostrophes are removed *inside* words, so
 *    "می‌خواهم" == "میخواهم" and "don't" == "dont".
 *  - Persian and Arabic-Indic digits become ASCII; whole numbers are spelled
 *    out for the selected language where supported ("25" → "twenty five").
 *  - Any other character that is not a letter/digit separates words.
 */
class TextNormalizer(private val languageTag: String = "en") {

    private val lang = languageTag.substringBefore('-').substringBefore('_').lowercase(Locale.ROOT)

    fun tokenize(text: String): List<Token> {
        val out = ArrayList<Token>(text.length / 5 + 4)
        var i = 0
        val n = text.length
        while (i < n) {
            // skip separators
            while (i < n && !isWordChar(text, i)) i++
            if (i >= n) break
            val start = i
            while (i < n && (isWordChar(text, i) || isInnerJoiner(text, i))) i++
            var end = i
            // trailing joiners/apostrophes are not part of the word
            while (end > start && isInnerJoiner(text, end - 1)) end--
            val normalized = normalizeWord(text.substring(start, end))
            if (normalized.isEmpty()) continue
            expandNumbers(normalized, start, end, out)
        }
        return out
    }

    /** Normalizes a single word. Public for tests and for the similarity helper. */
    fun normalizeWord(raw: String): String {
        val decomposed = Normalizer.normalize(raw, Normalizer.Form.NFKD)
        val sb = StringBuilder(decomposed.length)
        var k = 0
        while (k < decomposed.length) {
            val cp = decomposed.codePointAt(k)
            k += Character.charCount(cp)
            val type = Character.getType(cp)
            if (type == Character.NON_SPACING_MARK.toInt() || type == Character.ENCLOSING_MARK.toInt()) continue
            when (cp) {
                0x200C, 0x200D, 0x200B, 0x2060, 0xFEFF -> continue // zero-width chars
                0x0640 -> continue // tatweel
                '\''.code, 0x2019, 0x2018, 0x02BC, 0x0060, 0x00B4 -> continue // apostrophes
                0x064A, 0x0649 -> { sb.append('ی'); continue } // Arabic yeh / alef maksura → Persian yeh
                0x0643 -> { sb.append('ک'); continue } // Arabic kaf → Persian keheh
                0x0629 -> { sb.append('ه'); continue } // teh marbuta → heh
            }
            val digit = asciiDigit(cp)
            if (digit != null) { sb.append(digit); continue }
            if (Character.isLetterOrDigit(cp)) sb.appendCodePoint(Character.toLowerCase(cp))
        }
        return sb.toString()
    }

    private fun expandNumbers(word: String, start: Int, end: Int, out: MutableList<Token>) {
        if (word.all { it in '0'..'9' } && word.length <= 6) {
            val words = NumberWords.spell(word.toLong(), lang)
            if (words != null) {
                for (w in words) out.add(Token(w, start, end))
                return
            }
        }
        out.add(Token(word, start, end))
    }

    private fun isWordChar(s: String, i: Int): Boolean {
        val c = s[i]
        val cp = when {
            Character.isHighSurrogate(c) -> s.codePointAt(i)
            Character.isLowSurrogate(c) && i > 0 -> s.codePointAt(i - 1)
            else -> c.code
        }
        if (Character.isLetterOrDigit(cp)) return true
        val type = Character.getType(cp)
        return type == Character.NON_SPACING_MARK.toInt() ||
            type == Character.COMBINING_SPACING_MARK.toInt() ||
            type == Character.ENCLOSING_MARK.toInt()
    }

    /** Characters that join word parts when they sit between word characters. */
    private fun isInnerJoiner(s: String, i: Int): Boolean {
        val c = s[i]
        val joiner = c == '‌' || c == '‍' || c == '\'' || c == '’' || c == 'ʼ' || c == 'ـ'
        if (!joiner) return false
        return i + 1 < s.length && isWordChar(s, i + 1)
    }

    private fun asciiDigit(cp: Int): Char? = when (cp) {
        in 0x06F0..0x06F9 -> ('0' + (cp - 0x06F0))
        in 0x0660..0x0669 -> ('0' + (cp - 0x0660))
        else -> null
    }
}

/** Spells whole numbers for supported languages; returns null when unsupported. */
internal object NumberWords {
    private val EN_ONES = arrayOf(
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    )
    private val EN_TENS = arrayOf("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")

    private val NL_ONES = arrayOf(
        "nul", "een", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien",
        "elf", "twaalf", "dertien", "veertien", "vijftien", "zestien", "zeventien", "achttien", "negentien",
    )
    private val NL_TENS = arrayOf("", "", "twintig", "dertig", "veertig", "vijftig", "zestig", "zeventig", "tachtig", "negentig")

    private val FA_ONES = arrayOf(
        "صفر", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده",
        "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده",
    )
    private val FA_TENS = arrayOf("", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود")
    private val FA_HUNDREDS = arrayOf("", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد")

    fun spell(n: Long, lang: String): List<String>? = when (lang) {
        "en" -> if (n < 1_000_000) en(n.toInt()) else null
        "nl" -> if (n < 10_000) nl(n.toInt()) else null
        "fa" -> if (n < 1_000_000) fa(n.toInt()) else null
        else -> null
    }

    private fun en(n: Int): List<String> {
        if (n < 20) return listOf(EN_ONES[n])
        if (n < 100) return listOf(EN_TENS[n / 10]) + if (n % 10 != 0) listOf(EN_ONES[n % 10]) else emptyList()
        if (n < 1000) return listOf(EN_ONES[n / 100], "hundred") + if (n % 100 != 0) en(n % 100) else emptyList()
        return en(n / 1000) + "thousand" + if (n % 1000 != 0) en(n % 1000) else emptyList()
    }

    private fun nl(n: Int): List<String> {
        if (n < 20) return listOf(NL_ONES[n])
        if (n < 100) {
            val o = n % 10
            if (o == 0) return listOf(NL_TENS[n / 10])
            // "tweeëntwintig" normalizes to "tweeentwintig", so plain "en" works for all.
            return listOf(NL_ONES[o] + "en" + NL_TENS[n / 10])
        }
        if (n < 1000) {
            val h = n / 100
            val head = if (h == 1) "honderd" else NL_ONES[h] + "honderd"
            return if (n % 100 == 0) listOf(head) else listOf(head + nl(n % 100).joinToString(""))
        }
        val t = n / 1000
        val head = if (t == 1) "duizend" else nl(t).joinToString("") + "duizend"
        return if (n % 1000 == 0) listOf(head) else listOf(head) + nl(n % 1000)
    }

    private fun fa(n: Int): List<String> {
        if (n < 20) return listOf(FA_ONES[n])
        val parts = ArrayList<String>()
        if (n >= 1000) {
            parts += if (n / 1000 == 1) listOf("هزار") else fa(n / 1000) + "هزار"
            if (n % 1000 == 0) return parts
            parts += "و"
            parts += fa(n % 1000)
            return parts
        }
        if (n >= 100) {
            parts += FA_HUNDREDS[n / 100]
            if (n % 100 == 0) return parts
            parts += "و"
            parts += fa(n % 100)
            return parts
        }
        parts += FA_TENS[n / 10]
        if (n % 10 != 0) { parts += "و"; parts += FA_ONES[n % 10] }
        return parts
    }
}
