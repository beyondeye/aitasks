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
