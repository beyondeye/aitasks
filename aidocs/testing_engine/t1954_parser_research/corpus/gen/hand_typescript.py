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
