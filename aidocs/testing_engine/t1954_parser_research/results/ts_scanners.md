# Tree-sitter: hand-written code per grammar, and how it is checked (t1954_2)

Research date: 2026-10-13. gotreesitter v0.55.1, C references at the
`tsref/LOCK` commits (the same commits as gotreesitter's `languages.lock`).

A tree-sitter grammar's tables are generated, but three kinds of
**hand-written** code also decide where comments and strings begin and end.
Each kind is "a custom reader by another name", so it is listed here and
verified hardest:
1. **External scanners.** Upstream they are C (`src/scanner.c`). In
   gotreesitter they are Go ports (`grammars/runtime/<lang>_scanner.go`;
   Python's is `grammars/internal/pythonruntime/`).
2. **Hand-written lexers** that replace the generated DFA lexer in
   gotreesitter (`grammars/runtime/<lang>_lexer.go`).
3. **Owned grammars.** gotreesitter re-implements the grammar itself in its
   Go DSL ("own" in `grammars/grammar_ownership.go`), so its parse tables
   are not upstream's `parser.c` tables.

## Inventory

Lines are counted by `wc -l` at the pinned versions. The upstream line
counts are the C sources fetched by `tsref/fetch.sh`.

| grammar | upstream `scanner.c` (lines) | constructs the scanner owns (the grammar's `externals`) | gotreesitter Go port (lines) | hand-written Go lexer | table source in gotreesitter | grammar-local tests in gotreesitter (`grammars/<lang>_*_test.go`) |
|---|---|---|---|---|---|---|
| bash | yes (1,217) | heredocs (`heredoc_start`, `simple_heredoc_body`, `heredoc_content`, `heredoc_end`), `<<`/`<<-`, regex, expansion words, `extglob_pattern`, `variable_name`, `file_descriptor`, concat, error recovery | `bash_scanner.go` (1,556) | — | mirror (ts2go-extracted from upstream `parser.c`) | 7 |
| python | yes (437) | `_newline`, `_indent`, `_dedent`, `string_start`, `_string_content`, `escape_interpolation`, `string_end`, `comment` | `internal/pythonruntime` (902) | — | mirror | 2 |
| go | none | — | `go_scanner.go` + `go_lexer.go` (1,196): automatic-semicolon scanner + hand-written lexer | **yes** | **own** (grammargen Go DSL) | 2 |
| kotlin | yes (979) | `_automatic_semicolon`, `multiline_comment`, `_string_start`, `_string_end`, `string_content`, interpolation starts, `_import_dot`, … | `kotlin_scanner.go` (1,001) | — | mirror | 2 |
| typescript | yes (13 + shared `common/scanner.h` 347) | `_automatic_semicolon`, `_template_chars`, `_ternary_qmark`, `html_comment`, `escape_sequence`, `regex_pattern`, `jsx_text`, … | `typescript_scanner.go` (506) | — | mirror | 4 |
| tsx | yes (13 + shared 347) | as typescript | `tsx_scanner.go` (573) | — | mirror | 2 |
| javascript | yes (364) | `_automatic_semicolon`, `_template_chars`, `_ternary_qmark`, `html_comment`, `escape_sequence`, `regex_pattern`, `jsx_text` | `javascript_scanner.go` (638) | — | mirror | 4 |
| java | none | — | — | **yes** (`java_lexer.go`, 1,025) | mirror | 4 |
| rust | yes (403) | `string_content`, `string_close`, raw-string start/content/end, `float_literal`, block-comment content and doc markers, `_line_doc_content` | `rust_scanner.go` (532) | — | mirror | 2 |
| swift | yes (1,112) | `multiline_comment`, raw-string parts, implicit/explicit semicolons, custom operators, `#if` directives, keywords, … | `swift_scanner.go` (1,213) | — | **own** (grammargen) | 8 |

So **all 10 research grammars** depend on hand-written code somewhere:
- 8 on an external scanner, which gotreesitter re-implements in Go;
- 2 on a hand-written Go lexer that replaces the generated one (Go, Java);
- 2 on a grammar gotreesitter owns rather than mirrors (Go, Swift).

**Documentation claims, not verified here.** gotreesitter documents C-parity
"boards" (`docs/c-parity-boards.md`, counts dated 2026-09-08) run by a
`cgo_harness/` against the C runtime:
- recovery: 78 malformed cases, 36 agreeing on the default route (go 6/10,
  java 5/8, javascript 4/17, python 4/14, rust 5/10, typescript 3/6);
- query semantics: 103 cases, 101 agreeing.

That harness is not shipped in the module, and this task did not run it.
Its README claims "error-free trees on smoke samples" for all 206 grammars.

## What this task measured

The differential (`results/ts_differential.md`) parses every corpus file
and every git-visible file of the six read-only repositories with
gotreesitter and with the C reference. Both trees go through the same
mapping:

| grammar | files | trees differ | mapped Result differs | uncertain: gotreesitter only / C only | cause indicators for the Result differences (HEURISTIC) |
|---|---|---|---|---|---|
| bash | 1,689 | 459 | 74 | 37 / 14 | scanner 55, recovery 3, table-or-runtime 1, unknown 15 |
| python | 1,895 | 14 | 0 | 0 / 0 | — |
| go | 324 | 6 | 1 | 0 / 0 | recovery 1 |
| kotlin | 2,039 | 573 | 382 | 370 / 2 | table-or-runtime 136, recovery 105, scanner 11, unknown 130 |
| typescript | 7 | 0 | 0 | 0 / 0 | — |
| tsx | 1 | 0 | 0 | 0 / 0 | — |
| javascript | 6 | 1 | 0 | 0 / 0 | — |
| java | 25 | 1 | 0 | 0 / 0 | — |
| rust | 9 | 2 | 1 | 0 / 0 | unknown 1 |
| swift | 12 | 4 | 1 | 0 / 0 | unknown 1 |

tswasm vs tscgo is identical on every file of every grammar: the same C
runtime and the same C scanners compiled to wasm give the same trees.

How to read the cause indicators: they are heuristics, never attributions.
- **scanner:** an external token sits at the first divergent leaf.
- **recovery:** an ERROR or MISSING node sits at the first divergent leaf.
- **table-or-runtime:** the leaf ranges are identical but the trees differ.
  That fits either a table difference or a runtime defect and does not
  choose between them.

Kotlin is a mirror grammar, so gotreesitter's tables come from the same
`parser.c`. A difference there therefore cannot be blamed on owned tables.
It still does not tell runtime and scanner apart (`findings_t1954_2.md`).

The coverage outside bash, Python, Go and Kotlin is the corpus plus a
handful of real files: 25 Java, 12 Swift, 7 JS and no Rust or TS in the six
repositories. Agreement there is thin evidence.

## Before bumping a grammar or gotreesitter

The pinning model and the conformance gate are in `results/ts_grammars.md`.
For scanner-backed grammars, the gate's differential row for that grammar
is the check that a Go-port change has not moved a comment or string
boundary.
