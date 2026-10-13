"""hand_swift.py - hand-oracle Swift fixtures (t1954_1).

Proposed file-level placement: after the imports. Cross-checked by
`swiftc -parse` when a Swift toolchain is obtainable (docker `swift`
image); otherwise native evidence is `none`.
"""

from core import Fx

W, L, R, C = "⟦W⟧", "⟦L⟧", "⟦R⟧", "⟦C⟧"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
Q3 = '"""'
NATIVE = ["swiftc"]

FIXTURES = [
    Fx("ordinary.swift", f"""import Foundation

// testmap:covers Sources/App/Main.swift{W}

// testmap:unit testAdds{W}
// testmap:covers Sources/App/Adder.swift{W}
func testAdds() -> Bool {{ return 1 + 1 == 2 }}

let url = "https://example.com" // `//` inside a string
print(testAdds(), url.count)
""", placement={"": 3, "testAdds": 6}, native=NATIVE,
       edits=[
           (f"annotate member= source=Sources/App/Main.swift stamp={RE} from=original", "applied",
            ("rep", 3, f"// testmap:covers Sources/App/Main.swift {RE}{W}")),
           (f"annotate member=testAdds source=Sources/App/More.swift stamp={NEW} from=original", "applied",
            ("ins", 6, f"// testmap:covers Sources/App/More.swift {NEW}{W}")),
       ]),

    Fx("raw_strings.swift", f"""let a = #{Q3}
// testmap:covers Sources/fake1.swift{L}
{Q3}
// testmap:covers Sources/fake2.swift{L}
{Q3}#
let b = {Q3}
// testmap:covers Sources/fake3.swift{L}
\\(a.count) \\("nested \\"quote\\"")
{Q3}
let c = ##"one "# two"##
// testmap:covers Sources/real.swift{W}
print(a.count, b.count, c)
""", native=NATIVE,
       notes=["#\"\"\"…\"\"\"# is closed only by \"\"\"#; interpolation with nested quotes; ##\"…\"## containing \"#"]),

    Fx("nested_comments.swift", f"""/* outer /* inner */
// testmap:covers Sources/still_comment.swift{L}
*/
/// Doc comment.{C}
func f() {{}}
// testmap:covers Sources/real.swift{W}
""", native=NATIVE, notes=["Swift block comments nest"]),

    Fx("regex_literals.swift", f"""let r = /\\/\\/ testmap/{L}
let r2 = #/a/b/#
// testmap:covers Sources/real.swift{W}
let x = 4 / 2 / 1
""", native=NATIVE, notes=["Swift 5.7 regex literals (bare /…/ and extended #/…/#) containing //; bare /…/ needs "
                           "Swift 6 mode or -enable-bare-slash-regex (the native check passes the flag)"]),

    Fx("shebang.swift", f"""#!/usr/bin/env swift
// testmap:covers Sources/script.swift{W}
print("hi")
""", native=NATIVE),

    Fx("fresh_imports.swift", """@testable import App
import XCTest

final class T: XCTestCase {}
""", placement={"": 2}, native=NATIVE,
       notes=["proposed placement: after the imports"],
       edits=[(f"annotate member= source=Sources/fresh.swift stamp={NEW}", "applied",
               ("ins", 2, f"// testmap:covers Sources/fresh.swift {NEW}{W}"))]),

    Fx("embedded_json.swift", f"""let json = {Q3}
{{ "c": "// testmap:covers Sources/in_json.swift" }}{L}
// testmap:covers Sources/in_string.swift{L}
{Q3}
// testmap:covers Sources/real.swift{W}
""", native=NATIVE),

    Fx("malformed_multiline.swift", f"""let s = {Q3}
// testmap:covers Sources/x.swift{L}
""", uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("malformed_nested.swift", f"""/* outer /* inner */
// testmap:covers Sources/x.swift{L}
""", uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("crlf.swift", f"""import Foundation
// testmap:covers Sources/crlf.swift{W}
print(1)
""", crlf=True, native=NATIVE,
       edits=[(f"annotate member= source=Sources/crlf.swift stamp={RE}", "applied",
               ("rep", 2, f"// testmap:covers Sources/crlf.swift {RE}{W}"))]),
]

# t1954_3: non-ASCII position fixtures (see hand_bash.py).
FIXTURES += [
    Fx("nonascii.swift", f"""// é€漢😀 header comment{C}
import Foundation

// testmap:covers Sources/App/Real.swift{W}

// 😀 € plain comment{C}
// testmap:unit testNonAscii{W}
// testmap:covers Sources/App/Member.swift{W}
func testNonAscii() -> Int {{ return "😀".count }}

let s = "é€😀 // testmap:covers Sources/fake.swift"{L}
let raw = {Q3}
漢字😀
// testmap:covers Sources/fake2.swift{L}
{Q3}
print(s.count, raw.count, testNonAscii())
""", placement={"": "Real.swift", "testNonAscii": "Member.swift"}, native=NATIVE,
       notes=["t1954_3 non-ASCII positions: 2-, 3- and 4-byte characters before every comment, look-alike and edit target"],
       edits=[
           (f"annotate member= source=Sources/App/Real.swift stamp={RE} from=original", "applied",
            ("rep", "Real.swift", f"// testmap:covers Sources/App/Real.swift {RE}{W}")),
           (f"annotate member=testNonAscii source=Sources/App/More.swift stamp={NEW} from=original", "applied",
            ("ins", "Member.swift", f"// testmap:covers Sources/App/More.swift {NEW}{W}")),
           (f"raw kind=replace line=14 member=testNonAscii source=Sources/fake2.swift from=original new=// testmap:covers Sources/fake2.swift {RE}",
            "refused:not-comment"),
       ]),
]
