# Matrix: antlr

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Safety columns (must be 0): FP-writable, Docstring-write, Silent-uncertain, Record-corruption. Recall/cost: Missed-writable, Missed-comment (a plain comment line not classed Comment), Read-mismatch, Over-refusal, Placement. Fidelity and Behaviour count applied edits that changed other bytes / program behaviour. Definitions: the t1954 shared design, *Metrics*.

## Summary by language

| lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | 69 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| python | 67 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| go | 22 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| kotlin | 31 | 31 | 2 | 0 | 3 | 0 | 1 | 0 | 9 | 4 | 0 | 0 | 0 | 30 pass / 1 fail | 7 / 3 / 4 / 0 |
| typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| java | 11 | 11 | 2 | 0 | 1 | 0 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 11 pass / 0 fail | 5 / 2 / 1 / 0 |
| rust | 10 | 10 | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 10 pass / 0 fail | 5 / 2 / 1 / 0 |
| swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |

## Per case

| lang | case | status | FP-W | DS-W | SIL-U | REC-C | MISS-W | MISS-C | READ-M | OVER-R | PLACE | FID | BEH | range | ops a/r/u/nm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | bash_members.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | bom_edit.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | case_patterns.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | crlf.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | crlf_edit.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | edits_members.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | edits_uncertain.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | embedded.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | exec_mode_edit.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | fresh_noheader.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | funsub_53.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | heredoc_in_arith.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | heredoc_in_backtick_subst.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | heredoc_matrix.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | latin1_edit.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_command.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_or_subshell_across_lines.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_shift.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_backtick_spanning.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_bom_is_a_word.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_case_in_cmdsubst.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell_quoted.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_comment_quote.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_continuation_line_is_code.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_delayed_by_continuation.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_delayed_by_spanning_quote.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_dollar_quote_spanning.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_double_quote_spanning.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_double_subshell.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_escaped_quote.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_here_string.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_ansi_c_delimiter.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_body_continuation.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_body_escaped_backslash.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_escape_in_double_quoted.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_escape_in_quoted_delimiter.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_in_backticks.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_in_cmdsubst.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_locale_delimiter.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_partly_quoted.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_quoted_no_joining.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_strip_continuation.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_heredoc_strip_quoted.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_param_expansion_in_quotes.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_param_expansion_literal_brace.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_param_expansion_literal_braces.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_param_expansion_nested.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_param_expansion_spanning.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_param_expansion_unterminated.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_param_hash.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_plain.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_single_quote_spanning.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_two_heredocs.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_unterminated_heredoc.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_unterminated_quote.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lookalikes.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | malformed_unterminated_single.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | malformed_unterminated_subst.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | nonascii.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | nonl_edit.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | ordinary.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_existing.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_header.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_noheader.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_noshebang.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_unit_first.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | syntax_error_lexically_valid.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | bom.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | cgo_preamble.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | crlf.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | embedded_sql.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | fresh.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | go_members.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_anchors.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_block.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_bom_comment.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_plain.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_raw_string.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_unterminated_raw.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lookalikes.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | malformed_unterminated_block.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | malformed_unterminated_string.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | nonascii.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | ordinary.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | placement_go_buildtag.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | placement_go_pkgdoc.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | runes_and_strings.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | struct_tags.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | syntax_error_lexically_valid.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | CharsAndStrings.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Crlf.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| java | EmbeddedSql.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Fresh.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| java | MalformedComment.java | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | MalformedTextBlock.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | Nested.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | NonAscii.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| java | Ordinary.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| java | TextBlocks.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| java | UnicodeEscape.java | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | backtick_names.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | char_and_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | crlf.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | embedded_json.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | fresh_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | kotlin_members.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_anchors.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_block_nested.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_bom_comment.kt | ok | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_plain.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_raw.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_slashes_in_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_template_string.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lex_unterminated_raw.kt | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | lookalikes.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_block.kt | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | malformed_unterminated_string.kt | ok | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | multidollar_comment_desync.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/1/0/0 |
| kotlin | multidollar_interpolation.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | multidollar_literal_brace.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | multidollar_quote_boundary.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nested_comments.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | nonascii.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| kotlin | ordinary.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| kotlin | placement_kotlin_imports.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_license.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | placement_kotlin_member.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_member_existing.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| kotlin | placement_kotlin_package.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| kotlin | raw_templates.kt | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| kotlin | script.kts | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | fail:1 (no native oracle) | 0/0/0/0 |
| python | bom_doc.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | crlf_doc.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_grouping_multiline.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_implicit_concat.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_paren_closing_later.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_raw.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_00.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_01.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_02.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_03.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_04.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_05.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_06.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_07.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_08.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_09.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | doc_shape_10.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_00.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_01.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_02.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_03.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_04.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_05.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_06.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_07.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_08.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_09.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_10.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_11.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_12.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_13.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_14.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_15.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_16.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_17.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_18.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | docvalue_19.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | edits_uncertain.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | embedded_sql.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | fstrings_312.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | latin1_cookie.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | latin1_member.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_bom_comment.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_brackets.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_continuation.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_docstring.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_fstring_nested.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_hash_in_string.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_raw_triple.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_string_not_docstring.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lex_unterminated.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | lookalikes.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | malformed_unterminated_single.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | nodoc_fresh.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | nonascii.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | nonascii_doc.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | not_doc_bytes.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | not_doc_call.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | not_doc_fstring.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | ordinary.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | placement_python_docstring.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | placement_python_nodoc.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | python_docstring.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | syntax_error_lexically_valid.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | triple_strings.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | tstring_314.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| python | tstrings_314.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | chars_and_macros.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | crlf.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 1/0/0/0 |
| rust | embedded_sql.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | inner_attrs.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/1/0 |
| rust | malformed_nested.rs | ok | 2 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | malformed_raw.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nested_comments.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| rust | nonascii.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| rust | ordinary.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 2/1/0/0 |
| rust | raw_strings.rs | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (no native oracle) | 0/0/0/0 |
| swift | crlf.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | embedded_json.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | fresh_imports.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | malformed_multiline.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | malformed_nested.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | nested_comments.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | nonascii.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | ordinary.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | raw_strings.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | regex_literals.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | shebang.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | crlf.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | embedded.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | fresh_comment_between.tsx | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | fresh_imports_only.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | fresh_noimports.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | fresh_strict_imports.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | html_comments.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | imports.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | jsx_text.jsx | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | jsx_text.tsx | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | malformed_unterminated_comment.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | malformed_unterminated_template.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | nonascii.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | nonascii.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | nonascii.tsx | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | ordinary.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | prologue.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | regex.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | templates.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |

## Notes per case

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
  - range: full cover not checked: uncertain input, recovery gaps attributed to its diagnostics
- `java/TextBlocks.java`
  - over-refusal: valid file uncertain at line 6 (antlr: token recognition error at: '";
')
  - range: full cover not checked: uncertain input, recovery gaps attributed to its diagnostics
  - refusal: got "uncertain@6", want ""
- `java/UnicodeEscape.java`
  - over-refusal: valid file uncertain at line 3 (antlr: token recognition error at: '\')
  - range: full cover not checked: uncertain input, recovery gaps attributed to its diagnostics
  - refusal: got "uncertain@3", want ""
- `kotlin/fresh_imports.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=app/fresh.kt stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/lex_anchors.kt`
  - placement file: unsupported:APackage,AImportEnd
- `kotlin/lex_bom_comment.kt`
  - missed-writable: line 1 classed Code
  - read: missing line=1 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `kotlin/lex_unterminated_raw.kt`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain@1"
- `kotlin/malformed_unterminated_block.kt`
  - FP-writable: line 3 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=3 member= key=covers value=app/x.kt stamp= origin=comment
  - FP-writable: look-alike/read-only line 3 read as a comment annotation
- `kotlin/malformed_unterminated_string.kt`
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
- `kotlin/multidollar_comment_desync.kt`
  - over-refusal: valid file uncertain at line 5 (antlr: token recognition error at: '$$')
  - refusal: got "uncertain@5", want ""
  - op 1 (raw kind=replace line=9 member= source=app/fake.kt from=original new=// testmap:covers app/fake.kt @2026-02-02/bbbbbbbbbb) [raw]: outcome "refused:uncertain", want "refused:not-comment"
  - op 1 (raw kind=replace line=9 member= source=app/fake.kt from=original new=// testmap:covers app/fake.kt @2026-02-02/bbbbbbbbbb) [raw]: refused for a different reason; file untouched
  - op 1 (raw kind=replace line=9 member= source=app/fake.kt from=original new=// testmap:covers app/fake.kt @2026-02-02/bbbbbbbbbb) [raw]: records after differ: missing line=3 member= key=covers value=app/real.kt stamp= origin=comment
- `kotlin/multidollar_interpolation.kt`
  - over-refusal: valid file uncertain at line 4 (antlr: token recognition error at: '$$')
  - refusal: got "uncertain@4", want ""
- `kotlin/multidollar_literal_brace.kt`
  - over-refusal: valid file uncertain at line 3 (antlr: token recognition error at: '$$')
  - refusal: got "uncertain@3", want ""
- `kotlin/multidollar_quote_boundary.kt`
  - over-refusal: valid file uncertain at line 3 (antlr: token recognition error at: '$$')
  - refusal: got "uncertain@3", want ""
- `kotlin/placement_kotlin_imports.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/placement_kotlin_license.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/placement_kotlin_package.kt`
  - placement file: unsupported:APackage,AImportEnd
  - op 1 (annotate member= source=src/new stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:APackage,AImportEnd
- `kotlin/script.kts`
  - range: line comment at 0 does not start with "//"
- `rust/inner_attrs.rs`
  - placement file: unsupported:AImportEnd,AInnerAttrEnd
  - op 1 (annotate member= source=src/inner.rs stamp=@2026-10-12/aaaaaaaaaa) [fresh-file-insert]: unsupported:AImportEnd,AInnerAttrEnd
- `rust/malformed_nested.rs`
  - FP-writable: line 2 classed Comment (look-alike/read-only)
  - silent-uncertain: expect uncertain, got certain
  - refusal: got "", want "uncertain"
  - read: extra line=2 member= key=covers value=src/x.rs stamp= origin=comment
  - FP-writable: look-alike/read-only line 2 read as a comment annotation
- `rust/malformed_raw.rs`
  - range: full cover not checked: uncertain input, recovery gaps attributed to its diagnostics
