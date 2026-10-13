"""hand_typescript.py - hand-oracle TypeScript / JavaScript fixtures (t1954_1).

No landed rule exists for these languages: the file-level placement is the
research-PROPOSED rule (after the import block and any directive prologue;
see provider/placement.go). The baseline does not support them; candidate
providers (t1954_2/3) are scored against these oracles, cross-checked by the
parser-aware TypeScript oracle (oracle/ts_oracle.js) and `node` execution.
"""

from core import Fx

W, L, R, C = "⟦W⟧", "⟦L⟧", "⟦R⟧", "⟦C⟧"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
BT = "`"
NATIVE_TS = ["node-ts"]

FIXTURES = [
    Fx("ordinary.ts", f"""import {{ strict as assert }} from "node:assert";
import {{ join }} from "node:path";

// testmap:covers src/join.ts{W}

// testmap:unit joinsPaths{W}
// testmap:covers src/path.ts{W}
function joinsPaths(): void {{
  assert.equal(join("a", "b"), "a/b"); // trailing
}}

const url = "http://example.com"; // `//` inside a string
joinsPaths();
console.log("ok", url.length);
""", placement={"": 4, "joinsPaths": 7}, native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       edits=[
           (f"annotate member= source=src/join.ts stamp={RE} from=original", "applied",
            ("rep", 4, f"// testmap:covers src/join.ts {RE}{W}")),
           (f"annotate member=joinsPaths source=src/more.ts stamp={NEW} from=original", "applied",
            ("ins", 7, f"// testmap:covers src/more.ts {NEW}{W}")),
           (f"annotate member=nope source=src/x.ts stamp={NEW} from=original", "refused:no-member-block"),
           (f"stale member=joinsPaths source=src/path.ts stamp={RE} from=original mutate=append:joinsPaths();", "refused:conflict"),
       ]),

    Fx("templates.ts", f"""const x = 1;
const a = {BT}${{x}}
// testmap:covers src/fake1.ts{L}
{BT}; // testmap:covers src/trailing.ts{L}
// testmap:covers src/real1.ts{W}
const b = {BT}outer ${{{BT}inner ${{x}}
// testmap:covers src/fake2.ts{L}
{BT}}} done
// testmap:covers src/fake3.ts{L}
{BT};
// testmap:covers src/real2.ts{W}
const c = {BT}${{ "}}" }}
// testmap:covers src/fake4.ts{L}
${{ {BT}${{ {BT}deep{BT} }}{BT} }}{BT};
// testmap:covers src/real3.ts{W}
console.log(a.length, b.length, c.length);
""", native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       notes=["the reviewer's repro: a template continuation after ${x}, a fake covers line inside, a real comment "
              "after the closing backtick; nested templates; a '}' string inside a substitution"],
       edits=[
           (f"annotate member= source=src/real2.ts stamp={RE}", "applied",
            ("rep", "src/real2.ts", f"// testmap:covers src/real2.ts {RE}{W}")),
           (f"raw kind=replace line=3 member= source=src/fake1.ts new=// testmap:covers src/fake1.ts {RE}", "refused:not-comment"),
       ]),

    Fx("regex.ts", f"""const re = /\\/\\/ testmap:covers src\\/fake/;{L}
const d = 4 / 2 / 1; // division
const r2 = /[/]\\/ testmap/g;{L}
const r3 = /x\\/*/;
// testmap:covers src/after_regex.ts{W}
const r4 = d / 2 /* block */ / 1;
// testmap:covers src/real.ts{W}
console.log(re.test("// testmap:covers src/fake"), r2.source, r3.source, r4);{L}
""", native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       notes=["regex literals containing // and /* (a context-free scanner opens a block comment at r3's '/*')"]),

    Fx("jsx_text.tsx", f"""export function C() {{
  return (
    <div>
      // testmap:covers src/jsx_text.tsx{L}
      /* not a comment either */
      {{/* a real JSX comment */}}
    </div>
  );
}}
// testmap:covers src/real.tsx{W}
""", native=NATIVE_TS, notes=["JSX text that looks like a line comment; .tsx is not executed (no React runtime)"]),

    Fx("jsx_text.jsx", f"""export const D = () => (
  <p>
    // testmap:covers src/jsx_text.jsx{L}
    text
  </p>
);
// testmap:covers src/real.jsx{W}
""", native=NATIVE_TS),

    Fx("prologue.js", """#!/usr/bin/env node
"use strict";
const fs = require("node:fs");
console.log(typeof fs.readFileSync);
""", placement={"": 2}, native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       notes=["proposed placement: after the shebang and the directive prologue"],
       edits=[(f"annotate member= source=src/prologue.js stamp={NEW}", "applied",
               ("ins", 2, f"// testmap:covers src/prologue.js {NEW}{W}"))]),

    Fx("imports.ts", f"""// Copyright header.{C}
import {{ a }} from "./a";
import type {{
  B,
}} from "./b";

export const x = a;
""", placement={"": 5}, native=NATIVE_TS,
       notes=["proposed placement: after the import block (the multi-line import closes on line 5)"],
       edits=[(f"annotate member= source=src/imports.ts stamp={NEW}", "applied",
               ("ins", 5, f"// testmap:covers src/imports.ts {NEW}{W}"))]),

    Fx("html_comments.js", f"""var x = 1;
<!-- testmap:covers src/html.js{L}
--> testmap:covers src/html2.js{L}
// testmap:covers src/real.js{W}
console.log(x);
""", native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       notes=["Annex B HTML-like comments (legal in sloppy scripts): real comments without the // leader, never annotations",
              "the TypeScript parser does not implement Annex B and rejects the file; V8 (node) accepts and runs it"],
       extra={"x-native-differs": "validity"}),

    Fx("embedded.ts", f"""const css = {BT}
  /* testmap:covers src/in_css.ts */{L}
  a {{ background: url(//example.com/x.png); }}
// testmap:covers src/in_css2.ts{L}
{BT};
const html = {BT}<!-- testmap:covers src/in_html.ts -->{L}
// testmap:covers src/in_html2.ts{L}
{BT};
const gql = {BT}
  # testmap:covers src/in_gql.ts{L}
  query {{ x }}
{BT};
// testmap:covers src/real.ts{W}
console.log(css.length + html.length + gql.length);
""", native=NATIVE_TS + ["node-exec"], exec_="node {file}"),

    Fx("malformed_unterminated_template.ts", f"""const s = {BT}abc
// testmap:covers src/x.ts{L}
""", uncertain=True, refuse="uncertain", native=NATIVE_TS),

    Fx("malformed_unterminated_comment.js", f"""var x = 1; /* open
// testmap:covers src/x.js{L}
""", uncertain=True, refuse="uncertain", native=NATIVE_TS),

    Fx("crlf.ts", f"""import {{ a }} from "./a";
// testmap:covers src/crlf.ts{W}
export const y = a;
""", crlf=True, native=NATIVE_TS,
       edits=[(f"annotate member= source=src/crlf.ts stamp={RE}", "applied",
               ("rep", 2, f"// testmap:covers src/crlf.ts {RE}{W}"))]),
]

# t1954_3: non-ASCII position fixtures (see hand_bash.py) for .ts, .tsx and
# .js — JavaScript engines and the TypeScript compiler report UTF-16 units.
FIXTURES += [
    Fx("nonascii.ts", f"""// é€漢😀 header comment{C}
import {{ strict as assert }} from "node:assert";

// testmap:covers src/real.ts{W}

// 😀 € plain comment{C}
// testmap:unit nonAscii{W}
// testmap:covers src/member.ts{W}
function nonAscii(): number {{ return "😀".length; }}

const s = "é€😀 // testmap:covers src/fake.ts";{L}
const t = {BT}漢字😀
// testmap:covers src/fake2.ts{L}
${{s.length}}{BT};
assert.ok(nonAscii() + t.length > 0);
""", placement={"": "src/real.ts", "nonAscii": "src/member.ts"}, native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       notes=["t1954_3 non-ASCII positions: 2-, 3- and 4-byte characters before every comment, look-alike and edit target"],
       edits=[
           (f"annotate member= source=src/real.ts stamp={RE} from=original", "applied",
            ("rep", "src/real.ts", f"// testmap:covers src/real.ts {RE}{W}")),
           (f"annotate member=nonAscii source=src/more.ts stamp={NEW} from=original", "applied",
            ("ins", "src/member.ts", f"// testmap:covers src/more.ts {NEW}{W}")),
           (f"raw kind=replace line=13 member= source=src/fake2.ts from=original new=// testmap:covers src/fake2.ts {RE}",
            "refused:not-comment"),
       ]),

    Fx("nonascii.tsx", f"""// é€漢😀 header comment{C}
import {{ useState }} from "react";

// testmap:covers src/real.tsx{W}
export function C() {{
  const [s] = useState("é€😀 // testmap:covers src/fake.tsx");{L}
  return <p title={{s}}>漢字😀 // testmap:covers src/fake2.tsx</p>;{L}
}}
""", placement={"": "src/real.tsx"}, native=NATIVE_TS,
       notes=["t1954_3 non-ASCII positions in TSX; not executed (no React runtime)"],
       edits=[
           (f"annotate member= source=src/real.tsx stamp={RE} from=original", "applied",
            ("rep", "src/real.tsx", f"// testmap:covers src/real.tsx {RE}{W}")),
           (f"annotate member= source=src/new.tsx stamp={NEW} from=original", "applied",
            ("ins", "src/real.tsx", f"// testmap:covers src/new.tsx {NEW}{W}")),
       ]),

    Fx("nonascii.js", f"""// é€漢😀 header comment{C}
"use strict";
const s = "é€😀 // testmap:covers src/fake.js";{L}
// testmap:covers src/real.js{W}
console.log(s.length, {BT}漢字😀{BT}.length);
""", placement={"": "src/real.js"}, native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       notes=["t1954_3 non-ASCII positions in JavaScript"],
       edits=[
           (f"annotate member= source=src/real.js stamp={RE} from=original", "applied",
            ("rep", "src/real.js", f"// testmap:covers src/real.js {RE}{W}")),
           (f"annotate member= source=src/new.js stamp={NEW} from=original", "applied",
            ("ins", "src/real.js", f"// testmap:covers src/new.js {NEW}{W}")),
       ]),
]

# t1954_3: independent, hand-written expectations for the proposed file-level
# placement rule (after the imports and any directive prologue), so a provider
# that derives the anchors from the same TypeScript AST as the ts-parser
# oracle (tsnative) is checked against something it did not produce.
FIXTURES += [
    Fx("fresh_noimports.ts", f"""// A header comment.{C}
export const x = 1;
console.log(x);
""", placement={"": 1}, native=NATIVE_TS + ["node-exec"], exec_="node {file}",
       notes=["t1954_3 anchors: no imports, no prologue: after the leading comment block"],
       edits=[(f"annotate member= source=src/fresh_noimports.ts stamp={NEW}", "applied",
               ("ins", 1, f"// testmap:covers src/fresh_noimports.ts {NEW}{W}"))]),

    Fx("fresh_imports_only.ts", """import { a } from "./a";
import { b } from "./b";
""", placement={"": 2}, native=NATIVE_TS,
       notes=["t1954_3 anchors: a file of imports only: after the last import"],
       edits=[(f"annotate member= source=src/fresh_imports_only.ts stamp={NEW}", "applied",
               ("ins", 2, f"// testmap:covers src/fresh_imports_only.ts {NEW}{W}"))]),

    Fx("fresh_strict_imports.js", """"use strict";
import fs from "node:fs";
export const exists = fs.existsSync(".");
""", placement={"": 2}, native=NATIVE_TS,
       notes=["t1954_3 anchors: a directive prologue followed by an import: after the import"],
       edits=[(f"annotate member= source=src/fresh_strict_imports.js stamp={NEW}", "applied",
               ("ins", 2, f"// testmap:covers src/fresh_strict_imports.js {NEW}{W}"))]),

    Fx("fresh_comment_between.tsx", f"""import {{ a }} from "./a";
import type {{ B }} from "./b";
// A comment between the imports and the code.{C}
export const C = (b: B) => <div>{{a}}{{String(b)}}</div>;
""", placement={"": 2}, native=NATIVE_TS,
       notes=["t1954_3 anchors: a comment between the imports and the code: the rule places the block right after the imports"],
       edits=[(f"annotate member= source=src/fresh_comment_between.tsx stamp={NEW}", "applied",
               ("ins", 2, f"// testmap:covers src/fresh_comment_between.tsx {NEW}{W}"))]),
]
