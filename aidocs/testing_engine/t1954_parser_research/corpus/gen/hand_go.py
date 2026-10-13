"""hand_go.py - hand-oracle Go fixtures (t1954_1)."""

from core import Fx

W, L, R, C = "\u27e6W\u27e7", "\u27e6L\u27e7", "\u27e6R\u27e7", "\u27e6C\u27e7"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
NATIVE = ["go-scanner", "gofmt"]
BT = "`"

FIXTURES = [
    Fx("ordinary.go", f"""// Package main is an ordinary file.{C}
package main

// testmap:covers internal/demo/demo.go @2026-01-02/0123456789{W}

import (
\t"fmt"
\t"strings"
)

// testmap:unit TestJoin{W}
// testmap:covers internal/demo/join.go{W}
func join() string {{ return strings.Join([]string{{"a", "b"}}, "//") }}

func main() {{
\traw := {BT}
// testmap:covers internal/fake.go{L}
{BT}
\tr := '/'
\tfmt.Println(join(), len(raw), r) // trailing
}}
""", placement={"": 4, "TestJoin": 12}, native=NATIVE + ["go-run"], exec_="go run {file}",
       edits=[
           (f"annotate member= source=internal/demo/demo.go stamp={RE} from=original", "applied",
            ("rep", 4, f"// testmap:covers internal/demo/demo.go {RE}{W}")),
           (f"annotate member=TestJoin source=internal/demo/more.go stamp={NEW} from=original", "applied",
            ("ins", 12, f"// testmap:covers internal/demo/more.go {NEW}{W}")),
           (f"raw kind=replace line=17 member= source=internal/fake.go from=original new=// testmap:covers internal/fake.go {RE}",
            "refused:not-comment"),
           (f"stale member=TestJoin source=internal/demo/join.go stamp={RE} from=original mutate=replace:11:// testmap:unit Renamed",
            "refused:conflict"),
       ]),

    Fx("fresh.go", f"""//go:build linux{C}

// Package a does things.{C}
package a

import "testing"

func TestX(t *testing.T) {{}}
""", placement={"": 4}, native=NATIVE,
       edits=[(f"annotate member= source=src/fresh.go stamp={NEW}", "applied",
               ("ins", 4, f"// testmap:covers src/fresh.go {NEW}{W}"))]),

    Fx("struct_tags.go", f"""package p

type T struct {{
\tA string {BT}json:"a"
// testmap:covers src/tag.go{L}
{BT}
\tB string {BT}json:"b" // not a comment{BT}
}}
// testmap:covers src/real.go{W}
""", native=NATIVE, notes=["a raw-string struct tag spanning lines; `//` inside a one-line tag"]),

    Fx("runes_and_strings.go", f"""package p

var a = '"'
var b = "/* not a comment"
var c = "\\"// testmap:covers src/fake.go"{L}
var d = '\\''
// testmap:covers src/real.go{W}
var e = 1 /* block */ + 2
/* block
// testmap:covers src/in_block.go{L}
*/
// testmap:covers src/real2.go{W}
""", native=NATIVE),

    Fx("cgo_preamble.go", f"""package main

/*
#include <stdio.h>
// testmap:covers src/c_in_preamble.c{L}
*/
import "C"

// testmap:covers src/cgo.go{W}
func main() {{}}
""", native=["go-scanner"],
       notes=["unsupported-construct class: a cgo preamble is C code inside a Go block comment; lexically a comment, never an annotation"]),

    Fx("embedded_sql.go", f"""package p

const q = {BT}
-- testmap:covers src/q.sql{L}
/* testmap:covers src/block.sql */{L}
// testmap:covers src/in_sql.go{L}
{BT}

// testmap:covers src/real.go{W}
""", native=NATIVE),

    Fx("malformed_unterminated_block.go", f"""package p
/* open
// testmap:covers src/x.go{L}
""", uncertain=True, refuse="uncertain", native=["go-scanner"]),

    Fx("malformed_unterminated_string.go", f"""package p
var s = "never closed
// testmap:covers src/x.go{L}
""", uncertain=True, refuse="uncertain", native=["go-scanner"],
       notes=["an interpreted string cannot span lines: the scanner reports it; line 3 is then a real comment, "
              "but the file is malformed and must be refused, not read"]),

    Fx("syntax_error_lexically_valid.go", f"""package p

func {{
// testmap:covers src/x.go{W}
""", native=["go-scanner"],
       notes=["scans cleanly, does not parse: comment context is certain"]),

    Fx("crlf.go", f"""package p

// testmap:covers src/crlf.go{W}
var s = {BT}a
b{BT}
""", crlf=True, native=NATIVE,
       notes=["CRLF: go/scanner strips '\\r' from raw strings and comment text, so byte offsets need care"],
       edits=[(f"annotate member= source=src/crlf.go stamp={RE}", "applied",
               ("rep", 3, f"// testmap:covers src/crlf.go {RE}{W}"))]),

    Fx("bom.go", f"""package p

// testmap:covers src/bom.go{W}
""", bom=True, native=NATIVE, notes=["Go ignores a BOM at the start of a file"],
       edits=[(f"annotate member= source=src/bom2.go stamp={NEW}", "applied",
               ("ins", 3, f"// testmap:covers src/bom2.go {NEW}{W}"))]),
]

# t1954_3: non-ASCII position fixtures (see hand_bash.py).
FIXTURES += [
    Fx("nonascii.go", f"""// é€漢😀 header comment{C}
package main

import "fmt"

// testmap:covers internal/real.go{W}

// 😀 € plain comment{C}
// testmap:unit TestNonAscii{W}
// testmap:covers internal/member.go{W}
func nonASCII() string {{ return "😀 // testmap:covers internal/fake2.go" }}{L}

func main() {{
\ts := "é€😀 // testmap:covers internal/fake.go"{L}
\traw := {BT}漢字😀
// testmap:covers internal/fake3.go{L}
{BT}
\tfmt.Println(len(s), len(raw), nonASCII()) // é trailing
}}
""", placement={"": "internal/real.go", "TestNonAscii": "internal/member.go"}, native=NATIVE + ["go-run"],
       exec_="go run {file}",
       notes=["t1954_3 non-ASCII positions: 2-, 3- and 4-byte characters before every comment, look-alike and edit target"],
       edits=[
           (f"annotate member= source=internal/real.go stamp={RE} from=original", "applied",
            ("rep", "internal/real.go", f"// testmap:covers internal/real.go {RE}{W}")),
           (f"annotate member=TestNonAscii source=internal/more.go stamp={NEW} from=original", "applied",
            ("ins", "internal/member.go", f"// testmap:covers internal/more.go {NEW}{W}")),
           (f"raw kind=replace line=16 member= source=internal/fake3.go from=original new=// testmap:covers internal/fake3.go {RE}",
            "refused:not-comment"),
       ]),
]
