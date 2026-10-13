# Native cross-checks of the hand oracles (t1954_1 step 3)

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Rerun: `go run ./cmd/t1954 oraclecheck` (environment: `results/environment.md`; TS oracle needs `T1954_TS_NODE_MODULES`, Kotlin `T1954_KOTLINC`, Swift `T1954_SWIFT_DOCKER`).

- **expect**: `valid` (a native tool must accept), `invalid` (malformed: must reject), `lexically-valid` (tokenizes, does not parse: the parser must reject), `fragment` (an M2.2 lexical case or docstring fragment, not necessarily a program: informational).
- **comments**: hand `comments:` lines must be native line comments starting at the line's first non-blank byte; `lookalikes:` / `readonly:` lines must not be. Comment oracles: go/scanner (Go), Python tokenize, mvdan/sh (bash), the parser-aware TS extractor (TS/JS). Java, Rust, Kotlin and Swift have validity and execution evidence only.
- **Self-test rule**: the M2.2 adversarial fixtures (`lex_*`, `lookalikes.*`, docstring cases — origin M2.2) are each comment oracle's self-test; an oracle may override a hand expectation only if it agrees on all of them for its language (summary below).

## Summary

| lang | fixtures | validity matches / checked | comment agreement (M2.2 self-test) | comment agreement (hand) | exec ok / run | native none |
|---|---|---|---|---|---|---|
| bash | 66 | 29 / 29 | 39 / 39 | 12 / 12 | 9 / 9 | 0 |
| python | 61 | 24 / 24 | 41 / 41 | 17 / 17 | 9 / 9 | 0 |
| go | 20 | 16 / 16 | 8 / 8 | 9 / 9 | 1 / 1 | 0 |
| kotlin | 25 | 19 / 19 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |
| typescript | 12 | 11 / 11 | 0 / 0 | 10 / 10 | 6 / 6 | 0 |
| java | 10 | 10 / 10 | 0 / 0 | 0 / 0 | 3 / 3 | 0 |
| rust | 9 | 9 / 9 | 0 / 0 | 0 / 0 | 6 / 6 | 0 |
| swift | 10 | 10 / 10 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |

## Per fixture

| lang | case | origin | expect | native | match | comments | exec |
|---|---|---|---|---|---|---|---|
| bash | bash_members.sh | M2.2 | valid | accept | yes | agree (shfmt, 8 comment lines) |  |
| bash | bom_edit.sh | hand | valid | accept | yes | agree (shfmt, 1 comment lines) |  |
| bash | case_patterns.sh | hand | valid | accept | yes | agree (shfmt, 1 comment lines) | ok |
| bash | crlf.sh | M2.2 | valid | accept | yes | agree (shfmt, 1 comment lines) |  |
| bash | crlf_edit.sh | hand | valid | accept | yes | agree (shfmt, 1 comment lines) |  |
| bash | edits_members.sh | hand | valid | accept | yes | agree (shfmt, 6 comment lines) | ok |
| bash | edits_uncertain.sh | hand | invalid | reject:warning: here-document at line 3 delimited by end-of-file (wanted `EOF') | yes | n/a (malformed) |  |
| bash | embedded.sh | hand | valid | accept | yes | agree (shfmt, 2 comment lines) | ok |
| bash | exec_mode_edit.sh | hand | valid | accept | yes | agree (shfmt, 1 comment lines) | ok |
| bash | fresh_noheader.sh | hand | valid | accept | yes | agree (shfmt, 0 comment lines) | ok |
| bash | heredoc_in_arith.sh | hand | valid | accept | yes | agree (shfmt, 1 comment lines) | ok |
| bash | heredoc_in_backtick_subst.sh | hand | valid | accept | yes | agree (shfmt, 1 comment lines) | ok |
| bash | heredoc_matrix.sh | hand | valid | accept | yes | agree (shfmt, 2 comment lines) | ok |
| bash | latin1_edit.sh | hand | valid | accept | yes | none (shfmt: shfmt cannot parse: 2:6: invalid UTF-8 encoding) |  |
| bash | lex_arith_command.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_arith_or_subshell_across_lines.sh | M2.2 | fragment | accept | n/a | none (shfmt: shfmt cannot parse: 1:10: not a valid arithmetic operator: `a`) |  |
| bash | lex_arith_shift.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_backtick_spanning.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines; 1 explained) |  |
| bash | lex_case_in_cmdsubst.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_cmdsubst_of_subshell.sh | M2.2 | fragment | accept | n/a | none (shfmt: shfmt cannot parse: 1:13: not a valid arithmetic operator: `"`) |  |
| bash | lex_cmdsubst_of_subshell_quoted.sh | M2.2 | fragment | accept | n/a | none (shfmt: shfmt cannot parse: 1:11: not a valid arithmetic operator: `a`) |  |
| bash | lex_comment_quote.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_continuation_line_is_code.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines; 1 explained) |  |
| bash | lex_delayed_by_continuation.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_delayed_by_spanning_quote.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_dollar_quote_spanning.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_double_quote_spanning.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_double_subshell.sh | M2.2 | fragment | accept | n/a | none (shfmt: shfmt cannot parse: 1:7: not a valid arithmetic operator: `x`) |  |
| bash | lex_escaped_quote.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_here_string.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_ansi_c_delimiter.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_body_continuation.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_body_escaped_backslash.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_escape_in_double_quoted.sh | M2.2 | invalid | reject:warning: here-document at line 1 delimited by end-of-file (wanted `E"F') | yes | n/a (malformed) |  |
| bash | lex_heredoc_escape_in_quoted_delimiter.sh | M2.2 | fragment | accept | n/a | none (shfmt: shfmt cannot parse: 1:5: unclosed here-document `E\x4fF`) |  |
| bash | lex_heredoc_in_backticks.sh | M2.2 | invalid | accept | explained | n/a (malformed) |  |
| bash | lex_heredoc_in_cmdsubst.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_locale_delimiter.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_partly_quoted.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_quoted_no_joining.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_heredoc_strip_continuation.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines; 1 explained) |  |
| bash | lex_heredoc_strip_quoted.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_param_expansion_in_quotes.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_param_expansion_literal_brace.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_param_expansion_literal_braces.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_param_expansion_nested.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_param_expansion_spanning.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_param_expansion_unterminated.sh | M2.2 | invalid | reject:lex_param_expansion_unterminated.sh: line 1: unexpected EOF while looking for matching `}' | yes | n/a (malformed) |  |
| bash | lex_param_hash.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_plain.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 2 comment lines) |  |
| bash | lex_single_quote_spanning.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_two_heredocs.sh | M2.2 | fragment | accept | n/a | agree (shfmt, 1 comment lines) |  |
| bash | lex_unterminated_heredoc.sh | M2.2 | invalid | reject:warning: here-document at line 1 delimited by end-of-file (wanted `EOF') | yes | n/a (malformed) |  |
| bash | lex_unterminated_quote.sh | M2.2 | invalid | reject:lex_unterminated_quote.sh: line 1: unexpected EOF while looking for matching `"' | yes | n/a (malformed) |  |
| bash | lookalikes.sh | M2.2 | valid | accept | yes | agree (shfmt, 2 comment lines) |  |
| bash | malformed_unterminated_single.sh | hand | invalid | reject:malformed_unterminated_single.sh: line 2: unexpected EOF while looking for matching `'' | yes | n/a (malformed) |  |
| bash | malformed_unterminated_subst.sh | hand | invalid | reject:malformed_unterminated_subst.sh: line 4: unexpected EOF while looking for matching `)' | yes | n/a (malformed) |  |
| bash | nonl_edit.sh | hand | valid | accept | yes | agree (shfmt, 2 comment lines) |  |
| bash | ordinary.sh | hand | valid | accept | yes | agree (shfmt, 7 comment lines) | ok |
| bash | placement_bash_existing.sh | M2.2 | valid | accept | yes | agree (shfmt, 1 comment lines) |  |
| bash | placement_bash_header.sh | M2.2 | valid | accept | yes | agree (shfmt, 0 comment lines) |  |
| bash | placement_bash_noheader.sh | M2.2 | valid | accept | yes | agree (shfmt, 0 comment lines) |  |
| bash | placement_bash_noshebang.sh | M2.2 | valid | accept | yes | agree (shfmt, 0 comment lines) |  |
| bash | placement_bash_unit_first.sh | M2.2 | valid | accept | yes | agree (shfmt, 1 comment lines) |  |
| bash | syntax_error_lexically_valid.sh | hand | lexically-valid | reject:syntax_error_lexically_valid.sh: line 5: syntax error: unexpected end of file from `if' command on line 2 | yes | none (shfmt: shfmt cannot parse: 2:1: `if` statement must end with `fi`) |  |
| go | bom.go | hand | valid | accept | yes | agree (goscanner, 1 comment lines) |  |
| go | cgo_preamble.go | hand | valid | accept | yes | agree (goscanner, 1 comment lines) |  |
| go | crlf.go | hand | valid | accept | yes | agree (goscanner, 1 comment lines) |  |
| go | embedded_sql.go | hand | valid | accept | yes | agree (goscanner, 1 comment lines) |  |
| go | fresh.go | hand | valid | accept | yes | agree (goscanner, 2 comment lines) |  |
| go | go_members.go | M2.2 | valid | accept | yes | agree (goscanner, 5 comment lines) |  |
| go | lex_anchors.go | M2.2 | fragment | accept | n/a | agree (goscanner, 2 comment lines) |  |
| go | lex_block.go | M2.2 | fragment | accept | n/a | agree (goscanner, 1 comment lines) |  |
| go | lex_plain.go | M2.2 | fragment | accept | n/a | agree (goscanner, 1 comment lines) |  |
| go | lex_raw_string.go | M2.2 | fragment | accept | n/a | agree (goscanner, 1 comment lines) |  |
| go | lex_unterminated_raw.go | M2.2 | invalid | reject:lex_unterminated_raw.go:2:9: raw string literal not terminated | yes | n/a (malformed) |  |
| go | lookalikes.go | M2.2 | valid | accept | yes | agree (goscanner, 2 comment lines) |  |
| go | malformed_unterminated_block.go | hand | invalid | reject:malformed_unterminated_block.go:2:1: comment not terminated | yes | n/a (malformed) |  |
| go | malformed_unterminated_string.go | hand | invalid | reject:malformed_unterminated_string.go:2:9: string literal not terminated | yes | n/a (malformed) |  |
| go | ordinary.go | hand | valid | accept | yes | agree (goscanner, 4 comment lines) | ok |
| go | placement_go_buildtag.go | M2.2 | valid | accept | yes | agree (goscanner, 0 comment lines) |  |
| go | placement_go_pkgdoc.go | M2.2 | valid | accept | yes | agree (goscanner, 0 comment lines) |  |
| go | runes_and_strings.go | hand | valid | accept | yes | agree (goscanner, 2 comment lines) |  |
| go | struct_tags.go | hand | valid | accept | yes | agree (goscanner, 1 comment lines) |  |
| go | syntax_error_lexically_valid.go | hand | lexically-valid | reject:syntax_error_lexically_valid.go:3:6: expected 'IDENT', found '{' (and 3 more errors) | yes | agree (goscanner, 1 comment lines) |  |
| java | CharsAndStrings.java | hand | valid | accept | yes | n/a (no comment oracle) |  |
| java | Crlf.java | hand | valid | accept | yes | n/a (no comment oracle) |  |
| java | EmbeddedSql.java | hand | valid | accept | yes | n/a (no comment oracle) |  |
| java | Fresh.java | hand | valid | accept | yes | n/a (no comment oracle) |  |
| java | MalformedComment.java | hand | invalid | reject:MalformedComment.java:2: error: unclosed comment | yes | n/a (malformed) |  |
| java | MalformedTextBlock.java | hand | invalid | reject:MalformedTextBlock.java:2: error: unclosed text block | yes | n/a (malformed) |  |
| java | Nested.java | hand | valid | accept | yes | n/a (no comment oracle) |  |
| java | Ordinary.java | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| java | TextBlocks.java | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| java | UnicodeEscape.java | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| kotlin | backtick_names.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | char_and_templates.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | crlf.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | embedded_json.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | fresh_imports.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | kotlin_members.kt | M2.2 | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | lex_anchors.kt | M2.2 | fragment | reject:lex_anchors.kt:3:8: error: unresolved reference 'b'. | n/a | n/a (no comment oracle) |  |
| kotlin | lex_block_nested.kt | M2.2 | fragment | accept | n/a | n/a (no comment oracle) |  |
| kotlin | lex_plain.kt | M2.2 | fragment | accept | n/a | n/a (no comment oracle) |  |
| kotlin | lex_raw.kt | M2.2 | fragment | accept | n/a | n/a (no comment oracle) |  |
| kotlin | lex_slashes_in_string.kt | M2.2 | fragment | accept | n/a | n/a (no comment oracle) |  |
| kotlin | lex_template_string.kt | M2.2 | fragment | accept | n/a | n/a (no comment oracle) |  |
| kotlin | lex_unterminated_raw.kt | M2.2 | invalid | reject:lex_unterminated_raw.kt:3:1: error: syntax error: Expecting '"'. | yes | n/a (malformed) |  |
| kotlin | lookalikes.kt | M2.2 | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | malformed_unterminated_block.kt | hand | invalid | reject:malformed_unterminated_block.kt:4:1: error: syntax error: Unclosed comment. | yes | n/a (malformed) |  |
| kotlin | malformed_unterminated_string.kt | hand | invalid | reject:malformed_unterminated_string.kt:1:22: error: syntax error: Expecting '"'. | yes | n/a (malformed) |  |
| kotlin | nested_comments.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | ordinary.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | placement_kotlin_imports.kt | M2.2 | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | placement_kotlin_license.kt | M2.2 | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | placement_kotlin_member.kt | M2.2 | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | placement_kotlin_member_existing.kt | M2.2 | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | placement_kotlin_package.kt | M2.2 | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | raw_templates.kt | hand | valid | accept | yes | n/a (no comment oracle) |  |
| kotlin | script.kts | hand | valid | accept | yes | n/a (no comment oracle) |  |
| python | bom_doc.py | hand | valid | accept | yes | agree (pytokenize, 0 comment lines) | ok |
| python | crlf_doc.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) | ok |
| python | doc_grouping_multiline.py | hand | valid | accept | yes | agree (pytokenize, 0 comment lines) |  |
| python | doc_implicit_concat.py | hand | valid | accept | yes | agree (pytokenize, 0 comment lines) |  |
| python | doc_paren_closing_later.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) |  |
| python | doc_raw.py | hand | valid | accept | yes | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_00.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_01.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_02.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_03.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_04.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_05.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_06.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_07.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_08.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | doc_shape_09.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_00.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_01.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_02.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_03.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_04.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_05.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_06.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_07.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_08.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_09.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 1 comment lines) |  |
| python | docvalue_10.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_11.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_12.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_13.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_14.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_15.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_16.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_17.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_18.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | docvalue_19.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 0 comment lines) |  |
| python | edits_uncertain.py | hand | invalid | reject:tokenize: EOF in multi-line string | yes | n/a (malformed) |  |
| python | embedded_sql.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) | ok |
| python | fstrings_312.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) | ok |
| python | latin1_cookie.py | hand | valid | accept | yes | agree (pytokenize, 3 comment lines) | ok |
| python | lex_brackets.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 1 comment lines) |  |
| python | lex_continuation.py | M2.2 | fragment | reject:ast: invalid syntax | n/a | agree (pytokenize, 0 comment lines; 1 explained) |  |
| python | lex_docstring.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 1 comment lines) |  |
| python | lex_fstring_nested.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 1 comment lines) |  |
| python | lex_hash_in_string.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 1 comment lines) |  |
| python | lex_raw_triple.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 1 comment lines) |  |
| python | lex_string_not_docstring.py | M2.2 | fragment | accept | n/a | agree (pytokenize, 1 comment lines) |  |
| python | lex_unterminated.py | M2.2 | invalid | reject:tokenize: EOF in multi-line string | yes | n/a (malformed) |  |
| python | lookalikes.py | M2.2 | valid | accept | yes | agree (pytokenize, 2 comment lines) |  |
| python | malformed_unterminated_single.py | hand | invalid | reject:tokenize: unterminated string literal (detected at line 1) | yes | n/a (malformed) |  |
| python | nodoc_fresh.py | hand | valid | accept | yes | agree (pytokenize, 0 comment lines) | ok |
| python | not_doc_bytes.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) |  |
| python | not_doc_call.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) |  |
| python | not_doc_fstring.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) |  |
| python | ordinary.py | hand | valid | accept | yes | agree (pytokenize, 4 comment lines) | ok |
| python | placement_python_docstring.py | M2.2 | valid | accept | yes | agree (pytokenize, 0 comment lines) |  |
| python | placement_python_nodoc.py | M2.2 | valid | accept | yes | agree (pytokenize, 0 comment lines) |  |
| python | python_docstring.py | M2.2 | valid | accept | yes | agree (pytokenize, 4 comment lines) |  |
| python | syntax_error_lexically_valid.py | hand | lexically-valid | reject:tokenize: unexpected EOF in multi-line statement | yes | agree (pytokenize, 1 comment lines) |  |
| python | triple_strings.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) | ok |
| python | tstring_314.py | hand | valid | accept | yes | agree (pytokenize, 1 comment lines) | ok |
| rust | chars_and_macros.rs | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| rust | crlf.rs | hand | valid | accept | yes | n/a (no comment oracle) |  |
| rust | embedded_sql.rs | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| rust | inner_attrs.rs | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| rust | malformed_nested.rs | hand | invalid | reject:error[E0758]: unterminated block comment | yes | n/a (malformed) |  |
| rust | malformed_raw.rs | hand | invalid | reject:error[E0748]: unterminated raw string | yes | n/a (malformed) |  |
| rust | nested_comments.rs | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| rust | ordinary.rs | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| rust | raw_strings.rs | hand | valid | accept | yes | n/a (no comment oracle) | ok |
| swift | crlf.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| swift | embedded_json.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| swift | fresh_imports.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| swift | malformed_multiline.swift | hand | invalid | reject:/w/malformed_multiline.swift:1:9: error: unterminated string literal | yes | n/a (malformed) |  |
| swift | malformed_nested.swift | hand | invalid | reject:/w/malformed_nested.swift:2:34: error: unterminated '/*' comment | yes | n/a (malformed) |  |
| swift | nested_comments.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| swift | ordinary.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| swift | raw_strings.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| swift | regex_literals.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| swift | shebang.swift | hand | valid | accept | yes | n/a (no comment oracle) |  |
| typescript | crlf.ts | hand | valid | accept | yes | agree (ts-parser, 1 comment lines) |  |
| typescript | embedded.ts | hand | valid | accept | yes | agree (ts-parser, 1 comment lines) | ok |
| typescript | html_comments.js | hand | valid | reject:Expression expected. | explained | agree (ts-parser, 1 comment lines) | ok |
| typescript | imports.ts | hand | valid | accept | yes | agree (ts-parser, 1 comment lines) |  |
| typescript | jsx_text.jsx | hand | valid | accept | yes | agree (ts-parser, 1 comment lines) |  |
| typescript | jsx_text.tsx | hand | valid | accept | yes | agree (ts-parser, 1 comment lines) |  |
| typescript | malformed_unterminated_comment.js | hand | invalid | reject:'*/' expected. | yes | n/a (malformed) |  |
| typescript | malformed_unterminated_template.ts | hand | invalid | reject:Unterminated template literal. | yes | n/a (malformed) |  |
| typescript | ordinary.ts | hand | valid | accept | yes | agree (ts-parser, 3 comment lines) | ok |
| typescript | prologue.js | hand | valid | accept | yes | agree (ts-parser, 0 comment lines) | ok |
| typescript | regex.ts | hand | valid | accept | yes | agree (ts-parser, 2 comment lines) | ok |
| typescript | templates.ts | hand | valid | accept | yes | agree (ts-parser, 3 comment lines) | ok |

## Disagreements

- `bash/lex_backtick_spanning.sh`: native accept; exec 
  - 1 line(s) differ from shfmt as explained in the fixture notes
- `bash/lex_continuation_line_is_code.sh`: native accept; exec 
  - 1 line(s) differ from shfmt as explained in the fixture notes
- `bash/lex_heredoc_in_backticks.sh`: native accept; exec 
  - validity: explained in the fixture notes
- `bash/lex_heredoc_strip_continuation.sh`: native accept; exec 
  - 1 line(s) differ from shfmt as explained in the fixture notes
- `python/lex_continuation.py`: native reject:ast: invalid syntax; exec 
  - 1 line(s) differ from pytokenize as explained in the fixture notes
- `typescript/html_comments.js`: native reject:Expression expected.; exec ok
  - validity: explained in the fixture notes
