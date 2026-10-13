"""hand_rust.py - hand-oracle Rust fixtures (t1954_1).

Proposed file-level placement: after inner attributes / `//!` docs and the
`use` block. Cross-checked by `rustc --edition 2021` and executed.
"""

from core import Fx

W, L, R, C = "⟦W⟧", "⟦L⟧", "⟦R⟧", "⟦C⟧"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
NATIVE = ["rustc"]
EXEC = "rustc --edition 2021 -o prog {file} 2>/dev/null && ./prog"

FIXTURES = [
    Fx("ordinary.rs", f"""//! Crate docs.{C}
#![allow(dead_code)]

use std::collections::HashMap;
use std::fmt;

// testmap:covers src/lib.rs{W}

// testmap:unit builds_map{W}
// testmap:covers src/map.rs{W}
fn builds_map() -> HashMap<&'static str, i32> {{
    let mut m = HashMap::new();
    m.insert("// not a comment", 1);
    m
}}

fn main() {{
    let s = r#"
// testmap:covers src/fake.rs{L}
"#;
    println!("{{}} {{}} {{:?}}", s.len(), builds_map().len(), fmt::Error);
}}
""", placement={"": 7, "builds_map": 10}, native=NATIVE + ["rust-exec"], exec_=EXEC,
       edits=[
           (f"annotate member= source=src/lib.rs stamp={RE} from=original", "applied",
            ("rep", 7, f"// testmap:covers src/lib.rs {RE}{W}")),
           (f"annotate member=builds_map source=src/more.rs stamp={NEW} from=original", "applied",
            ("ins", 10, f"// testmap:covers src/more.rs {NEW}{W}")),
           (f"raw kind=replace line=19 member= source=src/fake.rs from=original new=// testmap:covers src/fake.rs {RE}", "refused:not-comment"),
       ]),

    Fx("raw_strings.rs", f"""fn take<'a>(s: &'a str) -> &'a str {{ s }}
fn main() {{
    let a = r##"
// testmap:covers src/fake1.rs{L}
"# still inside
// testmap:covers src/fake2.rs{L}
"##;
    let q = '"';
    let b = br#"
// testmap:covers src/fake3.rs{L}
"#;
    let r#type = "raw identifier, not a raw string";
// testmap:covers src/real.rs{W}
    println!("{{}}{{}}{{}}{{}}", take(a).len(), q, b.len(), r#type.len());
}}
""", native=NATIVE + ["rust-exec"], exec_=EXEC,
       notes=["r##\"…\"## containing \"#, byte raw strings, lifetimes 'a (not char literals), a raw identifier r#type"]),

    Fx("nested_comments.rs", f"""/* outer /* inner */
// testmap:covers src/still_comment.rs{L}
*/
/// Doc comment on main.{C}
fn main() {{}}
// testmap:covers src/real.rs{W}
""", native=NATIVE + ["rust-exec"], exec_=EXEC, notes=["Rust block comments nest; `///` is a line comment (doc)"]),

    Fx("inner_attrs.rs", f"""//! Inner doc.{C}
#![allow(unused)]
#![cfg_attr(test, allow(dead_code))]

use std::io;
use std::fmt::{{
    Debug,
    Display,
}};

fn main() {{ let _ = io::stdout(); }}
""", placement={"": 9}, native=NATIVE + ["rust-exec"], exec_=EXEC,
       notes=["proposed placement: after the inner attributes and the use block (closing on line 9)"],
       edits=[(f"annotate member= source=src/inner.rs stamp={NEW}", "applied",
               ("ins", 9, f"// testmap:covers src/inner.rs {NEW}{W}"))]),

    Fx("chars_and_macros.rs", f"""macro_rules! m {{
    () => {{ "// testmap:covers src/in_macro.rs" }};{L}
}}
fn main() {{
    let c = '\\'';
    let d = '/';
    let e = b'"';
// testmap:covers src/real.rs{W}
    println!("{{}}{{}}{{}}{{}}", m!(), c, d, e);
}}
""", native=NATIVE + ["rust-exec"], exec_=EXEC),

    Fx("embedded_sql.rs", f"""const Q: &str = r#"
-- testmap:covers src/q.sql{L}
// testmap:covers src/in_sql.rs{L}
"#;
// testmap:covers src/real.rs{W}
fn main() {{ print!("{{}}", Q.len()); }}
""", native=NATIVE + ["rust-exec"], exec_=EXEC),

    Fx("malformed_raw.rs", f"""fn main() {{
    let s = r#"never closed
// testmap:covers src/x.rs{L}
""", uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("malformed_nested.rs", f"""/* outer /* inner */
// testmap:covers src/x.rs{L}
fn main() {{}}
""", uncertain=True, refuse="uncertain", native=NATIVE,
       notes=["only the inner comment is closed: everything after is still the outer comment"]),

    Fx("crlf.rs", f"""// testmap:covers src/crlf.rs{W}
fn main() {{}}
""", crlf=True, native=NATIVE,
       edits=[(f"annotate member= source=src/crlf.rs stamp={RE}", "applied",
               ("rep", 1, f"// testmap:covers src/crlf.rs {RE}{W}"))]),
]
