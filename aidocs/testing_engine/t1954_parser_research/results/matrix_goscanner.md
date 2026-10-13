# Matrix: goscanner

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Safety columns (must be 0): FP-writable, Docstring-write, Silent-uncertain, Record-corruption. Recall/cost: Missed-writable, Missed-comment (a plain comment line not classed Comment), Read-mismatch, Over-refusal, Placement. Fidelity and Behaviour count applied edits that changed other bytes / program behaviour. Definitions: the t1954 shared design, *Metrics*.

## Summary by language

| lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | 66 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| python | 61 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| go | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 pass / 0 fail | 7 / 2 / 0 / 0 |
| kotlin | 25 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| typescript | 12 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| java | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| rust | 9 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| swift | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |

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
| bash | heredoc_in_arith.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | heredoc_in_backtick_subst.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | heredoc_matrix.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | latin1_edit.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_command.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_or_subshell_across_lines.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_arith_shift.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | lex_backtick_spanning.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
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
| bash | nonl_edit.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | ordinary.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_existing.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_header.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_noheader.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_noshebang.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | placement_bash_unit_first.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| bash | syntax_error_lexically_valid.sh | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | bom.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 1/0/0/0 |
| go | cgo_preamble.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | crlf.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 1/0/0/0 |
| go | embedded_sql.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | fresh.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 1/0/0/0 |
| go | go_members.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | lex_anchors.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | lex_block.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | lex_plain.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | lex_raw_string.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | lex_unterminated_raw.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | lookalikes.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | malformed_unterminated_block.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | malformed_unterminated_string.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | ordinary.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 2/2/0/0 |
| go | placement_go_buildtag.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 1/0/0/0 |
| go | placement_go_pkgdoc.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 1/0/0/0 |
| go | runes_and_strings.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | struct_tags.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| go | syntax_error_lexically_valid.go | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (goscanner)) | 0/0/0/0 |
| java | CharsAndStrings.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | Crlf.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | EmbeddedSql.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | Fresh.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | MalformedComment.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | MalformedTextBlock.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | Nested.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | Ordinary.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | TextBlocks.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | UnicodeEscape.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | backtick_names.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | char_and_templates.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | crlf.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | embedded_json.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | fresh_imports.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | kotlin_members.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lex_anchors.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lex_block_nested.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lex_plain.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lex_raw.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lex_slashes_in_string.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lex_template_string.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lex_unterminated_raw.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | lookalikes.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | malformed_unterminated_block.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | malformed_unterminated_string.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | nested_comments.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | ordinary.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | placement_kotlin_imports.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | placement_kotlin_license.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | placement_kotlin_member.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | placement_kotlin_member_existing.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | placement_kotlin_package.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | raw_templates.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| kotlin | script.kts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
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
| rust | chars_and_macros.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | crlf.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | embedded_sql.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | inner_attrs.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | malformed_nested.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | malformed_raw.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | nested_comments.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | ordinary.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | raw_strings.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | crlf.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | embedded_json.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | fresh_imports.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | malformed_multiline.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | malformed_nested.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | nested_comments.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | ordinary.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | raw_strings.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | regex_literals.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| swift | shebang.swift | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | crlf.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | embedded.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | html_comments.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | imports.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | jsx_text.jsx | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | jsx_text.tsx | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | malformed_unterminated_comment.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | malformed_unterminated_template.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | ordinary.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | prologue.js | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | regex.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| typescript | templates.ts | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |

## Notes per case

