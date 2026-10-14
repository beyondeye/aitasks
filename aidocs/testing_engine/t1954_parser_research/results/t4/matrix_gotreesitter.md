# Matrix: gotreesitter

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Safety columns (must be 0): FP-writable, Docstring-write, Silent-uncertain, Record-corruption. Recall/cost: Missed-writable, Missed-comment (a plain comment line not classed Comment), Read-mismatch, Over-refusal, Placement. Fidelity and Behaviour count applied edits that changed other bytes / program behaviour. Definitions: the t1954 shared design, *Metrics*.

## Summary by language

| lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | 69 | 69 | 4 | 0 | 0 | 0 | 0 | 2 | 8 | 13 | 0 | 0 | 0 | 63 pass / 6 fail | 20 / 9 / 0 / 0 |
| python | 67 | 67 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 2 | 0 | 0 | 0 | 65 pass / 2 fail | 20 / 31 / 0 / 0 |
| go | 22 | 22 | 0 | 0 | 0 | 0 | 1 | 0 | 2 | 1 | 0 | 0 | 0 | 21 pass / 1 fail | 9 / 3 / 0 / 0 |
| kotlin | 31 | 31 | 2 | 0 | 2 | 0 | 1 | 0 | 4 | 1 | 0 | 0 | 0 | 31 pass / 0 fail | 11 / 3 / 0 / 0 |
| typescript | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 16 pass / 3 fail | 16 / 4 / 0 / 0 |
| java | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 2 / 0 / 0 |
| rust | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 6 / 2 / 0 / 0 |
| swift | 11 | 11 | 2 | 0 | 1 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 11 pass / 0 fail | 6 / 1 / 0 / 0 |

## Per case

| lang | case | status | FP-W | DS-W | SIL-U | REC-C | MISS-W | MISS-C | READ-M | OVER-R | PLACE | FID | BEH | range | ops a/r/u/nm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | bash_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | bom_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 1/0/0/0 |
| bash | case_patterns.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | crlf.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | crlf_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 2/0/0/0 |
| bash | edits_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 2/3/0/0 |
| bash | edits_uncertain.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 3:5: unclosed here-document `EOF`) | 0/2/0/0 |
| bash | embedded.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | exec_mode_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | fresh_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | funsub_53.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | heredoc_in_arith.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | heredoc_in_backtick_subst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | heredoc_matrix.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/2/0/0 |
| bash | latin1_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:6: invalid UTF-8 encoding) | 1/0/0/0 |
| bash | lex_arith_command.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_arith_or_subshell_across_lines.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:10: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_arith_shift.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_backtick_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_bom_is_a_word.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_case_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:13: not a valid arithmetic operator: `"`) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:11: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_comment_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_continuation_line_is_code.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_delayed_by_continuation.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_delayed_by_spanning_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_dollar_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_double_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_double_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:7: not a valid arithmetic operator: `x`) | 0/0/0/0 |
| bash | lex_escaped_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_here_string.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_ansi_c_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_body_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_body_escaped_backslash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_double_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\"F`) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_quoted_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\x4fF`) | 0/0/0/0 |
| bash | lex_heredoc_in_backticks.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_locale_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_partly_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_quoted_no_joining.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_strip_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_heredoc_strip_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_in_quotes.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_literal_brace.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_literal_braces.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_nested.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_param_expansion_unterminated.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:6: reached EOF without matching `${` with `}`) | 0/0/0/0 |
| bash | lex_param_hash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_plain.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_single_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | lex_two_heredocs.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | fail:1 (vs shfmt: 1 differing comment ranges) | 0/0/0/0 |
| bash | lex_unterminated_heredoc.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `EOF`) | 0/0/0/0 |
| bash | lex_unterminated_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:3: reached EOF without closing quote `"`) | 0/0/0/0 |
| bash | lookalikes.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 0/0/0/0 |
| bash | malformed_unterminated_single.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:6: reached EOF without closing quote `'`) | 0/0/0/0 |
| bash | malformed_unterminated_subst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:3: reached EOF without matching `$(` with `)`) | 0/0/0/0 |
| bash | nonascii.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 3/1/0/0 |
| bash | nonl_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | ordinary.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 3/1/0/0 |
| bash | placement_bash_existing.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_header.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_noshebang.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | placement_bash_unit_first.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs shfmt: 0 differing comment ranges) | 1/0/0/0 |
| bash | syntax_error_lexically_valid.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:1: `if` statement must end with `fi`) | 0/0/0/0 |
| go | bom.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 1/0/0/0 |
| go | cgo_preamble.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | crlf.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 1/0/0/0 |
| go | embedded_sql.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | fresh.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 1/0/0/0 |
| go | go_members.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_anchors.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_block.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_bom_comment.go | ok | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_plain.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_raw_string.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lex_unterminated_raw.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | lookalikes.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | malformed_unterminated_block.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs goscanner: 1 differing comment ranges) | 0/0/0/0 |
| go | malformed_unterminated_string.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | nonascii.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 2/1/0/0 |
| go | ordinary.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 2/2/0/0 |
| go | placement_go_buildtag.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 1/0/0/0 |
| go | placement_go_pkgdoc.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 1/0/0/0 |
| go | runes_and_strings.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | struct_tags.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| go | syntax_error_lexically_valid.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (vs goscanner: 0 differing comment ranges) | 0/0/0/0 |
| java | CharsAndStrings.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Crlf.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| java | EmbeddedSql.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Fresh.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| java | MalformedComment.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | MalformedTextBlock.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Nested.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | NonAscii.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| java | Ordinary.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| java | TextBlocks.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | UnicodeEscape.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | backtick_names.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | char_and_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | crlf.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | embedded_json.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | fresh_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | kotlin_members.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_anchors.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_block_nested.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_bom_comment.kt | ok | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_plain.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_raw.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_slashes_in_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_template_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_unterminated_raw.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lookalikes.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_block.kt | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_string.kt | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | multidollar_comment_desync.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/1/0/0 |
| kotlin | multidollar_interpolation.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | multidollar_literal_brace.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | multidollar_quote_boundary.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nested_comments.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nonascii.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| kotlin | ordinary.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| kotlin | placement_kotlin_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_license.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_member.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_member_existing.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_package.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | raw_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | script.kts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| python | bom_doc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/1/0/0 |
| python | crlf_doc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/1/0/0 |
| python | doc_grouping_multiline.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/1/0/0 |
| python | doc_implicit_concat.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/1/0/0 |
| python | doc_paren_closing_later.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/1/0/0 |
| python | doc_raw.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | doc_shape_00.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_01.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | doc_shape_02.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | doc_shape_03.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_04.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | doc_shape_05.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_06.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_07.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_08.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_09.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | doc_shape_10.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_00.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_01.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_02.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_03.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_04.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_05.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_06.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_07.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_08.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_09.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/0/0/0 |
| python | docvalue_10.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_11.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_12.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_13.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_14.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_15.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_16.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_17.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | docvalue_18.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | docvalue_19.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/1/0/0 |
| python | edits_uncertain.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/2/0/0 |
| python | embedded_sql.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | fstrings_312.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | latin1_cookie.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/0/0/0 |
| python | latin1_member.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 2/0/0/0 |
| python | lex_bom_comment.py | ok | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_brackets.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_continuation.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_fstring_nested.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_hash_in_string.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_raw_triple.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_string_not_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | lex_unterminated.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | lookalikes.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | malformed_unterminated_single.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs pytokenize: 1 differing comment ranges) | 0/0/0/0 |
| python | nodoc_fresh.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/0/0/0 |
| python | nonascii.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 3/1/0/0 |
| python | nonascii_doc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 2/1/0/0 |
| python | not_doc_bytes.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | not_doc_call.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | not_doc_fstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | ordinary.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 3/3/0/0 |
| python | placement_python_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/0/0/0 |
| python | placement_python_nodoc.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 1/0/0/0 |
| python | python_docstring.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | syntax_error_lexically_valid.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | triple_strings.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | tstring_314.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| python | tstrings_314.py | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs pytokenize: 0 differing comment ranges) | 0/0/0/0 |
| rust | chars_and_macros.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | crlf.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| rust | embedded_sql.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | inner_attrs.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| rust | malformed_nested.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | malformed_raw.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nested_comments.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nonascii.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| rust | ordinary.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| rust | raw_strings.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | crlf.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| swift | embedded_json.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | fresh_imports.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| swift | malformed_multiline.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | malformed_nested.swift | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | nested_comments.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | nonascii.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| swift | ordinary.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/0/0/0 |
| swift | raw_strings.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | regex_literals.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | shebang.swift | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| typescript | crlf.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | embedded.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | fresh_comment_between.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | fresh_imports_only.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | fresh_noimports.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | fresh_strict_imports.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | html_comments.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:2 (vs ts-parser: 2 differing comment ranges) | 0/0/0/0 |
| typescript | imports.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | jsx_text.jsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | jsx_text.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | malformed_unterminated_comment.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:2 (vs ts-parser: 2 differing comment ranges) | 0/0/0/0 |
| typescript | malformed_unterminated_template.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (vs ts-parser: 1 differing comment ranges) | 0/0/0/0 |
| typescript | nonascii.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 2/0/0/0 |
| typescript | nonascii.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 2/1/0/0 |
| typescript | nonascii.tsx | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 2/0/0/0 |
| typescript | ordinary.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 2/2/0/0 |
| typescript | prologue.js | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/0/0/0 |
| typescript | regex.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 0/0/0/0 |
| typescript | templates.ts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (vs ts-parser: 0 differing comment ranges) | 1/1/0/0 |

## Notes per case

- `bash/bom_edit.sh`
  - range vs shfmt: extra [3,29) "# header after a UTF-8 BOM"
- `bash/funsub_53.sh`
  - over-refusal: valid file uncertain at line 2 (ERROR node)
  - refusal: got "uncertain@2", want ""
- `bash/heredoc_matrix.sh`
  - over-refusal: valid file uncertain at line 23 (MISSING ;)
  - refusal: got "uncertain@23", want ""
  - op 1 (annotate member= source=src/new.sh stamp=@2026-10-12/aaaaaaaaaa): outcome "refused:uncertain", want "applied"
  - op 1 (annotate member= source=src/new.sh stamp=@2026-10-12/aaaaaaaaaa): records after differ: missing line=2 member= key=covers value=src/heredoc.sh stamp= origin=comment; missing line=24 member= key=covers value=src/real2.sh stamp= origin=comment; missing line=25 member= key=covers value=src/new.sh stamp=@2026-10-12/aaaaaaaaaa origin=comment
  - op 2 (raw kind=replace line=14 member= source=src/fake3.sh new=# testmap:covers src/fake3.sh @2026-02-02/bbbbbbbbbb) [raw]: outcome "refused:uncertain", want "refused:not-comment"
  - op 2 (raw kind=replace line=14 member= source=src/fake3.sh new=# testmap:covers src/fake3.sh @2026-02-02/bbbbbbbbbb) [raw]: refused for a different reason; file untouched
  - op 2 (raw kind=replace line=14 member= source=src/fake3.sh new=# testmap:covers src/fake3.sh @2026-02-02/bbbbbbbbbb) [raw]: records after differ: missing line=2 member= key=covers value=src/heredoc.sh stamp= origin=comment; missing line=24 member= key=covers value=src/real2.sh stamp= origin=comment; missing line=25 member= key=covers value=src/new.sh stamp=@2026-10-12/aaaaaaaaaa origin=comment
- `bash/lex_arith_command.sh`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
- `bash/lex_arith_or_subshell_across_lines.sh`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
- `bash/lex_bom_is_a_word.sh`
  - range vs shfmt: extra [3,11) "# header"
- `bash/lex_cmdsubst_of_subshell.sh`
  - over-refusal: valid file uncertain at line 1 (MISSING )))
- `bash/lex_cmdsubst_of_subshell_quoted.sh`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
- `bash/lex_heredoc_ansi_c_delimiter.sh`
  - missed-comment: line 5 classed Literal
  - range vs shfmt: missing [64,70) "# real"
- `bash/lex_heredoc_body_continuation.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - range vs shfmt: extra [22,63) "# testmap:covers x @2026-01-01/012345678"
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_heredoc_escape_in_quoted_delimiter.sh`
  - over-refusal: valid file uncertain at line 3 (MISSING heredoc_end)
  - refusal: got "uncertain@3", want ""
- `bash/lex_heredoc_locale_delimiter.sh`
  - missed-comment: line 5 classed Literal
  - range vs shfmt: missing [64,70) "# real"
- `bash/lex_heredoc_partly_quoted.sh`
  - over-refusal: valid file uncertain at line 3 (MISSING ;)
  - refusal: got "uncertain@3", want ""
- `bash/lex_heredoc_strip_continuation.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/lex_param_expansion_literal_brace.sh`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
- `bash/lex_param_expansion_literal_braces.sh`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
- `bash/lex_two_heredocs.sh`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
  - range vs shfmt: extra [56,97) "# testmap:covers x @2026-01-01/012345678"
  - refusal: got "uncertain@1", want ""
- `bash/syntax_error_lexically_valid.sh`
  - over-refusal: valid file uncertain at line 4 (MISSING fi)
  - refusal: got "uncertain@4", want ""
- `go/lex_bom_comment.go`
  - missed-writable: line 1 classed Code
  - read: missing line=1 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `go/malformed_unterminated_block.go`
  - range vs goscanner: missing [10,45) "/* open\n// testmap:covers src/x.go\n"
- `go/syntax_error_lexically_valid.go`
  - over-refusal: valid file uncertain at line 3 (ERROR node)
  - refusal: got "uncertain@3", want ""
- `java/Fresh.java`
  - placement file (proposed rule): 4; landed default fixedPosition: 0
- `java/UnicodeEscape.java`
  - over-refusal: valid file uncertain at line 3 (ERROR node)
  - refusal: got "uncertain@3", want ""
- `kotlin/lex_anchors.kt`
  - over-refusal: valid file uncertain at line 7 (ERROR node)
- `kotlin/lex_bom_comment.kt`
  - missed-writable: line 1 classed Code
  - read: missing line=1 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `kotlin/malformed_unterminated_block.kt`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `kotlin/malformed_unterminated_string.kt`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=2 member= key=covers value=app/x.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 2 read as a comment annotation
- `python/lex_bom_comment.py`
  - missed-comment: line 1 classed Code
- `python/lex_continuation.py`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
  - refusal: got "uncertain@1", want ""
- `python/lex_unterminated.py`
  - range vs pytokenize: extra [8,49) "# testmap:covers x @2026-01-01/012345678"
- `python/malformed_unterminated_single.py`
  - range vs pytokenize: extra [18,43) "# testmap:covers src/x.py"
- `python/syntax_error_lexically_valid.py`
  - over-refusal: valid file uncertain at line 1 (MISSING ))
  - refusal: got "uncertain@1", want ""
- `rust/inner_attrs.rs`
  - placement file (proposed rule): 9; landed default fixedPosition: 1
- `swift/fresh_imports.swift`
  - placement file (proposed rule): 2; landed default fixedPosition: 0
- `swift/malformed_nested.swift`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=2 member= key=covers value=Sources/x.swift stamp= origin=comment
  - FP-writable: look-alike/read-only line 2 read as a comment annotation
- `swift/regex_literals.swift`
  - over-refusal: valid file uncertain at line 1 (ERROR node)
  - refusal: got "uncertain@1", want ""
- `typescript/fresh_comment_between.tsx`
  - placement file (proposed rule): 2; landed default fixedPosition: 0
- `typescript/fresh_imports_only.ts`
  - placement file (proposed rule): 2; landed default fixedPosition: 0
- `typescript/fresh_noimports.ts`
  - placement file (proposed rule): 1; landed default fixedPosition: 1
- `typescript/fresh_strict_imports.js`
  - placement file (proposed rule): 2; landed default fixedPosition: 0
- `typescript/html_comments.js`
  - range vs ts-parser: extra [11,42) "<!-- testmap:covers src/html.js"
  - range vs ts-parser: extra [43,74) "--> testmap:covers src/html2.js"
- `typescript/imports.ts`
  - placement file (proposed rule): 5; landed default fixedPosition: 1
- `typescript/malformed_unterminated_comment.js`
  - range vs ts-parser: missing [11,46) "/* open\n// testmap:covers src/x.js\n"
  - range vs ts-parser: extra [19,45) "// testmap:covers src/x.js"
- `typescript/malformed_unterminated_template.ts`
  - range vs ts-parser: extra [15,41) "// testmap:covers src/x.ts"
- `typescript/prologue.js`
  - placement file (proposed rule): 2; landed default fixedPosition: 1
