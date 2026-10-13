"""m22.py - the landed M2.2 fixtures, imported from the PINNED commit.

Sources (read with `git show <pin>:<path>`, never from the working tree):
  annot/testdata/parse/*.in + .golden      -> parse fixtures (records from the goldens)
  annot/testdata/placement/*.in + .golden  -> placement fixtures with one edit op
  annot/lexctx_test.go                     -> TestClassify* case tables (hand-written class strings)
  annot/grammar_test.go                    -> TestDocstringValue (decoded values / refusals)

The .expect files are DERIVED from those landed expectations; nothing here
consults the running code.
"""

import ast
import json
import os
import re
import subprocess

from core import ANNOT, Fx, Rec

ANNOT_DIR = "goengines/internal/testmap/annot"
MARK = {"W": "⟦W⟧", "L": "⟦L⟧", "R": "⟦R⟧", "C": "⟦C⟧"}
STAMP_NEW = "@2026-10-12/aaaaaaaaaa"
RESTAMP = "@2026-02-02/bbbbbbbbbb"


def pin(research_dir):
    vals = {}
    with open(os.path.join(research_dir, "baseline", "PIN")) as f:
        for line in f:
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                vals[k.strip()] = v.strip()
    return vals["commit"]


def show(commit, path):
    return subprocess.run(["git", "show", "%s:%s" % (commit, path)], check=True, capture_output=True).stdout


def ls(commit, path):
    out = subprocess.run(["git", "ls-tree", "--full-tree", "--name-only", "%s:%s" % (commit, path)], check=True,
                         capture_output=True, text=True).stdout
    return sorted(out.split())


def lang_dir(name):
    ext = os.path.splitext(name)[1]
    return {".sh": "bash", ".py": "python", ".go": "go", ".kt": "kotlin"}[ext]


def mark(lines, marks):
    return "\n".join(l + (MARK[marks[i + 1]] if (i + 1) in marks else "") for i, l in enumerate(lines))


def golden_lines(units):
    """(line, docstring, record) for every record a parse golden pins."""
    out = []
    for u in units:
        member = u.get("member", "")
        if member:
            out.append((u["opener"]["no"], False, Rec(u["opener"]["no"], member, "unit", member)))
        for key in ("kind", "runner", "batch", "reviewed"):
            if u.get(key):
                kv = u[key]
                out.append((kv["line"]["no"], kv["line"].get("docstring", False),
                            Rec(kv["line"]["no"], member, kv["key"], " ".join(kv["args"]),
                                origin="docstring" if kv["line"].get("docstring") else "comment")))
        for key in ("areas", "scopes", "triggers", "reads", "needs", "axes"):
            for kv in u.get(key) or []:
                out.append((kv["line"]["no"], kv["line"].get("docstring", False),
                            Rec(kv["line"]["no"], member, kv["key"], " ".join(kv["args"]),
                                origin="docstring" if kv["line"].get("docstring") else "comment")))
        for c in u.get("covers") or []:
            st = c["stamp"]
            stamp = "@%s/%s" % (st["date"], st["blob"]) if st.get("date") else ""
            doc = c["line"].get("docstring", False)
            out.append((c["line"]["no"], doc, Rec(c["line"]["no"], member, "covers", c["source"], stamp,
                                                  "docstring" if doc else "comment")))
    return out


# Hand-reviewed: token-mentioning lines of the parse fixtures that are real
# prose comments (not testmap-shaped data). Every other such line is data.
PROSE_COMMENTS = {("go_members.go", 7)}


def is_line_comment(name, lines, i):
    return (name, i + 1) in PROSE_COMMENTS


def parse_fixtures(commit):
    fx = []
    base = ANNOT_DIR + "/testdata/parse"
    for n in ls(commit, base):
        if not n.endswith(".in"):
            continue
        name = n[:-3]
        raw = show(commit, base + "/" + n)
        units = json.loads(show(commit, base + "/" + name + ".golden"))
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        lines = text.split("\n")
        recs = golden_lines(units)
        marks, docrecs = {}, []
        for no, doc, r in recs:
            marks[no] = "R" if doc else "W"
            if doc:
                docrecs.append(r)
        leader = "#" if name.endswith((".sh", ".py")) else "//"
        for i, l in enumerate(lines):
            if "testmap:" in l and (i + 1) not in marks:
                # a comment that mentions the token (prose) is a plain comment, not data
                marks[i + 1] = "C" if (l.lstrip().startswith(leader) and is_line_comment(name, lines, i)) else "L"
        src = mark(lines, marks)
        # W-derived records must equal the golden's comment records.
        fx.append((lang_dir(name), Fx(name, src, docrecs=docrecs, crlf=crlf, expect_bytes=raw, origin="M2.2 annot/testdata/parse/" + n + " (+ .golden) @ " + commit[:12])))
    return fx


PLACEMENT_MEMBER = {"kotlin_member.kt": "Welcome", "kotlin_member_existing.kt": "Welcome"}


def placement_fixtures(commit):
    fx = []
    base = ANNOT_DIR + "/testdata/placement"
    for n in ls(commit, base):
        if not n.endswith(".in"):
            continue
        name = n[:-3]
        before = show(commit, base + "/" + n).decode("utf-8").split("\n")
        after = show(commit, base + "/" + name + ".golden").decode("utf-8").split("\n")
        assert len(after) == len(before) + 1, name
        i = 0
        while before[i] == after[i]:
            i += 1
        assert before[i:] == after[i + 1:], name
        marks = {}
        for k, l in enumerate(before):
            if ANNOT.match(l):
                marks[k + 1] = "W"
        member = PLACEMENT_MEMBER.get(name, "")
        op = "annotate member=%s source=src/new stamp=%s" % (member, STAMP_NEW)
        fx.append((lang_dir(name), Fx("placement_" + name, mark(before, marks), placement={member: i},
                                      expect_bytes=show(commit, base + "/" + n),
                                      edits=[(op, "applied", ("ins", i, after[i] + MARK["W"]))],
                                      origin="M2.2 annot/testdata/placement/" + n + " (+ .golden) @ " + commit[:12])))
    return fx


GO_STR = re.compile(r'"(?:[^"\\]|\\.)*"')


def go_expr(expr, env):
    """Evaluate a Go concatenation of interpreted string literals and names."""
    out = []
    for part in [p.strip() for p in split_plus(expr)]:
        if part.startswith('"'):
            out.append(ast.literal_eval(part))
        else:
            out.append(env[part])
    return "".join(out)


def split_plus(expr):
    parts, cur, i, inq = [], "", 0, False
    while i < len(expr):
        c = expr[i]
        if inq:
            cur += c
            if c == "\\":
                cur += expr[i + 1]
                i += 1
            elif c == '"':
                inq = False
        elif c == '"':
            inq = True
            cur += c
        elif c == "+":
            parts.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    parts.append(cur)
    return parts


def lex_tables(commit):
    src = show(commit, ANNOT_DIR + "/lexctx_test.go").decode("utf-8")
    look = "# testmap:covers x @2026-01-01/0123456789"
    env = {"look": look, "kl": look.replace("#", "//", 1), "gl": look.replace("#", "//", 1)}
    out = []
    for fn, ext in (("TestClassifyBash", ".sh"), ("TestClassifyPython", ".py"), ("TestClassifyKotlin", ".kt"), ("TestClassifyGo", ".go")):
        body = src[src.index("func " + fn):]
        body = body[: body.index("\n}\n")]
        table = body[body.index("[]lexCase{"):]
        for m in re.finditer(r'^\s*\{("(?:[^"\\]|\\.)*"),\s*(.*?),\s*("(?:[^"\\]|\\.)*"),\s*(\d+)\},\s*$', table, re.M):
            name = ast.literal_eval(m.group(1))
            text = go_expr(m.group(2), env)
            want = ast.literal_eval(m.group(3))
            unc = int(m.group(4))
            out.append((fn, ext, name, text, want, unc))
    return out, src


# Where the landed M2.2 expectation is M2.2's deliberate fail-closed refusal or
# policy rather than ground truth, the native tool decides (bash 5.3
# execution, see results/oracle_check.md) and the divergence is recorded:
#  - certain: the file is valid and its lexical context determined; M2.2's
#    refusal is then measured as over-refusal (cost), never a safety failure;
#  - policy: a REAL comment that M2.2 by design never treats as an annotation
#    line (inside a backtick substitution, or a continuation line); a subject
#    classing it Comment is a policy divergence, not data exposure.
LEX_OVERRIDES = {
    ("TestClassifyBash", "arith-or-subshell-across-lines"): dict(
        certain=True, note="bash accepts and runs it (a subshell inside $( … )); M2.2 refuses the ambiguous `$((` form by design"),
    ("TestClassifyBash", "heredoc-escape-in-quoted-delimiter"): dict(
        certain=True, writable={3},
        note="bash decodes the $'E\\x4fF' delimiter to EOF: line 2 ends an empty body and line 3 is a real annotation; "
             "M2.2 refuses ANSI-C escapes in delimiters by design"),
    ("TestClassifyBash", "backtick-spanning"): dict(
        policy={2}, note="a real bash comment inside a backtick substitution; M2.2 classes backtick bodies as data by "
                         "design (their bytes are escape-processed before the inner parse)"),
    ("TestClassifyBash", "continuation-line-is-code"): dict(
        policy={2}, note="bash joins the continuation: line 2 is a trailing comment of `echo a`, never an annotation line (M2.2 policy)"),
    ("TestClassifyPython", "continuation"): dict(
        policy={2}, note="tokenize joins the continuation: line 2 is a comment trailing `x = 1 +` (an incomplete expression); "
                         "never an annotation line (M2.2 policy)"),
    ("TestClassifyBash", "heredoc-in-backticks"): dict(
        native_differs="validity", note="`bash -n` accepts; executing it warns 'here-document delimited by end-of-file' "
                                        "(the heredoc inside the backtick substitution is unterminated): malformed, like "
                                        "lex_unterminated_heredoc"),
    ("TestClassifyBash", "heredoc-strip-continuation"): dict(
        native_differs="4", note="bash execution confirms line 4 is heredoc data (an unquoted body joins `prefix\\` with "
                                 "the next line before the delimiter is compared); mvdan/sh treats line 3 as the terminator"),
}


def lex_fixtures(commit):
    fx = []
    cases, _ = lex_tables(commit)
    for fn, ext, name, text, want, unc in cases:
        ov = LEX_OVERRIDES.get((fn, name), {})
        if ov.get("certain"):
            unc = 0
            want = None
        lines = text.split("\n")
        assert lines[-1] == "", name
        body = lines[:-1]
        marks, docrecs = {}, []
        refuse = None
        if unc:
            for i, l in enumerate(body):
                if "testmap:" in l:
                    marks[i + 1] = "L"
            if ext == ".py" or "testmap:" in text:
                refuse = "uncertain@%d" % unc
        elif want is None:
            for i, l in enumerate(body):
                if (i + 1) in ov.get("writable", ()):
                    marks[i + 1] = "W"
                elif "testmap:" in l:
                    marks[i + 1] = "L"
        else:
            assert len(want) == len(body), (name, want, body)
            for i, (cls, l) in enumerate(zip(want, body)):
                if cls == "#":
                    marks[i + 1] = "W" if ANNOT.match(l) else "C"
                elif "testmap:" in l:
                    marks[i + 1] = "L"
            if fn == "TestClassifyPython" and name == "docstring":
                marks[3] = "R"
                docrecs.append(Rec(3, "", "covers", "a.py", "", "docstring"))
        d = {".sh": "bash", ".py": "python", ".kt": "kotlin", ".go": "go"}[ext]
        fname = "lex_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") + ext
        extra = {}
        if ov.get("policy"):
            extra["x-policy"] = ",".join(str(n) for n in sorted(ov["policy"]))
        if ov.get("native_differs"):
            extra["x-native-differs"] = ov["native_differs"]
        fx.append((d, Fx(fname, mark(body, marks) + "\n", uncertain=bool(unc), refuse=refuse, docrecs=docrecs,
                         notes=[ov["note"]] if ov else [], extra=extra,
                         origin="M2.2 annot/lexctx_test.go %s %r @ %s" % (fn, name, commit[:12]))))
    return fx


# TestClassifyPython's docstring-shape table: (src, first, end, content) plus
# the hand-derived statement end (DocEnd) used for placement.
DOC_DOCEND = {0: 3, 1: 1, 2: 1, 3: 1, 4: 4}


def doc_fixtures(commit):
    _, src = lex_tables(commit)
    body = src[src.index("docs := []struct"):]
    body = body[: body.index("\n\t}\n")]
    fx = []
    for i, m in enumerate(re.finditer(r'^\s*\{("(?:[^"\\]|\\.)*"),\s*(\d+),\s*(\d+),\s*("(?:[^"\\]|\\.)*")\},\s*$', body, re.M)):
        text = ast.literal_eval(m.group(1))
        first = int(m.group(2))
        lines = text.split("\n")[:-1]
        marks, docrecs = {}, []
        for k, l in enumerate(lines):
            t = l.strip()
            if "testmap:" in l:
                if first and l.lstrip().startswith("#"):
                    marks[k + 1] = "W"
                elif first:
                    marks[k + 1] = "R"
                    mm = re.search(r"testmap:covers (\S+?)(\"\"\"|$)", l)
                    docrecs.append(Rec(k + 1, "", "covers", mm.group(1), "", "docstring"))
                else:
                    marks[k + 1] = "L"
            elif t.startswith("#") and not t.startswith("#!") and "coding" not in t:
                marks[k + 1] = "C"
        place = DOC_DOCEND.get(i, 0) if first else 0
        if not first and lines and lines[0].startswith("#"):
            place = 1
        edits = []
        for r in docrecs:
            edits.append(("annotate member= source=%s stamp=%s" % (r.value, RESTAMP), "refused:docstring"))
        fx.append(("python", Fx("doc_shape_%02d.py" % i, "\n".join(l + (MARK[marks[k + 1]] if k + 1 in marks else "") for k, l in enumerate(lines)) + "\n",
                                docrecs=docrecs, placement={"": place}, edits=edits, native=["python-tokenize", "ast"],
                                origin="M2.2 annot/lexctx_test.go TestClassifyPython docs[%d] @ %s" % (i, commit[:12]),
                                notes=["docstring literal lines %s-%s; placement = the statement's last line (DocEnd)" % (m.group(2), m.group(3))] if first else ["not a docstring"])))
    return fx


def docvalue_fixtures(commit):
    src = show(commit, ANNOT_DIR + "/grammar_test.go").decode("utf-8")
    body = src[src.index("func TestDocstringValue"):]
    body = body[: body.index("\n}\n")]
    fx = []
    for i, m in enumerate(re.finditer(r'^\s*\{("(?:[^"\\]|\\.)*"),\s*("(?:[^"\\]|\\.)*")\},', body, re.M)):
        text = ast.literal_eval(m.group(1))
        covers = ast.literal_eval(m.group(2))
        lines = text.split("\n")[:-1]
        marks, docrecs, refuse, edits = {}, [], None, []
        if covers == "!":
            refuse = "syntax"  # M2.2 pins a refusal, not its line
            for k, l in enumerate(lines):
                if "testmap" in l or "estmap" in l:
                    marks[k + 1] = "L"
            edits.append(("annotate member= source=src/zz.sh stamp=%s" % RESTAMP, "refused:syntax"))
        elif covers:
            for item in covers.split(","):
                no, source = item.split(":", 1)
                no = int(no)
                if lines[no - 1].lstrip().startswith("#"):
                    marks[no] = "W"
                    edits.append(("annotate member= source=%s stamp=%s" % (source, RESTAMP), "applied",
                                  ("rep", no, "# testmap:covers %s %s%s" % (source, RESTAMP, MARK["W"]))))
                else:
                    marks[no] = "R"
                    docrecs.append(Rec(no, "", "covers", source, "", "docstring"))
                    edits.append(("annotate member= source=%s stamp=%s" % (source, RESTAMP), "refused:docstring"))
        else:
            for k, l in enumerate(lines):
                if "testmap" in l:
                    marks[k + 1] = "L"
        fx.append(("python", Fx("docvalue_%02d.py" % i, "\n".join(l + (MARK[marks[k + 1]] if k + 1 in marks else "") for k, l in enumerate(lines)) + "\n",
                                docrecs=docrecs, refuse=refuse, edits=edits, native=["python-tokenize", "ast"],
                                origin="M2.2 annot/grammar_test.go TestDocstringValue[%d] @ %s" % (i, commit[:12]))))
    return fx


def anchor_fixtures(commit):
    """The anchor checks embedded in TestClassifyKotlin / TestClassifyGo."""
    return [
        ("kotlin", Fx("lex_anchors.kt", "package a\n\nimport b.C\nimport d.E\n\nclass T {\n  import x\n}\n", placement={"": 4},
                      origin="M2.2 annot/lexctx_test.go TestClassifyKotlin (Package 1, Import 4) @ " + commit[:12])),
        ("go", Fx("lex_anchors.go", "//go:build x\u27e6C\u27e7\n\n// Package a.⟦C⟧\npackage a\n", placement={"": 4},
                  origin="M2.2 annot/lexctx_test.go TestClassifyGo (Package 4) @ " + commit[:12])),
    ]


def all_fixtures(research_dir):
    commit = pin(research_dir)
    return (parse_fixtures(commit) + placement_fixtures(commit) + lex_fixtures(commit)
            + doc_fixtures(commit) + docvalue_fixtures(commit) + anchor_fixtures(commit))
