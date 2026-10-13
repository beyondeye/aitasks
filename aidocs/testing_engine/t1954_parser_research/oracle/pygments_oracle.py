#!/usr/bin/env python3
"""pygments_oracle.py - Pygments as a t1954 provider helper (t1954_3).

Protocol (one long-lived process): each stdin line is a JSON object
{"src": "<base64 bytes>", "lang": "<research lang>"}; each stdout line
answers it with
  {"tokens": [[start, end, type, text_b64], ...],   # BYTE offsets of the ORIGINAL source
   "codec": "<codec the text was decoded with>"}
or {"unsupported": "<what>"} when the bytes do not decode, or
{"error": "<msg>"}. A line {"version": true} answers {"version": "<pygments version>"}.

Pygments lexes DECODED text and reports code-point indices
(get_tokens_unprocessed). The t1954_3 position-conversion contract requires
original-source byte offsets, so this helper decodes exactly as the language
would — Python via tokenize.detect_encoding (UTF-8 BOM, PEP 263 cookie such as
Latin-1), every other language as strict UTF-8 after any BOM — and converts
each index to bytes under that SAME codec, adding the BOM length. Every
token's text is returned re-encoded with that codec, so the Go side can check
src[start:end] == text (Layer 1). Bytes that do not decode are refused,
never guessed.

Lexer options are forced to stripnl=False, ensurenl=False, tabsize=0 (the
defaults strip leading/trailing newlines and append one), and tokens come from
get_tokens_unprocessed() on the decoded text: get_tokens() always rewrites
CRLF/CR to LF, which would move every offset after a line break (--normcheck).
Because that skips ensurenl, which Pygments documents as required by
line-wise lexers, an input without a final newline is lexed with one and the
appended character is trimmed off the last token.

Other modes (findings evidence, not the provider path):
  pygments_oracle.py --normcheck <corpus-dir>   default-option normalisation count
  pygments_oracle.py --doccheck <corpus-dir>    String.Doc vs the module docstring

Named *_oracle.py so tests/run_all_python_tests.sh (test_*.py) never collects it.
"""

import base64
import glob
import io
import json
import os
import sys
import tokenize

import pygments
from pygments.lexers import get_lexer_by_name

LEXER = {
    "bash": "bash", "python": "python", "go": "go", "kotlin": "kotlin",
    "typescript": "typescript", "tsx": "tsx", "javascript": "javascript",
    "java": "java", "rust": "rust", "swift": "swift",
}
OPTS = dict(stripnl=False, ensurenl=False, tabsize=0)
BOM = b"\xef\xbb\xbf"


class Undecodable(Exception):
    pass


def decode(src, lang):
    """-> (text, codec, base): base is the byte offset the text starts at."""
    if lang == "python":
        try:
            enc, _ = tokenize.detect_encoding(io.BytesIO(src).readline)
        except SyntaxError as e:
            raise Undecodable("encoding declaration: %s" % e)
        if enc == "utf-8-sig":
            enc = "utf-8"
        base = 3 if src.startswith(BOM) else 0
    else:
        enc, base = "utf-8", (3 if src.startswith(BOM) else 0)
    try:
        return src[base:].decode(enc, "strict"), enc, base
    except UnicodeDecodeError as e:
        raise Undecodable("%s: %s" % (enc, e))


def tokens(src, lang, opts=OPTS):
    text, codec, base = decode(src, lang)
    lexer = get_lexer_by_name(LEXER[lang], **opts)
    # char index -> byte offset under the same codec
    cb = [0] * (len(text) + 1)
    b = base
    for i, ch in enumerate(text):
        cb[i] = b
        b += len(ch.encode(codec))
    cb[len(text)] = b
    # ensurenl emulation: Pygments documents ensurenl ("Make sure that the
    # input ends with a newline", default True) as REQUIRED by lexers that
    # consume input linewise (the Bash lexer's comment rule needs the "\n").
    # get_tokens_unprocessed skips that preprocessing, so the newline is
    # appended here and the one appended character trimmed back off the
    # last token — a documented normalisation, never an offset change.
    lexed = text if text.endswith("\n") or not text else text + "\n"
    out = []
    for i, ttype, value in lexer.get_tokens_unprocessed(lexed):
        j = i + len(value)
        if j > len(text):
            j = len(text)  # only the appended newline lies past the text
            value = value[: j - i]
        if not value:
            continue
        out.append([cb[i], cb[j], str(ttype), base64.b64encode(value.encode(codec)).decode()])
    return out, codec


def analyze(req):
    src = base64.b64decode(req["src"])
    try:
        toks, codec = tokens(src, req["lang"])
    except Undecodable as e:
        return {"unsupported": "decodable-input (%s)" % e}
    return {"tokens": toks, "codec": codec}


def corpus_cases(corpus):
    ext_lang = {".sh": "bash", ".py": "python", ".go": "go", ".kt": "kotlin", ".kts": "kotlin", ".ts": "typescript",
                ".mts": "typescript", ".tsx": "tsx", ".js": "javascript", ".jsx": "javascript",
                ".mjs": "javascript", ".java": "java", ".rs": "rust", ".swift": "swift"}
    for p in sorted(glob.glob(os.path.join(corpus, "*", "*.in"))):
        ext = os.path.splitext(p[:-3])[1]
        if ext in ext_lang:
            with open(p, "rb") as f:
                yield p, ext_lang[ext], f.read()


def normcheck(corpus):
    """How many fixtures does each tokenisation path fail to reproduce exactly?

    get_tokens() always preprocesses (CRLF/CR -> LF, and with the default
    options strips leading/trailing newlines and ensures a final one);
    get_tokens_unprocessed() on the decoded text is what the provider uses."""
    rows = {"get_tokens(), stripnl/ensurenl off": [], "get_tokens(), pygments defaults": [],
            "tokens() (the provider path: get_tokens_unprocessed + ensurenl emulation)": []}
    n = undec = 0
    for p, lang, src in corpus_cases(corpus):
        try:
            text, _, _ = decode(src, lang)
        except Undecodable:
            undec += 1
            continue
        n += 1
        name = os.path.relpath(p, corpus)
        for label, opts in (("get_tokens(), stripnl/ensurenl off", OPTS), ("get_tokens(), pygments defaults", {})):
            lexer = get_lexer_by_name(LEXER[lang], **opts)
            if "".join(v for _, v in lexer.get_tokens(text)) != text:
                rows[label].append(name)
        # the provider path: byte spans must tile the source and their texts reproduce it
        toks, _ = tokens(src, lang)
        start = 3 if src.startswith(BOM) else 0
        pos, ok = start, True
        for s, e, _, t in toks:
            ok = ok and s == pos and base64.b64decode(t) == src[s:e]
            pos = e
        if not (ok and pos == len(src)):
            rows["tokens() (the provider path: get_tokens_unprocessed + ensurenl emulation)"].append(name)
    print(json.dumps({"fixtures": n, "undecodable": undec,
                      "not_reproduced": {k: {"count": len(v), "files": v} for k, v in rows.items()}}, indent=1))


def doccheck(corpus):
    """Does String.Doc identify the Python module docstring (and its end)?"""
    import ast
    res = {"files": 0, "module_docstring": 0, "doc_token_on_docstring": 0,
           "doc_token_elsewhere": 0, "docstring_without_doc_token": 0, "stmt_end_differs": 0, "cases": []}
    for p, lang, src in corpus_cases(corpus):
        if lang != "python":
            continue
        try:
            text, codec, base = decode(src, lang)
            tree = ast.parse(src)
        except Exception:
            continue
        res["files"] += 1
        lines = src.split(b"\n")
        starts, acc = [], 0
        for ln in lines:
            starts.append(acc)
            acc += len(ln) + 1

        def off(row, col):
            return starts[row - 1] + col

        doc = None
        b = tree.body
        if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) and isinstance(b[0].value.value, str):
            doc = (off(b[0].lineno, b[0].col_offset), off(b[0].end_lineno, b[0].end_col_offset))
            res["module_docstring"] += 1
        toks, _ = tokens(src, lang)
        docs = [(s, e) for s, e, t, _ in toks if t == "Token.Literal.String.Doc"]
        on = [d for d in docs if doc and doc[0] <= d[0] < doc[1]]
        elsewhere = [d for d in docs if not (doc and doc[0] <= d[0] < doc[1])]
        res["doc_token_elsewhere"] += len(elsewhere)
        if doc:
            if on:
                res["doc_token_on_docstring"] += 1
                if max(e for _, e in on) != doc[1]:
                    res["stmt_end_differs"] += 1
                    res["cases"].append("%s: String.Doc ends at %d, statement ends at %d" % (os.path.basename(p), max(e for _, e in on), doc[1]))
            else:
                res["docstring_without_doc_token"] += 1
                res["cases"].append("%s: module docstring with no String.Doc token" % os.path.basename(p))
        for d in elsewhere:
            res["cases"].append("%s: String.Doc at byte %d is not the module docstring" % (os.path.basename(p), d[0]))
    print(json.dumps(res, indent=1))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--normcheck":
        return normcheck(sys.argv[2])
    if len(sys.argv) == 3 and sys.argv[1] == "--doccheck":
        return doccheck(sys.argv[2])
    for line in sys.stdin:
        req = json.loads(line)
        if req.get("version"):
            resp = {"version": pygments.__version__}
        else:
            try:
                resp = analyze(req)
            except Exception as e:  # a helper failure is reported, never an empty result
                resp = {"error": "%s: %s" % (type(e).__name__, e)}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
