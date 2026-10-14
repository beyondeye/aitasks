"""hand_bash.py - hand-oracle bash fixtures (t1954_1).

Classes per fixture: ordinary valid, difficult valid, malformed, embedded
language, unsupported construct; the edit set; encoding/EOL/mode. Lines are
marked per core.py. Every valid fixture is cross-checked by `bash -n`, and
the exec: fixtures run in a scratch copy before and after each applied edit.
"""

from core import Fx

W, L, R, C = "⟦W⟧", "⟦L⟧", "⟦R⟧", "⟦C⟧"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
NATIVE = ["bash-n", "shfmt"]

FIXTURES = [
    Fx("ordinary.sh", f"""#!/usr/bin/env bash
# ordinary.sh - an ordinary test file.{C}
#{C}
# testmap:kind unit{W}
# testmap:covers src/lib/a.sh @2026-01-02/0123456789{W}
set -euo pipefail

# testmap:unit Alpha{W}
# testmap:covers src/lib/alpha.sh{W}
alpha() {{
    local x="a # not a comment"
    echo "$x" # a trailing comment, not a line comment
}}

# plain comment{C}
alpha
""", placement={"": 5, "Alpha": 9}, native=NATIVE + ["bash-exec"], exec_="bash {file}",
       edits=[
           (f"annotate member= source=src/lib/a.sh stamp={RE} from=original", "applied",
            ("rep", 5, f"# testmap:covers src/lib/a.sh {RE}{W}")),
           (f"annotate member= source=src/lib/b.sh stamp={NEW} from=original", "applied",
            ("ins", 5, f"# testmap:covers src/lib/b.sh {NEW}{W}")),
           (f"annotate member=Alpha source=src/lib/c.sh stamp={NEW} from=original", "applied",
            ("ins", 9, f"# testmap:covers src/lib/c.sh {NEW}{W}")),
           ("raw kind=replace line=11 member=Alpha source=src/x.sh from=original new=# testmap:covers src/x.sh",
            "refused:not-comment"),
       ]),

    Fx("heredoc_matrix.sh", f"""#!/usr/bin/env bash
# testmap:covers src/heredoc.sh{W}
set -euo pipefail
out=$(cat <<'EOF'
# testmap:covers src/fake1.sh{L}
EOF
)
echo "$out" | grep -c EOF >/dev/null || true
cat <<-INDENTED
\t# testmap:covers src/fake2.sh{L}
\tINDENTED
printf '%s\\n' EOF <<EOF2 \\
  "EOF"
# testmap:covers src/fake3.sh{L}
EOF2
inner=$(echo "$(cat <<X
# testmap:covers src/fake4.sh{L}
X
)")
echo "$inner"
cat <<"Q"EOF
# testmap:covers src/fake5.sh{L}
QEOF
# testmap:covers src/real2.sh{W}
""", placement={"": "src/real2.sh"}, native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["delimiter-shaped arguments (EOF as a printf argument, grep pattern), a heredoc delayed by a "
              "backslash continuation, <<- with tabs, nested $( … $( … ) … ) with a heredoc, a partly quoted delimiter"],
       edits=[
           (f"annotate member= source=src/new.sh stamp={NEW}", "applied",
            ("ins", "src/real2.sh", f"# testmap:covers src/new.sh {NEW}{W}")),
           (f"raw kind=replace line=14 member= source=src/fake3.sh new=# testmap:covers src/fake3.sh {RE}",
            "refused:not-comment"),
       ]),

    Fx("embedded.sh", f"""#!/usr/bin/env bash
# testmap:covers src/embed.sh{W}
python3 - <<'PY'
# testmap:covers src/py_in_heredoc.py{L}
print("hi")  # a python comment
PY
awk '
# testmap:covers src/awk.awk{L}
{{ print $1 }}
' /dev/null
sql="
-- testmap:covers src/q.sql{L}
# testmap:covers src/in_sql_string.sh{L}
"
echo "${{sql:0:3}}"
# testmap:covers src/embed2.sh{W}
""", native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["embedded languages: a python heredoc, an awk program in single quotes, SQL in a double-quoted string"]),

    Fx("heredoc_in_arith.sh", f"""#!/usr/bin/env bash
x=$(( $(cat <<EOF
1
EOF
) + 1 ))
echo "$x"
# testmap:covers src/arith.sh{W}
""", native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["a heredoc inside a command substitution inside $(( … )): valid bash (exec prints 2)"]),

    Fx("heredoc_in_backtick_subst.sh", f"""#!/usr/bin/env bash
x=`cat <<EOF
# testmap:covers src/in_backtick.sh{L}
EOF
`
echo "$x"
# testmap:covers src/after.sh{W}
""", native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["unsupported-construct class: a heredoc inside backticks that bash accepts (the M2.2 lexer refuses "
              "the one-line `cat <<EOF` form; this multi-line form is valid). A refusal here is over-refusal, never a safety failure."]),

    Fx("case_patterns.sh", f"""#!/usr/bin/env bash
v=a
case "$v" in
  a) echo one ;;   # trailing
  '#'*) echo hash ;;
  *) echo other
# testmap:covers src/in_case.sh{W}
     ;;
esac
""", native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["case patterns with ')' and a quoted '#' pattern; the comment inside the case arm is a real comment"]),

    Fx("malformed_unterminated_subst.sh", f"""#!/usr/bin/env bash
x=$(echo a
# testmap:covers src/x.sh{L}
""", uncertain=True, refuse="uncertain", native=["bash-n"],
       notes=["malformed: $( never closed; bash -n rejects it"]),

    Fx("malformed_unterminated_single.sh", f"""#!/usr/bin/env bash
echo 'never closed
# testmap:covers src/x.sh{L}
""", uncertain=True, refuse="uncertain", native=["bash-n"]),

    Fx("syntax_error_lexically_valid.sh", f"""#!/usr/bin/env bash
if true; then
# testmap:covers src/x.sh{W}
echo missing-fi
""", native=["bash-n"],
       notes=["grammar error (no `fi`) that does not affect comment context: the oracle expects the annotation "
              "read. A parser-based provider that refuses is over-refusal (a cost), not a safety failure."]),

    Fx("edits_members.sh", f"""#!/usr/bin/env bash
# testmap:covers src/shared.sh @2026-01-01/0123456789{W}
set -e
# testmap:unit A{W}
# testmap:covers src/shared.sh @2026-01-01/0123456789{W}
a() {{ :; }}
# testmap:unit B{W}
# testmap:covers src/shared.sh @2026-01-01/0123456789{W}
# testmap:covers src/b.sh{W}
b() {{ :; }}
cat <<EOF
# testmap:covers src/shared.sh @2026-01-01/0123456789{L}
EOF
""", placement={"": 2, "A": 5, "B": 9}, native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["several blocks cover src/shared.sh: re-stamping B's must leave the file-level and A's lines record- and byte-identical"],
       edits=[
           (f"annotate member=B source=src/shared.sh stamp={RE}", "applied",
            ("rep", 8, f"# testmap:covers src/shared.sh {RE}{W}")),
           (f"annotate member=A source=src/new.sh stamp={NEW} from=original", "applied",
            ("ins", 5, f"# testmap:covers src/new.sh {NEW}{W}")),
           (f"annotate member=C source=src/x.sh stamp={NEW} from=original", "refused:no-member-block"),
           (f"raw kind=replace line=12 member= source=src/shared.sh from=original new=# testmap:covers src/shared.sh {RE}",
            "refused:not-comment"),
           (f"stale member=A source=src/shared.sh stamp={RE} from=original mutate=append:echo late", "refused:conflict"),
       ]),

    Fx("edits_uncertain.sh", f"""#!/usr/bin/env bash
# testmap:covers src/u.sh{C}
cat <<EOF
never terminated
""", uncertain=True, refuse="uncertain", native=["bash-n"],
       notes=["a write into an uncertain file is refused (the comment on line 2 is real, but the file's context cannot be established)"],
       edits=[
           (f"annotate member= source=src/u.sh stamp={RE}", "refused:uncertain"),
           (f"raw kind=replace line=2 member= source=src/u.sh new=# testmap:covers src/u.sh {RE}", "refused:uncertain"),
       ]),

    Fx("fresh_noheader.sh", """#!/usr/bin/env bash
set -euo pipefail
echo hi
""", placement={"": 1}, native=NATIVE + ["bash-exec"], exec_="bash {file}",
       edits=[(f"annotate member= source=src/fresh.sh stamp={NEW}", "applied",
               ("ins", 1, f"# testmap:covers src/fresh.sh {NEW}{W}"))]),

    Fx("crlf_edit.sh", f"""#!/bin/sh
# testmap:covers src/crlf.sh @2026-01-02/0123456789{W}
echo crlf
""", crlf=True, native=NATIVE,
       edits=[(f"annotate member= source=src/crlf2.sh stamp={NEW}", "applied",
               ("ins", 2, f"# testmap:covers src/crlf2.sh {NEW}{W}")),
              (f"annotate member= source=src/crlf.sh stamp={RE}", "applied",
               ("rep", 2, f"# testmap:covers src/crlf.sh {RE}{W}"))]),

    Fx("nonl_edit.sh", f"""#!/bin/sh
# header{C}
# testmap:covers src/nonl.sh{W}""", nonl=True, native=NATIVE,
       edits=[(f"annotate member= source=src/nonl2.sh stamp={NEW}", "applied",
               ("ins", 3, f"# testmap:covers src/nonl2.sh {NEW}{W}"))]),

    Fx("bom_edit.sh", f"""# header after a UTF-8 BOM
# testmap:covers src/bom.sh{W}
echo bom
""", bom=True, native=["bash-n"],
       notes=["bash gives a BOM no meaning: line 1 is the word U+FEFF'#' (a command), so it is NOT a comment; "
              "line 2 is. The BOM must survive every edit."],
       edits=[(f"annotate member= source=src/bom2.sh stamp={NEW}", "applied",
               ("ins", 2, f"# testmap:covers src/bom2.sh {NEW}{W}"))]),

    Fx("latin1_edit.sh", f"""#!/bin/sh
# café — latin-1 bytes in a comment{C}
# testmap:covers src/latin1.sh{W}
echo "naïve"
""".replace("—", "-"), encoding="latin-1", native=["bash-n"],
       notes=["Latin-1 (non-UTF-8) bytes in a comment and a string; every other byte must survive"],
       edits=[(f"annotate member= source=src/latin1.sh stamp={RE}", "applied",
               ("rep", 3, f"# testmap:covers src/latin1.sh {RE}{W}"))]),

    Fx("exec_mode_edit.sh", f"""#!/usr/bin/env bash
# testmap:covers src/exec.sh{W}
echo exec
""", mode=0o755, native=NATIVE + ["bash-exec"], exec_="env ./{file}",
       notes=["an executable fixture: the mode must survive the edit, and the file still runs"],
       edits=[(f"annotate member= source=src/exec2.sh stamp={NEW}", "applied",
               ("ins", 2, f"# testmap:covers src/exec2.sh {NEW}{W}"))]),
]

# t1954_3: non-ASCII position fixtures. A 2-byte (é), 3-byte (€, 漢) and
# 4-byte (😀, a UTF-16 surrogate pair) character precede a real comment, a
# look-alike inside a string, and the lines above every edit target, so a
# provider that converts code points or UTF-16 units instead of bytes
# misplaces spans (an adapter failure, listed apart from candidate defects).
FIXTURES += [
    Fx("nonascii.sh", f"""#!/usr/bin/env bash
# é€漢😀 header comment{C}
s="é€😀 # testmap:covers src/fake.sh"{L}
# testmap:covers src/real.sh{W}
t='漢字😀' # é trailing

# 😀 € plain comment{C}
# testmap:unit NonAscii{W}
# testmap:covers src/member.sh{W}
non_ascii() {{
    echo "😀 # testmap:covers src/fake2.sh"{L}
}}
echo "${{#s}} ${{#t}}" "$(non_ascii)"
""", placement={"": "src/real.sh", "NonAscii": "src/member.sh"}, native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["t1954_3 non-ASCII positions: 2-, 3- and 4-byte characters before every comment, look-alike and edit target"],
       edits=[
           (f"annotate member= source=src/real.sh stamp={RE} from=original", "applied",
            ("rep", "src/real.sh", f"# testmap:covers src/real.sh {RE}{W}")),
           (f"annotate member= source=src/new.sh stamp={NEW} from=original", "applied",
            ("ins", "src/real.sh", f"# testmap:covers src/new.sh {NEW}{W}")),
           (f"annotate member=NonAscii source=src/more.sh stamp={NEW} from=original", "applied",
            ("ins", "src/member.sh", f"# testmap:covers src/more.sh {NEW}{W}")),
           (f"raw kind=replace line=3 member= source=src/fake.sh from=original new=# testmap:covers src/fake.sh {RE}",
            "refused:not-comment"),
       ]),
]

# t1954_4: bash 5.3 function substitutions ${ cmd; } and ${| cmd; }, one
# holding a heredoc, one a quoted brace. bash 5.3.15 runs it (its output
# prints line 3 as heredoc data).
FIXTURES += [
    Fx("funsub_53.sh", f"""#!/bin/bash
x=${{ cat <<EOF
# testmap:covers src/fake_heredoc.sh{L}
EOF
}}
y=${{| REPLY="}}"; }}
# testmap:covers src/real.sh{W}
z=${{ echo "}}"; echo ok; }}
# testmap:covers src/real2.sh{W}
echo "$x $y $z"
""", native=NATIVE + ["bash-exec"], exec_="bash {file}",
       notes=["t1954_4: bash 5.3 ${ …; } / ${| …; } function substitutions with a heredoc and a quoted brace inside"]),
]
