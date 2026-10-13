# Matrix: textmate

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Safety columns (must be 0): FP-writable, Docstring-write, Silent-uncertain, Record-corruption. Recall/cost: Missed-writable, Missed-comment (a plain comment line not classed Comment), Read-mismatch, Over-refusal, Placement. Fidelity and Behaviour count applied edits that changed other bytes / program behaviour. Definitions: the t1954 shared design, *Metrics*.

## Summary by language

| lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | 67 | 66 | 12 | 0 | 0 (+8 n/a: no error reporting) | 0 | 2 | 6 | 17 | 0 | 1 | 0 | 0 | 55 pass / 11 fail | 0 / 0 / 25 / 3 |
| python | 64 | 62 | 4 | 0 | 0 (+3 n/a: no error reporting) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 57 pass / 5 fail | 0 / 0 / 40 / 7 |
| go | 21 | 21 | 0 | 0 | 0 (+3 n/a: no error reporting) | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 20 pass / 1 fail | 0 / 0 / 12 / 0 |
| kotlin | 26 | 26 | 8 | 0 | 0 (+3 n/a: no error reporting) | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 26 pass / 0 fail | 0 / 0 / 13 / 0 |
| typescript | 19 | 19 | 0 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 18 pass / 1 fail | 0 / 0 / 19 / 1 |
| java | 11 | 11 | 2 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 11 pass / 0 fail | 0 / 0 / 8 / 0 |
| rust | 10 | 10 | 0 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 0 / 0 / 8 / 0 |
| swift | 11 | 11 | 0 | 0 | 0 (+2 n/a: no error reporting) | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 10 pass / 1 fail | 0 / 0 / 7 / 0 |

## Per case

| lang | case | status | FP-W | DS-W | SIL-U | REC-C | MISS-W | MISS-C | READ-M | OVER-R | PLACE | FID | BEH | range | ops a/r/u/nm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | bash_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | bom_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/1/0 |
| bash | case_patterns.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | crlf.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | crlf_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/1 |
| bash | edits_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/5/0 |
| bash | edits_uncertain.sh | ok | 0 | 0 | n/a | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 3:5: unclosed here-document `EOF`) | 0/0/1/1 |
| bash | embedded.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | exec_mode_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | fresh_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | heredoc_in_arith.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | heredoc_in_backtick_subst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | heredoc_matrix.sh | ok | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/1/1 |
| bash | latin1_edit.sh | unsupported:UTF-8-input | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_command.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_arith_or_subshell_across_lines.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:10: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_arith_shift.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_backtick_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_case_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:13: not a valid arithmetic operator: `"`) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:11: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_comment_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_continuation_line_is_code.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_delayed_by_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_delayed_by_spanning_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_dollar_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_double_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_double_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:7: not a valid arithmetic operator: `x`) | 0/0/0/0 |
| bash | lex_escaped_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_here_string.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_ansi_c_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_body_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_body_escaped_backslash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_double_quoted.sh | ok | 0 | 0 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\"F`) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_quoted_delimiter.sh | ok | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\x4fF`) | 0/0/0/0 |
| bash | lex_heredoc_in_backticks.sh | ok | 0 | 0 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_locale_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_partly_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_quoted_no_joining.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_strip_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_strip_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_in_quotes.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_literal_brace.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_literal_braces.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_nested.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_unterminated.sh | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:6: reached EOF without matching `${` with `}`) | 0/0/0/0 |
| bash | lex_param_hash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_plain.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_single_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_two_heredocs.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_unterminated_heredoc.sh | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `EOF`) | 0/0/0/0 |
| bash | lex_unterminated_quote.sh | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:3: reached EOF without closing quote `"`) | 0/0/0/0 |
| bash | lookalikes.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | malformed_unterminated_single.sh | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:6: reached EOF without closing quote `'`) | 0/0/0/0 |
| bash | malformed_unterminated_subst.sh | ok | 2 | 0 | n/a | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:3: reached EOF without matching `$(` with `)`) | 0/0/0/0 |
| bash | nonascii.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/4/0 |
| bash | nonl_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | ordinary.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/4/0 |
| bash | placement_bash_existing.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | placement_bash_header.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | placement_bash_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | placement_bash_noshebang.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | placement_bash_unit_first.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/1/0 |
| bash | syntax_error_lexically_valid.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:1: `if` statement must end with `fi`) | 0/0/0/0 |
| go | bom.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | cgo_preamble.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | crlf.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | embedded_sql.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | fresh.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | go_members.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_anchors.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_block.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_plain.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_raw_string.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_unterminated_raw.go | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lookalikes.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | malformed_unterminated_block.go | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | malformed_unterminated_string.go | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs goscanner: 1 differing comment ranges) | 0/0/0/0 |
| go | nonascii.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/3/0 |
| go | ordinary.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/4/0 |
| go | placement_go_buildtag.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | placement_go_pkgdoc.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | runes_and_strings.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | struct_tags.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | syntax_error_lexically_valid.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| java | CharsAndStrings.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Crlf.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| java | EmbeddedSql.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Fresh.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| java | MalformedComment.java | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | MalformedTextBlock.java | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Nested.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | NonAscii.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/3/0 |
| java | Ordinary.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/3/0 |
| java | TextBlocks.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | UnicodeEscape.java | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | backtick_names.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | char_and_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | crlf.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | embedded_json.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | fresh_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | kotlin_members.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_anchors.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_block_nested.kt | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_plain.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_raw.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_slashes_in_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_template_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_unterminated_raw.kt | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lookalikes.kt | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_block.kt | ok | 2 | 0 | n/a | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_string.kt | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nested_comments.kt | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nonascii.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/3/0 |
| kotlin | ordinary.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/3/0 |
| kotlin | placement_kotlin_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_license.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_member.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_member_existing.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_package.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | raw_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | script.kts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| python | bom_doc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/1 |
| python | crlf_doc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/1 |
| python | doc_grouping_multiline.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/1 |
| python | doc_implicit_concat.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/1 |
| python | doc_paren_closing_later.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/1 |
| python | doc_raw.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | doc_shape_00.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_01.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | doc_shape_02.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | doc_shape_03.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_04.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | doc_shape_05.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_06.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_07.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_08.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_09.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_00.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_01.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_02.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_03.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_04.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_05.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_06.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_07.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_08.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_09.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_10.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_11.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_12.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_13.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_14.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_15.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_16.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_17.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | docvalue_18.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_19.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | edits_uncertain.py | ok | 0 | 0 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/1 |
| python | embedded_sql.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | fstrings_312.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | latin1_cookie.py | unsupported:UTF-8-input | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | latin1_member.py | unsupported:UTF-8-input | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_brackets.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_continuation.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_fstring_nested.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_hash_in_string.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_raw_triple.py | ok | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | lex_string_not_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_unterminated.py | ok | 0 | 0 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lookalikes.py | ok | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | malformed_unterminated_single.py | ok | 1 | 0 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | nodoc_fresh.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | nonascii.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/4/0 |
| python | nonascii_doc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/3/0 |
| python | not_doc_bytes.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | not_doc_call.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | not_doc_fstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | ordinary.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/5/1 |
| python | placement_python_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | placement_python_nodoc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | python_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | syntax_error_lexically_valid.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | triple_strings.py | ok | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | tstring_314.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| rust | chars_and_macros.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | crlf.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| rust | embedded_sql.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | inner_attrs.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| rust | malformed_nested.rs | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | malformed_raw.rs | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nested_comments.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nonascii.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/3/0 |
| rust | ordinary.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/3/0 |
| rust | raw_strings.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | crlf.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| swift | embedded_json.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | fresh_imports.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| swift | malformed_multiline.swift | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | malformed_nested.swift | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | nested_comments.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | nonascii.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/3/0 |
| swift | ordinary.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/2/0 |
| swift | raw_strings.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | regex_literals.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | shebang.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (no native oracle) | 0/0/0/0 |
| typescript | crlf.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | embedded.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | fresh_comment_between.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | fresh_imports_only.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | fresh_noimports.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | fresh_strict_imports.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | html_comments.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | imports.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | jsx_text.jsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | jsx_text.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | malformed_unterminated_comment.js | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | malformed_unterminated_template.ts | ok | 0 | 0 | n/a | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | nonascii.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/2/0 |
| typescript | nonascii.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/3/0 |
| typescript | nonascii.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/2/0 |
| typescript | ordinary.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/4/0 |
| typescript | prologue.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:2 (vs ts-parser: 1 differing comment ranges) | 0/0/1/0 |
| typescript | regex.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | templates.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/1 |

## Notes per case

- `bash/bom_edit.sh`
  - range vs shfmt: extra [3,29) "# header after a UTF-8 BOM"
  - op 1 (annotate member= source=src/bom2.sh stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/crlf_edit.sh`
  - op 1 (annotate member= source=src/crlf2.sh stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
  - op 2 (annotate member= source=src/crlf.sh stamp=@2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
- `bash/edits_members.sh`
  - op 1 (annotate member=B source=src/shared.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:Errors
  - op 2 (annotate member=A source=src/new.sh stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (annotate member=C source=src/x.sh stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 4 (raw kind=replace line=12 member= source=src/shared.sh from=original new=# testmap:covers src/shared.sh @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
  - op 5 (stale member=A source=src/shared.sh stamp=@2026-02-02/bbbbbbbbbb from=original mutate=append:echo late) []: unsupported:Errors
- `bash/edits_uncertain.sh`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
  - read: extra line=2 member= key=covers value=src/u.sh stamp= origin=comment
  - op 1 (annotate member= source=src/u.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:Errors
  - op 2 (raw kind=replace line=2 member= source=src/u.sh new=# testmap:covers src/u.sh @2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
- `bash/exec_mode_edit.sh`
  - op 1 (annotate member= source=src/exec2.sh stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/fresh_noheader.sh`
  - op 1 (annotate member= source=src/fresh.sh stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/heredoc_matrix.sh`
  - missed-writable: line 24 classed Literal
  - range vs shfmt: missing [418,447) "# testmap:covers src/real2.sh"
  - read: missing line=24 member= key=covers value=src/real2.sh stamp= origin=comment
  - placement "file": got after 2, want 24
  - op 1 (annotate member= source=src/new.sh stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
  - op 2 (raw kind=replace line=14 member= source=src/fake3.sh new=# testmap:covers src/fake3.sh @2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
- `bash/lex_arith_shift.sh`
  - missed-comment: line 2 classed Code
  - range vs shfmt: missing [19,25) "# real"
- `bash/lex_backtick_spanning.sh`
  - policy divergence: line 2 classed Comment (a real comment the M2.2 policy never treats as an annotation line)
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `bash/lex_continuation_line_is_code.sh`
  - policy divergence: line 2 classed Comment (a real comment the M2.2 policy never treats as an annotation line)
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `bash/lex_delayed_by_continuation.sh`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [24,65) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=3 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `bash/lex_delayed_by_spanning_quote.sh`
  - missed-comment: line 6 classed Literal
  - range vs shfmt: missing [70,76) "# real"
- `bash/lex_double_subshell.sh`
  - missed-comment: line 2 classed Code
- `bash/lex_heredoc_ansi_c_delimiter.sh`
  - missed-comment: line 5 classed Literal
  - range vs shfmt: missing [64,70) "# real"
- `bash/lex_heredoc_body_continuation.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [22,63) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_heredoc_escape_in_double_quoted.sh`
  - silent-uncertain: n/a — subject cannot report errors
- `bash/lex_heredoc_escape_in_quoted_delimiter.sh`
  - missed-writable: line 3 classed Literal
  - read: missing line=3 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `bash/lex_heredoc_in_backticks.sh`
  - silent-uncertain: n/a — subject cannot report errors
- `bash/lex_heredoc_locale_delimiter.sh`
  - missed-comment: line 5 classed Literal
  - range vs shfmt: missing [64,70) "# real"
- `bash/lex_heredoc_partly_quoted.sh`
  - missed-comment: line 4 classed Literal
  - range vs shfmt: missing [58,64) "# real"
- `bash/lex_heredoc_strip_continuation.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_param_expansion_unterminated.sh`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain@1"
- `bash/lex_two_heredocs.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [56,97) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_unterminated_heredoc.sh`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain@1"
- `bash/lex_unterminated_quote.sh`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain@1"
- `bash/lookalikes.sh`
  - FP-writable: line 9 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [176,207) "# testmap:covers src/delayed.sh"
  - read: extra line=9 member= key=covers value=src/delayed.sh stamp= origin=comment
  - FP-writable: look-alike/read-only line 9 read as a comment annotation
- `bash/malformed_unterminated_single.sh`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `bash/malformed_unterminated_subst.sh`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
  - read: extra line=3 member= key=covers value=src/x.sh stamp= origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `bash/nonascii.sh`
  - op 1 (annotate member= source=src/real.sh stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member= source=src/new.sh stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (annotate member=NonAscii source=src/more.sh stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 4 (raw kind=replace line=3 member= source=src/fake.sh from=original new=# testmap:covers src/fake.sh @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `bash/nonl_edit.sh`
  - op 1 (annotate member= source=src/nonl2.sh stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/ordinary.sh`
  - op 1 (annotate member= source=src/lib/a.sh stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member= source=src/lib/b.sh stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (annotate member=Alpha source=src/lib/c.sh stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 4 (raw kind=replace line=11 member=Alpha source=src/x.sh from=original new=# testmap:covers src/x.sh) [raw]: unsupported:Errors
- `bash/placement_bash_existing.sh`
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/placement_bash_header.sh`
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/placement_bash_noheader.sh`
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/placement_bash_noshebang.sh`
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `bash/placement_bash_unit_first.sh`
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `go/bom.go`
  - op 1 (annotate member= source=src/bom2.go stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `go/crlf.go`
  - op 1 (annotate member= source=src/crlf.go stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:Errors
- `go/fresh.go`
  - placement file: unsupported:APackage
  - op 1 (annotate member= source=src/fresh.go stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `go/lex_anchors.go`
  - placement file: unsupported:APackage
- `go/lex_unterminated_raw.go`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain@2"
- `go/malformed_unterminated_block.go`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `go/malformed_unterminated_string.go`
  - silent-uncertain: n/a — subject cannot report errors
  - range vs goscanner: missing [32,58) "// testmap:covers src/x.go"
  - refusal: got "", want "uncertain"
- `go/nonascii.go`
  - op 1 (annotate member= source=internal/real.go stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=TestNonAscii source=internal/more.go stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=16 member= source=internal/fake3.go from=original new=// testmap:covers internal/fake3.go @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `go/ordinary.go`
  - op 1 (annotate member= source=internal/demo/demo.go stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=TestJoin source=internal/demo/more.go stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=17 member= source=internal/fake.go from=original new=// testmap:covers internal/fake.go @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
  - op 4 (stale member=TestJoin source=internal/demo/join.go stamp=@2026-02-02/bbbbbbbbbb from=original mutate=replace:11:// testmap:unit Renamed) []: unsupported:Errors
- `go/placement_go_buildtag.go`
  - placement file: unsupported:APackage
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `go/placement_go_pkgdoc.go`
  - placement file: unsupported:APackage
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `java/Crlf.java`
  - op 1 (annotate member= source=src/crlf2.java stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `java/Fresh.java`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/fresh.java stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `java/MalformedComment.java`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `java/MalformedTextBlock.java`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `java/NonAscii.java`
  - op 1 (annotate member= source=src/main/java/app/Real.java stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=nonAscii source=src/main/java/app/More.java stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=17 member=nonAscii source=src/fake2.java from=original new=            // testmap:covers src/fake2.java) [raw]: unsupported:Errors
- `java/Ordinary.java`
  - op 1 (annotate member= source=src/main/java/app/Lists.java stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=sizes source=src/main/java/app/More.java stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=12 member=sizes source=fake from=original new=        // testmap:covers fake) [raw]: unsupported:Errors
- `java/UnicodeEscape.java`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - read: extra line=4 member= key=covers value=src/in_textblock.java stamp= origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `kotlin/crlf.kt`
  - op 1 (annotate member= source=app/crlf2.kt stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `kotlin/fresh_imports.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=app/fresh.kt stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `kotlin/lex_anchors.kt`
  - placement file: unsupported:APackage,AImportEnd
- `kotlin/lex_block_nested.kt`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 2 read as a comment annotation
- `kotlin/lex_unterminated_raw.kt`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain@1"
- `kotlin/lookalikes.kt`
  - FP-writable: line 7 classed Comment (look-alike/read-only)
  - read: extra line=7 member= key=covers value=src/InBlock.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 7 read as a comment annotation
- `kotlin/malformed_unterminated_block.kt`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
  - read: extra line=3 member= key=covers value=app/x.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `kotlin/malformed_unterminated_string.kt`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `kotlin/nested_comments.kt`
  - FP-writable: line 9 classed Comment (look-alike/read-only)
  - read: extra line=9 member= key=covers value=app/still_outer.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 9 read as a comment annotation
- `kotlin/nonascii.kt`
  - op 1 (annotate member= source=app/src/Real.kt stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=NonAscii source=app/src/More.kt stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=9 member= source=app/fake2.kt from=original new=// testmap:covers app/fake2.kt @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `kotlin/ordinary.kt`
  - op 1 (annotate member= source=app/src/Main.kt stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=Adds source=app/src/More.kt stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=15 member=Adds source=app/fake.kt from=original new=    // testmap:covers app/fake.kt @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `kotlin/placement_kotlin_imports.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `kotlin/placement_kotlin_license.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `kotlin/placement_kotlin_member.kt`
  - op 1 (annotate member=Welcome source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `kotlin/placement_kotlin_member_existing.kt`
  - op 1 (annotate member=Welcome source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `kotlin/placement_kotlin_package.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `python/bom_doc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/bom_doc.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/crlf_doc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/crlf_doc.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (annotate member= source=src/crlf2.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/doc_grouping_multiline.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/g.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/doc_implicit_concat.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/x.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/doc_paren_closing_later.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/p.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (annotate member= source=src/comment.sh stamp=@2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
- `python/doc_raw.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/raw.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/doc_shape_00.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_01.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/doc_shape_02.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/doc_shape_03.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_04.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=a stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/doc_shape_05.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_06.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_07.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_08.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_09.py`
  - records: unsupported:DocLiterals
- `python/docvalue_00.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_01.py`
  - records: unsupported:DocLiterals
- `python/docvalue_02.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/b.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_03.py`
  - records: unsupported:DocLiterals
- `python/docvalue_04.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/c.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_05.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/d.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_06.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_07.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_08.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_09.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/e.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_10.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_11.py`
  - records: unsupported:DocLiterals
- `python/docvalue_12.py`
  - records: unsupported:DocLiterals
- `python/docvalue_13.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_14.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/�.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_15.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_16.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_17.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/docvalue_18.py`
  - records: unsupported:DocLiterals
- `python/docvalue_19.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/f.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
- `python/edits_uncertain.py`
  - silent-uncertain: n/a — subject cannot report errors
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/u.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (raw kind=replace line=1 member= source=src/u.py new=# testmap:covers src/u.py @2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
- `python/embedded_sql.py`
  - records: unsupported:DocLiterals
- `python/fstrings_312.py`
  - range vs pytokenize: missing [39,85) "# a comment inside a replacement field ("
  - records: unsupported:DocLiterals
- `python/lex_brackets.py`
  - records: unsupported:DocLiterals
- `python/lex_continuation.py`
  - policy divergence: line 2 classed Comment (a real comment the M2.2 policy never treats as an annotation line)
  - records: unsupported:DocLiterals
- `python/lex_docstring.py`
  - records: unsupported:DocLiterals
- `python/lex_fstring_nested.py`
  - records: unsupported:DocLiterals
- `python/lex_hash_in_string.py`
  - records: unsupported:DocLiterals
- `python/lex_raw_triple.py`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - range vs pytokenize: extra [10,51) "# testmap:covers x @2026-01-01/012345678"
  - records: unsupported:DocLiterals
- `python/lex_string_not_docstring.py`
  - records: unsupported:DocLiterals
- `python/lex_unterminated.py`
  - silent-uncertain: n/a — subject cannot report errors
  - records: unsupported:DocLiterals
- `python/lookalikes.py`
  - FP-writable: line 8 classed Comment (look-alike/read-only)
  - range vs pytokenize: extra [127,154) "# testmap:covers src/raw.py"
  - records: unsupported:DocLiterals
- `python/malformed_unterminated_single.py`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - silent-uncertain: n/a — subject cannot report errors
  - range vs pytokenize: extra [18,43) "# testmap:covers src/x.py"
  - records: unsupported:DocLiterals
- `python/nodoc_fresh.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/fresh.py stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:DocLiterals,Errors
- `python/nonascii.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/real.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals,Errors
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals,Errors
  - op 3 (annotate member=TestNonAscii source=src/more.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals,Errors
  - op 4 (raw kind=replace line=2 member= source=src/fake.py from=original new=# testmap:covers src/fake.py @2026-02-02/bbbbbbbbbb) [raw]: unsupported:DocLiterals,Errors
- `python/nonascii_doc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/doc_x.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (annotate member= source=src/a.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals,Errors
  - op 3 (annotate member= source=src/b.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals,Errors
- `python/not_doc_bytes.py`
  - records: unsupported:DocLiterals
- `python/not_doc_call.py`
  - records: unsupported:DocLiterals
- `python/not_doc_fstring.py`
  - records: unsupported:DocLiterals
- `python/ordinary.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/doc_src.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals,Errors
  - op 2 (raw kind=replace line=3 member= source=src/doc_src.py new=# testmap:covers src/doc_src.py @2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
  - op 3 (annotate member= source=src/a.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals,Errors
  - op 4 (annotate member=TestA source=src/a.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals,Errors
  - op 5 (annotate member=TestA source=src/b.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals,Errors
  - op 6 (raw kind=replace line=14 member=TestA source=src/fake.py from=original new=# testmap:covers src/fake.py @2026-02-02/bbbbbbbbbb) [raw]: unsupported:DocLiterals,Errors
- `python/placement_python_docstring.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:DocLiterals,Errors
- `python/placement_python_nodoc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:DocLiterals,Errors
- `python/python_docstring.py`
  - records: unsupported:DocLiterals
- `python/syntax_error_lexically_valid.py`
  - records: unsupported:DocLiterals
- `python/triple_strings.py`
  - FP-writable: line 9 classed Comment (look-alike/read-only)
  - range vs pytokenize: extra [104,129) "# testmap:covers src/z.py"
  - records: unsupported:DocLiterals
- `python/tstring_314.py`
  - records: unsupported:DocLiterals
- `rust/crlf.rs`
  - op 1 (annotate member= source=src/crlf.rs stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:Errors
- `rust/inner_attrs.rs`
  - placement file: unsupported:AImportEnd,AInnerAttrEnd
  - op 1 (annotate member= source=src/inner.rs stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `rust/malformed_nested.rs`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `rust/malformed_raw.rs`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `rust/nonascii.rs`
  - op 1 (annotate member= source=src/real.rs stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=non_ascii source=src/more.rs stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=16 member= source=src/fake2.rs from=original new=// testmap:covers src/fake2.rs @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `rust/ordinary.rs`
  - op 1 (annotate member= source=src/lib.rs stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=builds_map source=src/more.rs stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=19 member= source=src/fake.rs from=original new=// testmap:covers src/fake.rs @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `swift/crlf.swift`
  - op 1 (annotate member= source=Sources/crlf.swift stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:Errors
- `swift/fresh_imports.swift`
  - placement file: unsupported:AImportEnd
  - op 1 (annotate member= source=Sources/fresh.swift stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `swift/malformed_multiline.swift`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `swift/malformed_nested.swift`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `swift/nonascii.swift`
  - op 1 (annotate member= source=Sources/App/Real.swift stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=testNonAscii source=Sources/App/More.swift stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=14 member=testNonAscii source=Sources/fake2.swift from=original new=// testmap:covers Sources/fake2.swift @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `swift/ordinary.swift`
  - op 1 (annotate member= source=Sources/App/Main.swift stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=testAdds source=Sources/App/More.swift stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
- `swift/shebang.swift`
  - range: line comment at 0 does not start with "//"
- `typescript/crlf.ts`
  - op 1 (annotate member= source=src/crlf.ts stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:Errors
- `typescript/fresh_comment_between.tsx`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_comment_between.tsx stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `typescript/fresh_imports_only.ts`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_imports_only.ts stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `typescript/fresh_noimports.ts`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_noimports.ts stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `typescript/fresh_strict_imports.js`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_strict_imports.js stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `typescript/imports.ts`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/imports.ts stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `typescript/malformed_unterminated_comment.js`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `typescript/malformed_unterminated_template.ts`
  - silent-uncertain: n/a — subject cannot report errors
  - refusal: got "", want "uncertain"
- `typescript/nonascii.js`
  - op 1 (annotate member= source=src/real.js stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member= source=src/new.js stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
- `typescript/nonascii.ts`
  - op 1 (annotate member= source=src/real.ts stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=nonAscii source=src/more.ts stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (raw kind=replace line=13 member= source=src/fake2.ts from=original new=// testmap:covers src/fake2.ts @2026-02-02/bbbbbbbbbb) [raw]: unsupported:Errors
- `typescript/nonascii.tsx`
  - op 1 (annotate member= source=src/real.tsx stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member= source=src/new.tsx stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
- `typescript/ordinary.ts`
  - op 1 (annotate member= source=src/join.ts stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:Errors
  - op 2 (annotate member=joinsPaths source=src/more.ts stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 3 (annotate member=nope source=src/x.ts stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:Errors
  - op 4 (stale member=joinsPaths source=src/path.ts stamp=@2026-02-02/bbbbbbbbbb from=original mutate=append:joinsPaths();) []: unsupported:Errors
- `typescript/prologue.js`
  - range: line comment at 0 does not start with "//"
  - range vs ts-parser: extra [0,19) "#!/usr/bin/env node"
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/prologue.js stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:Errors
- `typescript/templates.ts`
  - op 1 (annotate member= source=src/real2.ts stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:Errors
  - op 2 (raw kind=replace line=3 member= source=src/fake1.ts new=// testmap:covers src/fake1.ts @2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
