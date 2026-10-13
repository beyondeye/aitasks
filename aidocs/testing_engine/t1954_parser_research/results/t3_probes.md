# t1954_3 elimination probes

Rerun: `feasibility/t3_probes.sh <scratch-dir>` (`T1954_SCC`, `T1954_PYGMENTS_PYTHON`; network for gpython). Evidence for eliminations and for the Pygments provider's design; nothing here is a provider. Corpus: 229 fixtures.

## scc 4.1.0 (count-only line classifier)

- per-file JSON fields: `Binary`, `Blank`, `Bytes`, `Code`, `Comment`, `Complexity`, `EndPoint`, `Extension`, `Filename`, `Generated`, `Hash`, `Language`, `Lines`, `Location`, `Minified`, `PossibleLanguages`, `Symlocation`, `Uloc`, `WeightedComplexity` — counts only, **no line or byte positions**, so no comment location can be read from it.
- fixtures whose `Comment` count equals the hand oracle's line-comment count: **139 / 229** (bash 24/67, go 13/21, java 8/11, kotlin 19/26, python 44/64, rust 8/10, swift 8/11, typescript 15/19). The two counts are not the same definition (scc counts block-comment lines too), so this is a coarse indicator only.

## gpython v0.2.0 (github.com/go-python/gpython/parser, pure Go)

- fixtures 64 (valid 61, malformed 3): lexed 60; valid rejected 1 [bom_doc.py.in]; malformed rejected 3.
- the lexer emits **no comment token**: it skips a line that is only whitespace and a comment, and stops a line at `#` (`parser/lexer.go`, 2 such sites); its token set has no COMMENT. So it cannot report comment locations without modifying it — a custom reader by another route. Grammar: Python 3.4 era, last release 2023-06-28, no PEP 701 (3.12) f-string tokenisation.

## Pygments 2.21.0

Tokenisation path vs exact reconstruction of the decoded text (`--normcheck`):

```json
{
 "fixtures": 228,
 "undecodable": 1,
 "not_reproduced": {
  "get_tokens(), stripnl/ensurenl off": {
   "count": 9,
   "files": [
    "bash/crlf.sh.in",
    "bash/crlf_edit.sh.in",
    "go/crlf.go.in",
    "java/Crlf.java.in",
    "kotlin/crlf.kt.in",
    "python/crlf_doc.py.in",
    "rust/crlf.rs.in",
    "swift/crlf.swift.in",
    "typescript/crlf.ts.in"
   ]
  },
  "get_tokens(), pygments defaults": {
   "count": 10,
   "files": [
    "bash/crlf.sh.in",
    "bash/crlf_edit.sh.in",
    "bash/nonl_edit.sh.in",
    "go/crlf.go.in",
    "java/Crlf.java.in",
    "kotlin/crlf.kt.in",
    "python/crlf_doc.py.in",
    "rust/crlf.rs.in",
    "swift/crlf.swift.in",
    "typescript/crlf.ts.in"
   ]
  },
  "tokens() (the provider path: get_tokens_unprocessed + ensurenl emulation)": {
   "count": 0,
   "files": []
  }
 }
}
```

`String.Doc` vs the Python module docstring (ast) (`--doccheck`): Pygments' Python lexer marks a triple-quoted string at a line start as String.Doc wherever it is, and has no statement model — so it cannot supply DocInfo (content bounds + statement end); the provider declares no DocLiterals.

```json
{
 "files": 59,
 "module_docstring": 35,
 "doc_token_on_docstring": 15,
 "doc_token_elsewhere": 3,
 "docstring_without_doc_token": 20,
 "stmt_end_differs": 2,
 "cases": [
  "doc_grouping_multiline.py.in: module docstring with no String.Doc token",
  "doc_implicit_concat.py.in: module docstring with no String.Doc token",
  "doc_paren_closing_later.py.in: module docstring with no String.Doc token",
  "doc_shape_01.py.in: module docstring with no String.Doc token",
  "doc_shape_03.py.in: module docstring with no String.Doc token",
  "doc_shape_04.py.in: String.Doc ends at 32, statement ends at 34",
  "doc_shape_05.py.in: String.Doc at byte 9 is not the module docstring",
  "doc_shape_06.py.in: String.Doc at byte 1 is not the module docstring",
  "docvalue_00.py.in: module docstring with no String.Doc token",
  "docvalue_01.py.in: module docstring with no String.Doc token",
  "docvalue_02.py.in: module docstring with no String.Doc token",
  "docvalue_03.py.in: module docstring with no String.Doc token",
  "docvalue_04.py.in: String.Doc ends at 8, statement ends at 38",
  "docvalue_05.py.in: module docstring with no String.Doc token",
  "docvalue_07.py.in: module docstring with no String.Doc token",
  "docvalue_08.py.in: module docstring with no String.Doc token",
  "docvalue_09.py.in: module docstring with no String.Doc token",
  "docvalue_10.py.in: module docstring with no String.Doc token",
  "docvalue_13.py.in: module docstring with no String.Doc token",
  "docvalue_14.py.in: module docstring with no String.Doc token",
  "docvalue_15.py.in: module docstring with no String.Doc token",
  "docvalue_16.py.in: module docstring with no String.Doc token",
  "docvalue_17.py.in: module docstring with no String.Doc token",
  "docvalue_18.py.in: module docstring with no String.Doc token",
  "not_doc_bytes.py.in: String.Doc at byte 1 is not the module docstring"
 ]
}
```
