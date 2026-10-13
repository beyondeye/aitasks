#!/usr/bin/env python3
"""py_oracle.py - Python tokenize + ast oracle for the t1954 parser research.

Protocol (one long-lived process): each stdin line is a JSON object
{"src": "<base64 bytes>"}; each stdout line answers it with
  {"spans": [[start, end, kind], ...],      # byte offsets; kind: comment | string
   "diags": [[start, end, reason], ...],    # tokenize / ast errors
   "doc":   null | {"literals": [[content_start, content_end, raw], ...],
                    "stmt_end": n}}         # the module docstring, byte offsets
A line {"version": true} answers {"version": "<python version>"}.

The input is only tokenized and parsed (ast.parse), never compiled to code
objects or executed. Named *_oracle.py so tests/run_all_python_tests.sh
(test_*.py) never collects it.
"""

import ast
import base64
import io
import json
import sys
import token
import tokenize

FSTRING_START = getattr(token, "FSTRING_START", None)
FSTRING_END = getattr(token, "FSTRING_END", None)
TSTRING_START = getattr(token, "TSTRING_START", None)
TSTRING_END = getattr(token, "TSTRING_END", None)
OPENERS = {t for t in (FSTRING_START, TSTRING_START) if t is not None}
CLOSERS = {t for t in (FSTRING_END, TSTRING_END) if t is not None}


class Offsets:
    """Maps tokenize (row, char-col) and ast (row, utf8-col) to byte offsets."""

    def __init__(self, src, enc):
        self.src, self.enc = src, enc
        self.bom = 3 if src.startswith(b"\xef\xbb\xbf") else 0
        self.starts = [0]
        for i, b in enumerate(src):
            if b == 0x0A and i + 1 <= len(src):
                self.starts.append(i + 1)

    def _line(self, row):
        s = self.starts[row - 1] + (self.bom if row == 1 else 0)
        e = self.starts[row] if row < len(self.starts) else len(self.src)
        return s, self.src[s:e]

    def char(self, row, col):
        if row > len(self.starts):
            return len(self.src)
        s, raw = self._line(row)
        text = raw.decode(self.enc, errors="surrogateescape")
        return s + len(text[:col].encode(self.enc, errors="surrogateescape"))

    def utf8(self, row, col):
        if row > len(self.starts):
            return len(self.src)
        s, raw = self._line(row)
        text = raw.decode(self.enc, errors="surrogateescape")
        chars = text.encode("utf-8", errors="surrogateescape")[:col].decode("utf-8", errors="surrogateescape")
        return s + len(chars.encode(self.enc, errors="surrogateescape"))


def literal_bounds(tok_string, start, end):
    i = 0
    while i < len(tok_string) and tok_string[i] not in "'\"":
        i += 1
    prefix = tok_string[:i]
    q = tok_string[i:i + 3]
    quote = q if q in ('"""', "'''") else tok_string[i:i + 1]
    return start + len(prefix) + len(quote), end - len(quote), "r" in prefix.lower()


def analyze(src):
    out = {"spans": [], "diags": [], "doc": None}
    try:
        enc, _ = tokenize.detect_encoding(io.BytesIO(src).readline)
    except SyntaxError as e:
        out["diags"].append([0, 0, "encoding: %s" % e])
        return out
    if enc == "utf-8-sig":
        enc = "utf-8"
    off = Offsets(src, enc)
    strings = []  # (start, end, tok) of plain STRING tokens, for the docstring
    depth, fstart = 0, 0
    try:
        for t in tokenize.tokenize(io.BytesIO(src).readline):
            if t.type == token.ENCODING:
                continue
            s = off.char(*t.start)
            e = off.char(*t.end)
            if t.type in OPENERS:
                if depth == 0:
                    fstart = s
                depth += 1
            elif t.type in CLOSERS:
                depth -= 1
                if depth == 0:
                    out["spans"].append([fstart, e, "string"])
            elif depth > 0:
                if t.type == token.COMMENT:
                    out["spans"].append([s, e, "comment"])
            elif t.type == token.COMMENT:
                out["spans"].append([s, e, "comment"])
            elif t.type == token.STRING:
                out["spans"].append([s, e, "string"])
                strings.append((s, e, t))
            elif t.type == token.ERRORTOKEN:
                out["diags"].append([s, e, "error token %r" % t.string])
    except (tokenize.TokenError, SyntaxError) as e:
        pos = getattr(e, "args", [None, None])
        row, col = 1, 0
        if isinstance(e, SyntaxError) and e.lineno:
            row, col = e.lineno, max((e.offset or 1) - 1, 0)
        elif len(pos) > 1 and isinstance(pos[1], tuple):
            row, col = pos[1]
        at = off.char(row, col) if row <= len(off.starts) else len(src)
        out["diags"].append([at, at, "tokenize: %s" % (e.args[0] if e.args else e)])
        return out
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError) as e:
        row = getattr(e, "lineno", None) or 1
        col = max((getattr(e, "offset", None) or 1) - 1, 0)
        at = off.utf8(row, col) if row <= len(off.starts) else len(src)
        out["diags"].append([at, at, "ast: %s" % getattr(e, "msg", e)])
        return out
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        stmt = body[0]
        lo = off.utf8(stmt.lineno, stmt.col_offset)
        hi = off.utf8(stmt.end_lineno, stmt.end_col_offset)
        lits = []
        for s, e, t in strings:
            if lo <= s and e <= hi:
                cs, ce, raw = literal_bounds(t.string, s, e)
                lits.append([cs, ce, raw])
        out["doc"] = {"literals": lits, "stmt_end": hi}
    return out


def main():
    for line in sys.stdin:
        req = json.loads(line)
        if req.get("version"):
            resp = {"version": sys.version.split()[0]}
        else:
            try:
                resp = analyze(base64.b64decode(req["src"]))
            except Exception as e:  # an oracle failure is reported, never an empty result
                resp = {"error": "%s: %s" % (type(e).__name__, e)}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
