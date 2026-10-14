# LSP experiment: do language servers expose comment locations? (t1954_3)

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Rerun: `go run ./cmd/t1954 lsp` with `T1954_GOPLS`, `T1954_LSP_NODE_MODULES` (pyright, typescript-language-server, typescript) and `T1954_KOTLIN_LSP` set (README). Each server runs in its own scratch project, through a protocol-correct lifecycle (initialize with capability negotiation → initialized → server requests answered → readiness → controls → per-fixture requests → shutdown/exit). **Only `measured` outcomes are evidence about comment support**; `inconclusive` (a failed control, a timeout or an error), `setup failed` and `not measured` say nothing about it. The two features are scored independently, each on its own control.

Comment lines are lines whose first non-blank byte starts a comment token beginning with the language's leader — the same definition the seam's line classes use — compared with each fixture's hand oracle (`comments:`). FP-shaped = a look-alike line (testmap-shaped data) reported as a comment line, or inside a comment fold. Exact = the server's line-comment byte ranges equal the native oracle's (goscanner / pytokenize / ts-parser; none for Kotlin).

| server | lang | status | runtime | install size | position encoding | initialize | readiness | feature | advertised | control | outcome | fixtures | with ≥1 comment | comment-line agreement | missed lines | FP-shaped lines | exact vs native | first response |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gopls | go | measured | native binary (Go) | 43.2 MB | utf-16 | 113 ms | 2208 ms | semanticTokens/full | true | pass | measured | 22 | 20 | 13 / 22 | 1 | 5 | 14 / 22 | 0.8 ms |
| gopls | go | measured | native binary (Go) | 43.2 MB | utf-16 | 113 ms | 2208 ms | foldingRange | true | pass | measured | 22 | 7 | n/a (folds cover blocks, not single lines) | n/a | 4 | n/a | — |
| pyright | python | measured | Node.js | 19.5 MB | utf-16 | 135 ms | 2171 ms | semanticTokens/full | false | n/a | not advertised | 0 | 0 | — | — | 0 | — | — |
| pyright | python | measured | Node.js | 19.5 MB | utf-16 | 135 ms | 2171 ms | foldingRange | false | n/a | not advertised | 0 | 0 | — | — | 0 | — | — |
| typescript-language-server | typescript | measured | Node.js + typescript | 2.4 MB | utf-16 | 67 ms | 2279 ms | semanticTokens/full | true | pass | measured | 19 | 0 | 5 / 19 | 25 | 0 | 5 / 19 | 5.6 ms |
| typescript-language-server | typescript | measured | Node.js + typescript | 2.4 MB | utf-16 | 67 ms | 2279 ms | foldingRange | true | pass | measured | 19 | 2 | n/a (folds cover blocks, not single lines) | n/a | 0 | n/a | — |
| kotlin-lsp | kotlin | measured | JVM (bundled JBR) | 1199.7 MB | utf-16 | 2386 ms | 2768 ms | semanticTokens/full | true | pass | measured | 31 | 0 | 8 / 31 | 40 | 0 | 0 / 0 | 30.7 ms |
| kotlin-lsp | kotlin | measured | JVM (bundled JBR) | 1199.7 MB | utf-16 | 2386 ms | 2768 ms | foldingRange | true | pass | measured | 31 | 5 | n/a (folds cover blocks, not single lines) | n/a | 6 | n/a | — |

## Per server

- **gopls** (go): measured.
  - control file (a 4-line block comment, then the known function): semanticTokens: 4 comment token(s) for the control's block comment; foldingRange: 1 comment fold(s) for it
  - semantic token legend: namespace, type, typeParameter, parameter, property, variable, function, method, macro, keyword, comment, string, number, operator, label (has `comment`: true)
  - malformed fixtures sent: 3; files with published diagnostics (asynchronous `publishDiagnostics` only — no request returns certainty with the tokens): 5
  - semanticTokens go/cgo_preamble.go: FP-shaped (look-alike) lines [5], other extra lines [], missed lines []
  - semanticTokens go/go_members.go: FP-shaped (look-alike) lines [], other extra lines [1 3], missed lines []
  - semanticTokens go/lex_block.go: FP-shaped (look-alike) lines [3], other extra lines [], missed lines []
  - semanticTokens go/lex_bom_comment.go: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1]
  - semanticTokens go/lookalikes.go: FP-shaped (look-alike) lines [9], other extra lines [], missed lines []
  - semanticTokens go/malformed_unterminated_string.go: FP-shaped (look-alike) lines [3], other extra lines [], missed lines []
  - semanticTokens go/placement_go_buildtag.go: FP-shaped (look-alike) lines [], other extra lines [1], missed lines []
  - semanticTokens go/placement_go_pkgdoc.go: FP-shaped (look-alike) lines [], other extra lines [1], missed lines []
  - semanticTokens go/runes_and_strings.go: FP-shaped (look-alike) lines [10], other extra lines [], missed lines []
  - foldingRange go/cgo_preamble.go: comment fold lines 3-6 covers look-alike lines [5]
  - foldingRange go/lex_block.go: comment fold lines 2-5 covers look-alike lines [3]
  - foldingRange go/lookalikes.go: comment fold lines 8-11 covers look-alike lines [9]
  - foldingRange go/runes_and_strings.go: comment fold lines 9-12 covers look-alike lines [10]
- **pyright** (python): measured.
  - malformed fixtures sent: 3; files with published diagnostics (asynchronous `publishDiagnostics` only — no request returns certainty with the tokens): 0
- **typescript-language-server** (typescript): measured.
  - control file (a 4-line block comment, then the known function): semanticTokens: 0 comment token(s) for the control's block comment; foldingRange: 1 comment fold(s) for it
  - semantic token legend: class, enum, interface, namespace, typeParameter, type, parameter, variable, enumMember, property, function, member (has `comment`: false)
  - malformed fixtures sent: 2; files with published diagnostics (asynchronous `publishDiagnostics` only — no request returns certainty with the tokens): 0
  - semanticTokens typescript/crlf.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [2]
  - semanticTokens typescript/embedded.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [13]
  - semanticTokens typescript/fresh_comment_between.tsx: FP-shaped (look-alike) lines [], other extra lines [], missed lines [3]
  - semanticTokens typescript/fresh_noimports.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1]
  - semanticTokens typescript/html_comments.js: FP-shaped (look-alike) lines [], other extra lines [], missed lines [4]
  - semanticTokens typescript/imports.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1]
  - semanticTokens typescript/jsx_text.jsx: FP-shaped (look-alike) lines [], other extra lines [], missed lines [7]
  - semanticTokens typescript/jsx_text.tsx: FP-shaped (look-alike) lines [], other extra lines [], missed lines [10]
  - semanticTokens typescript/nonascii.js: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1 4]
  - semanticTokens typescript/nonascii.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1 4 6 7 8]
  - semanticTokens typescript/nonascii.tsx: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1 4]
  - semanticTokens typescript/ordinary.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [4 6 7]
  - semanticTokens typescript/regex.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [5 7]
  - semanticTokens typescript/templates.ts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [5 11 15]
- **kotlin-lsp** (kotlin): measured.
  - control file (a 4-line block comment, then the known function): semanticTokens: 0 comment token(s) for the control's block comment; foldingRange: 1 comment fold(s) for it
  - semantic token legend: namespace, class, enum, interface, struct, typeParameter, type, parameter, variable, property, enumMember, event, function, method, macro, keyword, modifier, comment, string, number, regexp, operator, decorator (has `comment`: true)
  - malformed fixtures sent: 3; files with published diagnostics (asynchronous `publishDiagnostics` only — no request returns certainty with the tokens): 0
  - semanticTokens kotlin/backtick_names.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [3 5]
  - semanticTokens kotlin/char_and_templates.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [4]
  - semanticTokens kotlin/crlf.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [3]
  - semanticTokens kotlin/embedded_json.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [8]
  - semanticTokens kotlin/kotlin_members.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [6 7 9 10 11 14 15 16]
  - semanticTokens kotlin/lex_block_nested.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [4]
  - semanticTokens kotlin/lex_bom_comment.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1]
  - semanticTokens kotlin/lex_plain.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [3]
  - semanticTokens kotlin/lex_raw.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [5]
  - semanticTokens kotlin/lex_slashes_in_string.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [2]
  - semanticTokens kotlin/lex_template_string.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [2]
  - semanticTokens kotlin/lookalikes.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1 9]
  - semanticTokens kotlin/multidollar_comment_desync.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [3]
  - semanticTokens kotlin/multidollar_interpolation.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [6]
  - semanticTokens kotlin/multidollar_literal_brace.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [7]
  - semanticTokens kotlin/multidollar_quote_boundary.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [9]
  - semanticTokens kotlin/nested_comments.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [11]
  - semanticTokens kotlin/nonascii.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [1 6 12 14 15]
  - semanticTokens kotlin/ordinary.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [8 9 11 12]
  - semanticTokens kotlin/placement_kotlin_member.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [2]
  - semanticTokens kotlin/placement_kotlin_member_existing.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [2 3]
  - semanticTokens kotlin/raw_templates.kt: FP-shaped (look-alike) lines [], other extra lines [], missed lines [9]
  - semanticTokens kotlin/script.kts: FP-shaped (look-alike) lines [], other extra lines [], missed lines [2]
  - foldingRange kotlin/lex_block_nested.kt: comment fold lines 1-3 covers look-alike lines [2]
  - foldingRange kotlin/lookalikes.kt: comment fold lines 6-8 covers look-alike lines [7]
  - foldingRange kotlin/malformed_unterminated_block.kt: comment fold lines 2-4 covers look-alike lines [3]
  - foldingRange kotlin/nested_comments.kt: comment fold lines 1-4 covers look-alike lines [3]
  - foldingRange kotlin/nested_comments.kt: comment fold lines 6-10 covers look-alike lines [7 9]
