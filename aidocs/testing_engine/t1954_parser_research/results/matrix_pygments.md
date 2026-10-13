# Matrix: pygments

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Safety columns (must be 0): FP-writable, Docstring-write, Silent-uncertain, Record-corruption. Recall/cost: Missed-writable, Missed-comment (a plain comment line not classed Comment), Read-mismatch, Over-refusal, Placement. Fidelity and Behaviour count applied edits that changed other bytes / program behaviour. Definitions: the t1954 shared design, *Metrics*.

## Summary by language

| lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | 67 | 66 | 22 | 0 | 8 | 3 | 0 | 2 | 19 | 0 | 0 | 0 | 0 | 56 pass / 10 fail | 21 / 6 / 0 / 0 |
| python | 64 | 64 | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 62 pass / 2 fail | 0 / 0 / 43 / 7 |
| go | 21 | 21 | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 19 pass / 2 fail | 6 / 3 / 3 / 0 |
| kotlin | 26 | 26 | 8 | 0 | 3 | 0 | 0 | 1 | 10 | 3 | 0 | 0 | 0 | 25 pass / 1 fail | 7 / 2 / 4 / 0 |
| typescript | 19 | 19 | 2 | 0 | 1 | 0 | 0 | 0 | 4 | 4 | 0 | 0 | 0 | 13 pass / 6 fail | 8 / 6 / 6 / 0 |
| java | 11 | 11 | 2 | 0 | 2 | 0 | 0 | 0 | 4 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 2 / 1 / 0 |
| rust | 10 | 10 | 0 | 0 | 2 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 0 | 8 pass / 2 fail | 5 / 2 / 1 / 0 |
| swift | 11 | 11 | 0 | 0 | 2 | 0 | 0 | 0 | 5 | 3 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 1 / 1 / 0 |

## Per case

| lang | case | status | FP-W | DS-W | SIL-U | REC-C | MISS-W | MISS-C | READ-M | OVER-R | PLACE | FID | BEH | range | ops a/r/u/nm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | bash_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | bom_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 1/0/0/0 |
| bash | case_patterns.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | crlf.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | crlf_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 2/0/0/0 |
| bash | edits_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 2/3/0/0 |
| bash | edits_uncertain.sh | ok | 0 | 0 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 3:5: unclosed here-document `EOF`) | 1/0/0/0 |
| bash | embedded.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | exec_mode_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | fresh_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | heredoc_in_arith.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | heredoc_in_backtick_subst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | heredoc_matrix.sh | ok | 2 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 1/1/0/0 |
| bash | latin1_edit.sh | unsupported:decodable-input (utf-8: 'utf-8' codec can't decode byte 0xe9 in position 15: invalid continuation byte) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_command.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_arith_or_subshell_across_lines.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:10: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_arith_shift.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_backtick_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_case_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:13: not a valid arithmetic operator: `"`) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:11: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_comment_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_continuation_line_is_code.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_delayed_by_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_delayed_by_spanning_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_dollar_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_double_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_double_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:7: not a valid arithmetic operator: `x`) | 0/0/0/0 |
| bash | lex_escaped_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_here_string.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_ansi_c_delimiter.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_body_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_body_escaped_backslash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_double_quoted.sh | ok | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\"F`) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_quoted_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\x4fF`) | 0/0/0/0 |
| bash | lex_heredoc_in_backticks.sh | ok | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_locale_delimiter.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_partly_quoted.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_quoted_no_joining.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_strip_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_strip_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_in_quotes.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_literal_brace.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_literal_braces.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_nested.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_unterminated.sh | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:6: reached EOF without matching `${` with `}`) | 0/0/0/0 |
| bash | lex_param_hash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_plain.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_single_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_two_heredocs.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_unterminated_heredoc.sh | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `EOF`) | 0/0/0/0 |
| bash | lex_unterminated_quote.sh | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:3: reached EOF without closing quote `"`) | 0/0/0/0 |
| bash | lookalikes.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | malformed_unterminated_single.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:6: reached EOF without closing quote `'`) | 0/0/0/0 |
| bash | malformed_unterminated_subst.sh | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:3: reached EOF without matching `$(` with `)`) | 0/0/0/0 |
| bash | nonascii.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 3/1/0/0 |
| bash | nonl_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | ordinary.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 3/1/0/0 |
| bash | placement_bash_existing.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_header.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_noshebang.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_unit_first.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | syntax_error_lexically_valid.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:1: `if` statement must end with `fi`) | 0/0/0/0 |
| go | bom.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 1/0/0/0 |
| go | cgo_preamble.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | crlf.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 1/0/0/0 |
| go | embedded_sql.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | fresh.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | go_members.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_anchors.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_block.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_plain.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_raw_string.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_unterminated_raw.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs goscanner: 1 differing comment ranges) | 0/0/0/0 |
| go | lookalikes.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | malformed_unterminated_block.go | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | fail:2 (vs goscanner: 2 differing comment ranges) | 0/0/0/0 |
| go | malformed_unterminated_string.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | nonascii.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 2/1/0/0 |
| go | ordinary.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 2/2/0/0 |
| go | placement_go_buildtag.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | placement_go_pkgdoc.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/1/0 |
| go | runes_and_strings.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | struct_tags.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | syntax_error_lexically_valid.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| java | CharsAndStrings.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Crlf.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| java | EmbeddedSql.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Fresh.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| java | MalformedComment.java | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | MalformedTextBlock.java | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Nested.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | NonAscii.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| java | Ordinary.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| java | TextBlocks.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | UnicodeEscape.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | backtick_names.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | char_and_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | crlf.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | embedded_json.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | fresh_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | kotlin_members.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_anchors.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_block_nested.kt | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_plain.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_raw.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_slashes_in_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_template_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_unterminated_raw.kt | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lookalikes.kt | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_block.kt | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_string.kt | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nested_comments.kt | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nonascii.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| kotlin | ordinary.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| kotlin | placement_kotlin_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_license.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_member.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_member_existing.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_package.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | raw_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | script.kts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (no native oracle) | 0/0/0/0 |
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
| python | edits_uncertain.py | ok | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/1 |
| python | embedded_sql.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | fstrings_312.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | latin1_cookie.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/1/0 |
| python | latin1_member.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/2/0 |
| python | lex_brackets.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_continuation.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_fstring_nested.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_hash_in_string.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_raw_triple.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_string_not_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_unterminated.py | ok | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lookalikes.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | malformed_unterminated_single.py | ok | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
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
| python | triple_strings.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | tstring_314.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| rust | chars_and_macros.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | crlf.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| rust | embedded_sql.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | inner_attrs.rs | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:2 (no native oracle) | 0/0/1/0 |
| rust | malformed_nested.rs | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | malformed_raw.rs | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nested_comments.rs | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nonascii.rs | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| rust | ordinary.rs | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (no native oracle) | 2/1/0/0 |
| rust | raw_strings.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | crlf.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| swift | embedded_json.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | fresh_imports.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| swift | malformed_multiline.swift | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | malformed_nested.swift | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | nested_comments.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | nonascii.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| swift | ordinary.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/0/0/0 |
| swift | raw_strings.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | regex_literals.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | shebang.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| typescript | crlf.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | embedded.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | fresh_comment_between.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | fresh_imports_only.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | fresh_noimports.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | fresh_strict_imports.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | html_comments.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:3 (vs ts-parser: 1 differing comment ranges) | 0/0/0/0 |
| typescript | imports.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/1/0 |
| typescript | jsx_text.jsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | fail:1 (vs ts-parser: 1 differing comment ranges) | 0/0/0/0 |
| typescript | jsx_text.tsx | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:2 (vs ts-parser: 2 differing comment ranges) | 0/0/0/0 |
| typescript | malformed_unterminated_comment.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:2 (vs ts-parser: 2 differing comment ranges) | 0/0/0/0 |
| typescript | malformed_unterminated_template.ts | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | nonascii.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 2/0/0/0 |
| typescript | nonascii.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 2/1/0/0 |
| typescript | nonascii.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 0 | 0 | 0 | fail:1 (vs ts-parser: 1 differing comment ranges) | 0/2/0/0 |
| typescript | ordinary.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 2/2/0/0 |
| typescript | prologue.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:2 (vs ts-parser: 1 differing comment ranges) | 0/0/1/0 |
| typescript | regex.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | templates.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/1/0/0 |

## Notes per case

- `bash/bom_edit.sh`
  - range vs shfmt: extra [3,29) "# header after a UTF-8 BOM"
- `bash/edits_uncertain.sh`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=2 member= key=covers value=src/u.sh stamp= origin=comment
  - op 1 (annotate member= source=src/u.sh stamp=@2026-02-02/bbbbbbbbbb) [restamp]: outcome "applied", want "refused:uncertain"
  - op 1 (annotate member= source=src/u.sh stamp=@2026-02-02/bbbbbbbbbb) [restamp]: records after differ: extra line=2 member= key=covers value=src/u.sh stamp=@2026-02-02/bbbbbbbbbb origin=comment
  - op 2 (raw kind=replace line=2 member= source=src/u.sh new=# testmap:covers src/u.sh @2026-02-02/bbbbbbbbbb) [raw]: outcome "unchanged", want "refused:uncertain"
  - op 2 (raw kind=replace line=2 member= source=src/u.sh new=# testmap:covers src/u.sh @2026-02-02/bbbbbbbbbb) [raw]: records after differ: extra line=2 member= key=covers value=src/u.sh stamp=@2026-02-02/bbbbbbbbbb origin=comment
- `bash/heredoc_matrix.sh`
  - FP-writable: line 22 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [383,412) "# testmap:covers src/fake5.sh"
  - read: extra line=22 member= key=covers value=src/fake5.sh stamp= origin=comment
  - FP-writable: look-alike/read-only line 22 read as a comment annotation
  - op 1 (annotate member= source=src/new.sh stamp=@2026-10-12/aaaaaaaaaa) [file-append]: records after differ: extra line=22 member= key=covers value=src/fake5.sh stamp= origin=comment
  - op 2 (raw kind=replace line=14 member= source=src/fake3.sh new=# testmap:covers src/fake3.sh @2026-02-02/bbbbbbbbbb) [raw]: records after differ: extra line=22 member= key=covers value=src/fake5.sh stamp= origin=comment
- `bash/lex_backtick_spanning.sh`
  - policy divergence: line 2 classed Comment (a real comment the M2.2 policy never treats as an annotation line)
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `bash/lex_cmdsubst_of_subshell_quoted.sh`
  - missed-comment: line 2 classed Literal
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
- `bash/lex_heredoc_ansi_c_delimiter.sh`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [18,59) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=3 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `bash/lex_heredoc_body_continuation.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [22,63) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_heredoc_escape_in_double_quoted.sh`
  - silent-uncertain: expect uncertain, got certain
- `bash/lex_heredoc_in_backticks.sh`
  - silent-uncertain: expect uncertain, got certain
- `bash/lex_heredoc_locale_delimiter.sh`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [18,59) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=3 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `bash/lex_heredoc_partly_quoted.sh`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [12,53) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 2 read as a comment annotation
- `bash/lex_heredoc_strip_continuation.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_param_expansion_unterminated.sh`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain@1"
- `bash/lex_two_heredocs.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [56,97) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_unterminated_heredoc.sh`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain@1"
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 2 read as a comment annotation
- `bash/lex_unterminated_quote.sh`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain@1"
- `bash/lookalikes.sh`
  - FP-writable: line 9 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [176,207) "# testmap:covers src/delayed.sh"
  - read: extra line=9 member= key=covers value=src/delayed.sh stamp= origin=comment
  - FP-writable: look-alike/read-only line 9 read as a comment annotation
- `bash/malformed_unterminated_subst.sh`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=3 member= key=covers value=src/x.sh stamp= origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `go/fresh.go`
  - placement file: unsupported:APackage
  - op 1 (annotate member= source=src/fresh.go stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage
- `go/lex_anchors.go`
  - placement file: unsupported:APackage
- `go/lex_unterminated_raw.go`
  - range vs goscanner: extra [20,62) "// testmap:covers x @2026-01-01/01234567"
- `go/malformed_unterminated_block.go`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - range vs goscanner: missing [10,45) "/* open\n// testmap:covers src/x.go\n"
  - range vs goscanner: extra [18,44) "// testmap:covers src/x.go"
  - refusal: got "", want "uncertain"
  - read: extra line=3 member= key=covers value=src/x.go stamp= origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `go/placement_go_buildtag.go`
  - placement file: unsupported:APackage
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage
- `go/placement_go_pkgdoc.go`
  - placement file: unsupported:APackage
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage
- `java/Fresh.java`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/fresh.java stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `java/MalformedComment.java`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=3 member= key=covers value=src/x.java stamp= origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `java/MalformedTextBlock.java`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `java/UnicodeEscape.java`
  - over-refusal: valid file uncertain at line 3 (pygments error token "\\")
  - refusal: got "uncertain@3", want ""
- `kotlin/backtick_names.kt`
  - over-refusal: valid file uncertain at line 2 (pygments error token "`")
  - refusal: got "uncertain@2", want ""
- `kotlin/fresh_imports.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=app/fresh.kt stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/lex_anchors.kt`
  - placement file: unsupported:APackage,AImportEnd
- `kotlin/lex_block_nested.kt`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 2 read as a comment annotation
- `kotlin/lex_raw.kt`
  - over-refusal: valid file uncertain at line 3 (pygments error token "\\")
  - refusal: got "uncertain@3", want ""
- `kotlin/lex_template_string.kt`
  - missed-comment: line 2 classed Literal
- `kotlin/lex_unterminated_raw.kt`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain@1"
- `kotlin/lookalikes.kt`
  - FP-writable: line 7 classed Comment (look-alike/read-only)
  - read: extra line=7 member= key=covers value=src/InBlock.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 7 read as a comment annotation
- `kotlin/malformed_unterminated_block.kt`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=3 member= key=covers value=app/x.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `kotlin/malformed_unterminated_string.kt`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `kotlin/nested_comments.kt`
  - FP-writable: line 9 classed Comment (look-alike/read-only)
  - read: extra line=9 member= key=covers value=app/still_outer.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 9 read as a comment annotation
- `kotlin/placement_kotlin_imports.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/placement_kotlin_license.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/placement_kotlin_package.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/raw_templates.kt`
  - over-refusal: valid file uncertain at line 5 (pygments error token "\\")
  - refusal: got "uncertain@5", want ""
- `kotlin/script.kts`
  - range: line comment at 0 does not start with "//"
- `python/bom_doc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/bom_doc.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/crlf_doc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/crlf_doc.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (annotate member= source=src/crlf2.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/doc_grouping_multiline.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/g.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/doc_implicit_concat.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/x.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa): not measured — follows unsupported op 1
- `python/doc_paren_closing_later.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/p.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (annotate member= source=src/comment.sh stamp=@2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
- `python/doc_raw.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/raw.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/doc_shape_00.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_01.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/doc_shape_02.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/doc_shape_03.py`
  - records: unsupported:DocLiterals
- `python/doc_shape_04.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=a stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
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
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_01.py`
  - records: unsupported:DocLiterals
- `python/docvalue_02.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/b.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_03.py`
  - records: unsupported:DocLiterals
- `python/docvalue_04.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/c.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_05.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/d.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_06.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_07.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_08.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_09.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/e.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_10.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_11.py`
  - records: unsupported:DocLiterals
- `python/docvalue_12.py`
  - records: unsupported:DocLiterals
- `python/docvalue_13.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_14.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/�.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_15.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_16.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/zz.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_17.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/a.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/docvalue_18.py`
  - records: unsupported:DocLiterals
- `python/docvalue_19.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/f.sh stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/edits_uncertain.py`
  - silent-uncertain: expect uncertain, got certain
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/u.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (raw kind=replace line=1 member= source=src/u.py new=# testmap:covers src/u.py @2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
- `python/embedded_sql.py`
  - records: unsupported:DocLiterals
- `python/fstrings_312.py`
  - over-refusal: valid file uncertain at line 4 (pygments error token "#")
  - range vs pytokenize: missing [39,85) "# a comment inside a replacement field ("
  - records: unsupported:DocLiterals
- `python/latin1_cookie.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/latin1.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
- `python/latin1_member.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/latin1_file.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals
  - op 2 (annotate member=TestLatin1 source=src/latin1_more.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals
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
  - records: unsupported:DocLiterals
- `python/lex_string_not_docstring.py`
  - records: unsupported:DocLiterals
- `python/lex_unterminated.py`
  - silent-uncertain: expect uncertain, got certain
  - records: unsupported:DocLiterals
- `python/lookalikes.py`
  - records: unsupported:DocLiterals
- `python/malformed_unterminated_single.py`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - range vs pytokenize: extra [18,43) "# testmap:covers src/x.py"
  - records: unsupported:DocLiterals
- `python/nodoc_fresh.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/fresh.py stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:DocLiterals
- `python/nonascii.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/real.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals
  - op 2 (annotate member= source=src/new.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals
  - op 3 (annotate member=TestNonAscii source=src/more.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals
  - op 4 (raw kind=replace line=2 member= source=src/fake.py from=original new=# testmap:covers src/fake.py @2026-02-02/bbbbbbbbbb) [raw]: unsupported:DocLiterals
- `python/nonascii_doc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/doc_x.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (annotate member= source=src/a.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals
  - op 3 (annotate member= source=src/b.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals
- `python/not_doc_bytes.py`
  - records: unsupported:DocLiterals
- `python/not_doc_call.py`
  - records: unsupported:DocLiterals
- `python/not_doc_fstring.py`
  - records: unsupported:DocLiterals
- `python/ordinary.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/doc_src.py stamp=@2026-02-02/bbbbbbbbbb) []: unsupported:DocLiterals
  - op 2 (raw kind=replace line=3 member= source=src/doc_src.py new=# testmap:covers src/doc_src.py @2026-02-02/bbbbbbbbbb): not measured — follows unsupported op 1
  - op 3 (annotate member= source=src/a.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals
  - op 4 (annotate member=TestA source=src/a.py stamp=@2026-02-02/bbbbbbbbbb from=original) []: unsupported:DocLiterals
  - op 5 (annotate member=TestA source=src/b.py stamp=@2026-10-12/aaaaaaaaaa from=original) []: unsupported:DocLiterals
  - op 6 (raw kind=replace line=14 member=TestA source=src/fake.py from=original new=# testmap:covers src/fake.py @2026-02-02/bbbbbbbbbb) [raw]: unsupported:DocLiterals
- `python/placement_python_docstring.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:DocLiterals
- `python/placement_python_nodoc.py`
  - records: unsupported:DocLiterals
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) []: unsupported:DocLiterals
- `python/python_docstring.py`
  - records: unsupported:DocLiterals
- `python/syntax_error_lexically_valid.py`
  - records: unsupported:DocLiterals
- `python/triple_strings.py`
  - records: unsupported:DocLiterals
- `python/tstring_314.py`
  - records: unsupported:DocLiterals
- `rust/inner_attrs.rs`
  - missed-comment: line 1 classed Code
  - range: line comment at 15 does not start with "//"
  - range: line comment at 33 does not start with "//"
  - placement file: unsupported:AImportEnd,AInnerAttrEnd
  - op 1 (annotate member= source=src/inner.rs stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,AInnerAttrEnd
- `rust/malformed_nested.rs`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `rust/malformed_raw.rs`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `rust/nested_comments.rs`
  - missed-comment: line 4 classed Code
- `rust/nonascii.rs`
  - missed-comment: line 1 classed Code
- `rust/ordinary.rs`
  - missed-comment: line 1 classed Code
  - range: line comment at 16 does not start with "//"
- `swift/embedded_json.swift`
  - over-refusal: valid file uncertain at line 2 (pygments error token "\"")
  - refusal: got "uncertain@2", want ""
- `swift/fresh_imports.swift`
  - placement file: unsupported:AImportEnd
  - op 1 (annotate member= source=Sources/fresh.swift stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd
- `swift/malformed_multiline.swift`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `swift/malformed_nested.swift`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `swift/raw_strings.swift`
  - over-refusal: valid file uncertain at line 8 (pygments error token "\\")
  - refusal: got "uncertain@8", want ""
- `swift/regex_literals.swift`
  - over-refusal: valid file uncertain at line 1 (pygments error token "\\")
  - refusal: got "uncertain@1", want ""
- `typescript/fresh_comment_between.tsx`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_comment_between.tsx stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,APrologue
- `typescript/fresh_imports_only.ts`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_imports_only.ts stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,APrologue
- `typescript/fresh_noimports.ts`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_noimports.ts stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,APrologue
- `typescript/fresh_strict_imports.js`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/fresh_strict_imports.js stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,APrologue
- `typescript/html_comments.js`
  - range: line comment at 11 does not start with "//"
  - range: line comment [11,15) does not end at end of line
  - range vs ts-parser: extra [11,15) "<!--"
- `typescript/imports.ts`
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/imports.ts stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,APrologue
- `typescript/jsx_text.jsx`
  - over-refusal: valid file uncertain at line 5 (pygments error token "/")
  - range vs ts-parser: extra [35,69) "// testmap:covers src/jsx_text.jsx"
  - refusal: got "uncertain@5", want ""
- `typescript/jsx_text.tsx`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - range vs ts-parser: extra [49,83) "// testmap:covers src/jsx_text.tsx"
  - range vs ts-parser: extra [90,116) "/* not a comment either */"
  - read: extra line=4 member= key=covers value=src/jsx_text.tsx stamp= origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `typescript/malformed_unterminated_comment.js`
  - range vs ts-parser: missing [11,46) "/* open\n// testmap:covers src/x.js\n"
  - range vs ts-parser: extra [19,45) "// testmap:covers src/x.js"
- `typescript/malformed_unterminated_template.ts`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `typescript/nonascii.tsx`
  - over-refusal: valid file uncertain at line 7 (pygments error token "😀")
  - range vs ts-parser: extra [220,256) "// testmap:covers src/fake2.tsx</p>;"
  - refusal: got "uncertain@7", want ""
  - op 1 (annotate member= source=src/real.tsx stamp=@2026-02-02/bbbbbbbbbb from=original): outcome "refused:uncertain", want "applied"
  - op 1 (annotate member= source=src/real.tsx stamp=@2026-02-02/bbbbbbbbbb from=original): records after differ: missing line=4 member= key=covers value=src/real.tsx stamp=@2026-02-02/bbbbbbbbbb origin=comment
  - op 2 (annotate member= source=src/new.tsx stamp=@2026-10-12/aaaaaaaaaa from=original): outcome "refused:uncertain", want "applied"
  - op 2 (annotate member= source=src/new.tsx stamp=@2026-10-12/aaaaaaaaaa from=original): records after differ: missing line=4 member= key=covers value=src/real.tsx stamp= origin=comment; missing line=5 member= key=covers value=src/new.tsx stamp=@2026-10-12/aaaaaaaaaa origin=comment
- `typescript/prologue.js`
  - range: line comment at 0 does not start with "//"
  - range vs ts-parser: extra [0,19) "#!/usr/bin/env node"
  - placement file: unsupported:AImportEnd,APrologue
  - op 1 (annotate member= source=src/prologue.js stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,APrologue
