"""hand_kotlin.py - hand-oracle Kotlin fixtures (t1954_1)."""

from core import Fx

W, L, R, C = "⟦W⟧", "⟦L⟧", "⟦R⟧", "⟦C⟧"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
NATIVE = ["kotlinc"]
Q3 = '"""'

FIXTURES = [
    Fx("ordinary.kt", f"""@file:JvmName("Ordinary")

package app.tests

import kotlin.math.abs
import kotlin.math.max

// testmap:kind unit{W}
// testmap:covers app/src/Main.kt{W}
class OrdinaryTest {{
    // testmap:unit Adds{W}
    // testmap:covers app/src/Adder.kt{W}
    fun adds() = abs(-1) + max(1, 2)

    val s = "// testmap:covers app/fake.kt"{L}
    val c = '"'
}}
""", placement={"": 9, "Adds": 12}, native=NATIVE,
       edits=[
           (f"annotate member= source=app/src/Main.kt stamp={RE} from=original", "applied",
            ("rep", 9, f"// testmap:covers app/src/Main.kt {RE}{W}")),
           (f"annotate member=Adds source=app/src/More.kt stamp={NEW} from=original", "applied",
            ("ins", 12, f"    // testmap:covers app/src/More.kt {NEW}{W}")),
           (f"raw kind=replace line=15 member=Adds source=app/fake.kt from=original new=    // testmap:covers app/fake.kt {RE}",
            "refused:not-comment"),
       ]),

    Fx("raw_templates.kt", f"""fun main() {{
    val x = 1
    val s = {Q3}
// testmap:covers app/raw.kt{L}
${{"\\"\\"\\""}}
// testmap:covers app/after_template.kt{L}
${{ if (x > 0) "}}" else "{{" }}
{Q3}
    // testmap:covers app/real.kt{W}
    println(s.length)
}}
""", native=NATIVE + ["kotlin-run"],
       notes=["a raw string with ${{…}} templates whose nested strings contain quotes and braces"]),

    Fx("nested_comments.kt", f"""/**
 * KDoc.
 * // testmap:covers app/kdoc.kt{L}
 */
class K
/* outer /* inner
// testmap:covers app/nested.kt{L}
*/ still in the outer comment
// testmap:covers app/still_outer.kt{L}
*/
// testmap:covers app/real.kt{W}
""", native=NATIVE, notes=["Kotlin block comments nest"]),

    Fx("backtick_names.kt", f"""class B {{
    fun `name with "quotes" and # hashes`() = '"'
// testmap:covers app/real.kt{W}
    fun `another * name with ' apostrophe`() = 1
// testmap:covers app/real2.kt{W}
}}
""", native=NATIVE, notes=["backticked identifiers may contain quotes, apostrophes, # and * (Kotlin/JVM forbids / . ; [ ] < > : \\ in them)"]),

    Fx("char_and_templates.kt", f"""val a = '\\''
val b = "${{"}}"}}// testmap:covers app/trailing.kt"{L}
val c = "\\${{not a template}} // still a string"
// testmap:covers app/real.kt{W}
""", native=NATIVE),

    Fx("script.kts", f"""#!/usr/bin/env kotlin
// testmap:covers app/script.kts{W}
println("hi")
""", native=NATIVE, notes=["a .kts script with a shebang line (legal only at the start of a script)"]),

    Fx("embedded_json.kt", f"""val json = {Q3}
{{
  "comment": "// testmap:covers app/in_json.kt",{L}
  "x": 1
}}
// testmap:covers app/in_raw.kt{L}
{Q3}.trimIndent()
// testmap:covers app/real.kt{W}
""", native=NATIVE),

    Fx("malformed_unterminated_block.kt", f"""class M
/* open /* nested */
// testmap:covers app/x.kt{L}
""", uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("malformed_unterminated_string.kt", f"""val s = "never closed
// testmap:covers app/x.kt{L}
""", uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("fresh_imports.kt", """package app

import a.B
import c.D

class T
""", placement={"": 4}, native=NATIVE,
       edits=[(f"annotate member= source=app/fresh.kt stamp={NEW}", "applied",
               ("ins", 4, f"// testmap:covers app/fresh.kt {NEW}{W}"))]),

    Fx("crlf.kt", f"""package app

// testmap:covers app/crlf.kt{W}
class T
""", crlf=True, native=NATIVE,
       edits=[(f"annotate member= source=app/crlf2.kt stamp={NEW}", "applied",
               ("ins", 3, f"// testmap:covers app/crlf2.kt {NEW}{W}"))]),
]

# t1954_3: non-ASCII position fixtures (see hand_bash.py). The JVM reports
# UTF-16 code units; 😀 is a surrogate pair.
FIXTURES += [
    Fx("nonascii.kt", f"""// é€漢😀 header comment{C}
package app.tests

import kotlin.math.abs

// testmap:covers app/src/Real.kt{W}
val s = "é€😀 // testmap:covers app/fake.kt"{L}
val raw = {Q3}漢字😀
// testmap:covers app/fake2.kt{L}
{Q3}

// 😀 € plain comment{C}
class NonAsciiTest {{
    // testmap:unit NonAscii{W}
    // testmap:covers app/src/Member.kt{W}
    fun nonAscii() = abs(-1) + "😀".length
}}
""", placement={"": "app/src/Real.kt", "NonAscii": "app/src/Member.kt"}, native=NATIVE,
       notes=["t1954_3 non-ASCII positions: 2-, 3- and 4-byte characters before every comment, look-alike and edit target"],
       edits=[
           (f"annotate member= source=app/src/Real.kt stamp={RE} from=original", "applied",
            ("rep", "app/src/Real.kt", f"// testmap:covers app/src/Real.kt {RE}{W}")),
           (f"annotate member=NonAscii source=app/src/More.kt stamp={NEW} from=original", "applied",
            ("ins", "app/src/Member.kt", f"    // testmap:covers app/src/More.kt {NEW}{W}")),
           (f"raw kind=replace line=9 member= source=app/fake2.kt from=original new=// testmap:covers app/fake2.kt {RE}",
            "refused:not-comment"),
       ]),
]

# t1954_4: Kotlin 2.2 multi-dollar interpolation strings ($$"…", $$"""…""").
# With N dollars in the prefix only $…${ with N dollars interpolates; a lone
# ${ is literal text. A reader that takes that ${ for a template mis-places
# every later string and comment boundary (the deps lexer defect fixed by
# t1980, the Gradle blanker in t1975). kotlinc 2.4.21 compiles all four.
FIXTURES += [
    Fx("multidollar_comment_desync.kt", f"""package app

// testmap:covers app/real.kt{W}
fun f() {{
    val s = $${Q3}${{/*{Q3}
    // */
}}
val t = {Q3}
// testmap:covers app/fake.kt{L}
{Q3}
val u = {Q3}x{Q3}
// {Q3}
""", native=NATIVE,
       notes=["t1954_4: a literal ${ then /* inside a multi-dollar raw string; a reader that opens a template there sees a block comment, leaves it at the `// */` line comment, and ends up outside the string that line 9 is really inside"],
       edits=[
           (f"raw kind=replace line=9 member= source=app/fake.kt from=original new=// testmap:covers app/fake.kt {RE}",
            "refused:not-comment"),
       ]),

    Fx("multidollar_literal_brace.kt", f"""package app

val s = $${Q3}${{
// testmap:covers app/fake.kt{L}
}}{Q3}

// testmap:covers app/real.kt{W}
fun f() = 1
""", native=NATIVE,
       notes=["t1954_4: a literal ${ … } spanning lines inside a multi-dollar raw string"]),

    Fx("multidollar_quote_boundary.kt", f"""package app

val a = $${Q3}${{{Q3}
val b = {Q3}
// testmap:covers app/fake.kt{L}
{Q3}
val c = {Q3}
}}{Q3}
// testmap:covers app/real.kt{W}
fun k() = 3
""", native=NATIVE,
       notes=["t1954_4: the closing quotes right after a literal ${ end the multi-dollar string"]),

    Fx("multidollar_interpolation.kt", f"""package app

val x = 1
val s = $${Q3}$${{x}} ${{not a template}} // testmap:covers app/fake.kt{Q3}{L}
val r = $$"${{"
// testmap:covers app/real.kt{W}
fun h() = "}}"
""", native=NATIVE,
       notes=["t1954_4: $${…} interpolates in a $$ string, ${…} does not; a single-quoted $$\"${\" string closes on the same line"]),
]
