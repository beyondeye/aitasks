"""hand_python.py - hand-oracle Python fixtures (t1954_1).

Docstring records are given explicitly with their DECODED values; each
docstring fixture with a record carries an edit op whose re-stamp must be
refused (Python docstrings are read, never written). The DocEnd shapes pin
the file-level placement to the statement's end, not the last literal's.
"""

from core import Fx, Rec

W, L, R, C = "⟦W⟧", "⟦L⟧", "⟦R⟧", "⟦C⟧"
NEW = "@2026-10-12/aaaaaaaaaa"
RE = "@2026-02-02/bbbbbbbbbb"
NATIVE = ["python-tokenize", "ast"]


def doc(line, source, stamp=""):
    return Rec(line, "", "covers", source, stamp, "docstring")


FIXTURES = [
    Fx("ordinary.py", f'''"""Ordinary test module.

testmap:covers src/doc_src.py @2026-01-02/0123456789{R}
"""
# testmap:kind unit{W}
# testmap:covers src/a.py{W}
import unittest


# testmap:unit TestA{W}
# testmap:covers src/a.py{W}
class TestA(unittest.TestCase):
    def test_x(self):
        s = "# testmap:covers src/fake.py"{L}
        self.assertTrue(s)  # trailing


if __name__ == "__main__":
    print("ok")
''', docrecs=[doc(3, "src/doc_src.py", "@2026-01-02/0123456789")], placement={"": 6, "TestA": 11},
       native=NATIVE + ["python-exec"], exec_="python3 {file}",
       notes=["several blocks cover src/a.py (file-level line 6, TestA line 11)"],
       edits=[
           (f"annotate member= source=src/doc_src.py stamp={RE}", "refused:docstring"),
           (f"raw kind=replace line=3 member= source=src/doc_src.py new=# testmap:covers src/doc_src.py {RE}", "refused:not-comment"),
           (f"annotate member= source=src/a.py stamp={RE} from=original", "applied",
            ("rep", 6, f"# testmap:covers src/a.py {RE}{W}")),
           (f"annotate member=TestA source=src/a.py stamp={RE} from=original", "applied",
            ("rep", 11, f"# testmap:covers src/a.py {RE}{W}")),
           (f"annotate member=TestA source=src/b.py stamp={NEW} from=original", "applied",
            ("ins", 11, f"# testmap:covers src/b.py {NEW}{W}")),
           (f"raw kind=replace line=14 member=TestA source=src/fake.py from=original new=# testmap:covers src/fake.py {RE}", "refused:not-comment"),
       ]),

    Fx("doc_grouping_multiline.py", f'''(
    "doc\\n"
    "testmap:covers src/g.sh"{R}
)
import os
''', docrecs=[doc(3, "src/g.sh")], placement={"": 4}, native=NATIVE,
       notes=["parenthesised implicit concatenation over lines 2-3; the statement ends on line 4 (DocEnd) — "
              "a fresh file-level line goes after the ')' line, not after the last literal"],
       edits=[(f"annotate member= source=src/g.sh stamp={RE}", "refused:docstring"),
              (f"annotate member= source=src/new.py stamp={NEW}", "applied",
               ("ins", 4, f"# testmap:covers src/new.py {NEW}{W}"))]),

    Fx("doc_implicit_concat.py", f'''"a\\n" \\
"testmap:covers src/x.sh"{R}
import os
''', docrecs=[doc(2, "src/x.sh")], placement={"": 2}, native=NATIVE,
       notes=["implicit concatenation across a backslash continuation: one docstring statement over lines 1-2"],
       edits=[(f"annotate member= source=src/x.sh stamp={RE}", "refused:docstring"),
              (f"annotate member= source=src/new.py stamp={NEW}", "applied",
               ("ins", 2, f"# testmap:covers src/new.py {NEW}{W}"))]),

    Fx("doc_raw.py", f'''r"""Raw docstring: \\n stays two characters.
testmap:covers src/raw.sh{R}
"""
import os
''', docrecs=[doc(2, "src/raw.sh")], placement={"": 3}, native=NATIVE,
       edits=[(f"annotate member= source=src/raw.sh stamp={RE}", "refused:docstring")]),

    Fx("doc_paren_closing_later.py", f'''("""Docstring whose statement closes later.
testmap:covers src/p.sh{R}
"""
)
# testmap:covers src/comment.sh{W}
''', docrecs=[doc(2, "src/p.sh")], placement={"": 5}, native=NATIVE,
       notes=["the literal ends on line 3, the statement on line 4; the file-level block already has line 5"],
       edits=[(f"annotate member= source=src/p.sh stamp={RE}", "refused:docstring"),
              (f"annotate member= source=src/comment.sh stamp={RE}", "applied",
               ("rep", 5, f"# testmap:covers src/comment.sh {RE}{W}"))]),

    Fx("not_doc_call.py", f'''("testmap:covers src/a.sh")("arg"){L}
# testmap:covers src/real.py{W}
''', native=NATIVE, notes=["a call, not grouping: no docstring"]),

    Fx("not_doc_fstring.py", f'''f"""testmap:covers src/f.sh{L}
"""
# testmap:covers src/real.py{W}
''', native=NATIVE, notes=["an f-string first statement is not a docstring"]),

    Fx("not_doc_bytes.py", f'''b"""testmap:covers src/b.sh{L}
"""
# testmap:covers src/real.py{W}
''', native=NATIVE, notes=["a bytes first statement is not a docstring"]),

    Fx("fstrings_312.py", f'''x = 1
s = f"{{f"{{x}}"}}"
t = f"""{{
    x  # a comment inside a replacement field (3.12+)
}}
# testmap:covers src/in_fstring.py{L}
"""
u = f"{{'# testmap:covers src/q.py'}}"{L}
# testmap:covers src/real.py{W}
print(s, len(t), u)
''', native=NATIVE + ["python-exec"], exec_="python3 {file}",
       notes=["PEP 701 f-strings: reused quotes, a comment inside a multi-line replacement field (line 4 starts inside "
              "the f-string: neither writable nor a look-alike), a token look-alike in the literal part"]),

    Fx("triple_strings.py", f'''import os
X = \'\'\'
# testmap:covers src/x.py{L}
\'\'\'
Y = """a""" """
# testmap:covers src/y.py{L}
"""
Z = r"""\\
# testmap:covers src/z.py{L}
"""
# testmap:covers src/real.py{W}
print(len(X + Y + Z), os.sep)
''', native=NATIVE + ["python-exec"], exec_="python3 {file}"),

    Fx("tstring_314.py", f'''name = "x"
t = t"""
# testmap:covers src/in_tstring.py{L}
{{name}}"""
# testmap:covers src/real.py{W}
print(type(t).__name__)
''', native=NATIVE + ["python-exec"], exec_="python3 {file}",
       notes=["PEP 750 template string (Python 3.14): an unknown prefix to older lexers"]),

    Fx("embedded_sql.py", f'''QUERY = """
-- testmap:covers src/q.sql{L}
# testmap:covers src/in_sql.py{L}
SELECT 1;
"""
JS = \'\'\'
// testmap:covers src/in_js.js{L}
\'\'\'
# testmap:covers src/real.py{W}
print(len(QUERY) + len(JS))
''', native=NATIVE + ["python-exec"], exec_="python3 {file}"),

    Fx("malformed_unterminated_single.py", f'''x = "never closed
# testmap:covers src/x.py{L}
''', uncertain=True, refuse="uncertain", native=NATIVE),

    Fx("syntax_error_lexically_valid.py", f'''def f(:
    pass
# testmap:covers src/x.py{W}
''', native=NATIVE,
       notes=["tokenizes cleanly, does not parse (ast): comment context is still certain, so the oracle reads the "
              "annotation; a provider that refuses is over-refusal (cost), not a safety failure"]),

    Fx("edits_uncertain.py", f'''# testmap:covers src/u.py{C}
X = """never closed
''', uncertain=True, refuse="uncertain", native=NATIVE,
       edits=[(f"annotate member= source=src/u.py stamp={RE}", "refused:uncertain"),
              (f"raw kind=replace line=1 member= source=src/u.py new=# testmap:covers src/u.py {RE}", "refused:uncertain")]),

    Fx("latin1_cookie.py", f'''# -*- coding: latin-1 -*-{C}
# café{C}
# testmap:covers src/latin1.py{W}
s = "naïve"
''', encoding="latin-1", native=NATIVE + ["python-exec"], exec_="python3 {file}",
       notes=["a coding cookie: offsets are bytes of the Latin-1 source"],
       edits=[(f"annotate member= source=src/latin1.py stamp={RE}", "applied",
               ("rep", 3, f"# testmap:covers src/latin1.py {RE}{W}"))]),

    Fx("crlf_doc.py", f'''"""Doc.
testmap:covers src/crlf_doc.py{R}
"""
# testmap:covers src/crlf.py{W}
print("crlf")
''', crlf=True, docrecs=[doc(2, "src/crlf_doc.py")], native=NATIVE + ["python-exec"], exec_="python3 {file}",
       edits=[(f"annotate member= source=src/crlf_doc.py stamp={RE}", "refused:docstring"),
              (f"annotate member= source=src/crlf2.py stamp={NEW}", "applied",
               ("ins", 4, f"# testmap:covers src/crlf2.py {NEW}{W}"))]),

    Fx("bom_doc.py", f'''"""Doc after a BOM.

testmap:covers src/bom_doc.py{R}
"""
print("bom")
''', bom=True, docrecs=[doc(3, "src/bom_doc.py")], placement={"": 4}, native=NATIVE + ["python-exec"],
       exec_="python3 {file}",
       notes=["Python skips a UTF-8 BOM, so line 1 opens the module docstring"],
       edits=[(f"annotate member= source=src/bom_doc.py stamp={RE}", "refused:docstring"),
              (f"annotate member= source=src/new.py stamp={NEW}", "applied",
               ("ins", 4, f"# testmap:covers src/new.py {NEW}{W}"))]),

    Fx("nodoc_fresh.py", '''#!/usr/bin/env python3
# Header comment.
import sys
print(sys.version_info[0])
''', placement={"": 2}, native=NATIVE + ["python-exec"], exec_="python3 {file}",
       edits=[(f"annotate member= source=src/fresh.py stamp={NEW}", "applied",
               ("ins", 2, f"# testmap:covers src/fresh.py {NEW}{W}"))]),
]
