"""hand_java.py - hand-oracle Java fixtures (t1954_1).

Proposed file-level placement: after the imports, else after the package
clause (provider/placement.go). Cross-checked by `javac` and run with the
single-file source launcher (`java File.java`).
"""

from core import Fx

W, L, R, C = "\u27e6W\u27e7", "\u27e6L\u27e7", "\u27e6R\u27e7", "\u27e6C\u27e7"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
Q3 = '"""'
NATIVE = ["javac"]

FIXTURES = [
    Fx("Ordinary.java", f"""package app;

import java.util.List;

// testmap:covers src/main/java/app/Lists.java{W}
public class Ordinary {{
    // testmap:unit sizes{W}
    // testmap:covers src/main/java/app/Size.java{W}
    static int sizes() {{ return List.of(1, 2).size(); }}

    public static void main(String[] a) {{
        String s = "// testmap:covers fake";{L}
        char c = '"';
        System.out.println(sizes() + s.length() + c);
    }}
}}
""", placement={"": 5, "sizes": 8}, native=NATIVE + ["java-exec"], exec_="java {file}",
       edits=[
           (f"annotate member= source=src/main/java/app/Lists.java stamp={RE} from=original", "applied",
            ("rep", 5, f"// testmap:covers src/main/java/app/Lists.java {RE}{W}")),
           (f"annotate member=sizes source=src/main/java/app/More.java stamp={NEW} from=original", "applied",
            ("ins", 8, f"    // testmap:covers src/main/java/app/More.java {NEW}{W}")),
           (f"raw kind=replace line=12 member=sizes source=fake from=original new=        // testmap:covers fake", "refused:not-comment"),
       ]),

    Fx("TextBlocks.java", f"""class TextBlocks {{
    static String t = {Q3}
        // testmap:covers src/fake.java{L}
        \\{Q3}
        // testmap:covers src/fake2.java{L}
        {Q3};
// testmap:covers src/real.java{W}
    public static void main(String[] a) {{ System.out.println(t.length()); }}
}}
""", native=NATIVE + ["java-exec"], exec_="java {file}",
       notes=["a text block with an escaped \\\"\"\" that does not close it"]),

    Fx("UnicodeEscape.java", f"""class UnicodeEscape {{
    // a comment that ends early \\u000a static int x = 1;
    static String s = \\u0022\\u0022\\u0022
// testmap:covers src/in_textblock.java{L}
\\u0022\\u0022\\u0022;
// testmap:covers src/real.java{W}
    \\u002f\\u002f testmap:covers src/escaped_leader.java{L}
    public static void main(String[] a) {{ System.out.println(x + s.length()); }}
}}
""", native=NATIVE + ["java-exec"], exec_="java {file}",
       notes=["unsupported-construct class: Java translates \\uXXXX escapes BEFORE lexing. Line 3 opens a text block "
              "with escaped quotes, so line 4 is string data (a lexer that ignores escapes calls it a comment: FP-writable); "
              "line 2's escaped newline turns `static int x = 1;` into code; line 7 is a real comment with an escaped "
              "leader, never an annotation (the leader must be literal bytes)"]),

    Fx("Nested.java", f"""class Nested {{
/* outer /* Java block comments do not nest
// testmap:covers src/in_block.java{L}
*/
// testmap:covers src/real.java{W}
    /** Javadoc
     * // testmap:covers src/javadoc.java{L}
     */
    void m() {{}}
}}
""", native=NATIVE),

    Fx("CharsAndStrings.java", f"""class CharsAndStrings {{
    char a = '\\'';
    char b = '"';
    String c = "/* not a comment";
    String d = "\\"// testmap:covers src/fake.java";{L}
// testmap:covers src/real.java{W}
}}
""", native=NATIVE),

    Fx("EmbeddedSql.java", f"""class EmbeddedSql {{
    static final String Q = {Q3}
        -- testmap:covers src/q.sql{L}
        // testmap:covers src/in_sql.java{L}
        SELECT 1;
        {Q3};
// testmap:covers src/real.java{W}
}}
""", native=NATIVE),

    Fx("Fresh.java", """package app.tests;

import java.util.List;
import static java.util.Map.of;

class Fresh {}
""", placement={"": 4}, native=NATIVE,
       notes=["proposed placement: after the imports"],
       edits=[(f"annotate member= source=src/fresh.java stamp={NEW}", "applied",
               ("ins", 4, f"// testmap:covers src/fresh.java {NEW}{W}"))]),

    Fx("MalformedTextBlock.java", f"""class MalformedTextBlock {{
    String s = {Q3}
// testmap:covers src/x.java{L}
""", uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("MalformedComment.java", f"""class MalformedComment {{
/* open
// testmap:covers src/x.java{L}
""", uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("Crlf.java", f"""package app;

// testmap:covers src/crlf.java{W}
class Crlf {{}}
""", crlf=True, native=NATIVE,
       edits=[(f"annotate member= source=src/crlf2.java stamp={NEW}", "applied",
               ("ins", 3, f"// testmap:covers src/crlf2.java {NEW}{W}"))]),
]
