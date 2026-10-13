# Matrix: shfmt

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Safety columns (must be 0): FP-writable, Docstring-write, Silent-uncertain, Record-corruption. Recall/cost: Missed-writable, Missed-comment (a plain comment line not classed Comment), Read-mismatch, Over-refusal, Placement. Fidelity and Behaviour count applied edits that changed other bytes / program behaviour. Definitions: the t1954 shared design, *Metrics*.

## Summary by language

| lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | 67 | 67 | 2 | 0 | 1 | 0 | 0 | 0 | 6 | 8 | 0 | 0 | 0 | 67 pass / 0 fail | 20 / 9 / 0 / 0 |
| python | 64 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| go | 21 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| kotlin | 26 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| typescript | 19 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| java | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| rust | 10 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |
| swift | 11 | 0 (unsupported) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0 / 0 / 0 / 0 |

## Per case

| lang | case | status | FP-W | DS-W | SIL-U | REC-C | MISS-W | MISS-C | READ-M | OVER-R | PLACE | FID | BEH | range | ops a/r/u/nm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bash | bash_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | bom_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | case_patterns.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | crlf.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | crlf_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 2/0/0/0 |
| bash | edits_members.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 2/3/0/0 |
| bash | edits_uncertain.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 3:5: unclosed here-document `EOF`) | 0/2/0/0 |
| bash | embedded.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | exec_mode_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | fresh_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | heredoc_in_arith.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | heredoc_in_backtick_subst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | heredoc_matrix.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/1/0/0 |
| bash | latin1_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:6: invalid UTF-8 encoding) | 0/1/0/0 |
| bash | lex_arith_command.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_arith_or_subshell_across_lines.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:10: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_arith_shift.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_backtick_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_case_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:13: not a valid arithmetic operator: `"`) | 0/0/0/0 |
| bash | lex_cmdsubst_of_subshell_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:11: not a valid arithmetic operator: `a`) | 0/0/0/0 |
| bash | lex_comment_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_continuation_line_is_code.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_delayed_by_continuation.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_delayed_by_spanning_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_dollar_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_double_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_double_subshell.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:7: not a valid arithmetic operator: `x`) | 0/0/0/0 |
| bash | lex_escaped_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_here_string.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_ansi_c_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_body_continuation.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_body_escaped_backslash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_double_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\"F`) | 0/0/0/0 |
| bash | lex_heredoc_escape_in_quoted_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `E\x4fF`) | 0/0/0/0 |
| bash | lex_heredoc_in_backticks.sh | ok | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_in_cmdsubst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_locale_delimiter.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_partly_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_quoted_no_joining.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_strip_continuation.sh | ok | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_heredoc_strip_quoted.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_param_expansion_in_quotes.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_param_expansion_literal_brace.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_param_expansion_literal_braces.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_param_expansion_nested.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_param_expansion_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_param_expansion_unterminated.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:6: reached EOF without matching `${` with `}`) | 0/0/0/0 |
| bash | lex_param_hash.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_plain.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_single_quote_spanning.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_two_heredocs.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | lex_unterminated_heredoc.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:5: unclosed here-document `EOF`) | 0/0/0/0 |
| bash | lex_unterminated_quote.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 1:3: reached EOF without closing quote `"`) | 0/0/0/0 |
| bash | lookalikes.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 0/0/0/0 |
| bash | malformed_unterminated_single.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:6: reached EOF without closing quote `'`) | 0/0/0/0 |
| bash | malformed_unterminated_subst.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:3: reached EOF without matching `$(` with `)`) | 0/0/0/0 |
| bash | nonascii.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 3/1/0/0 |
| bash | nonl_edit.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | ordinary.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 3/1/0/0 |
| bash | placement_bash_existing.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | placement_bash_header.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | placement_bash_noheader.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | placement_bash_noshebang.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | placement_bash_unit_first.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | pass (provider is the oracle (shfmt)) | 1/0/0/0 |
| bash | syntax_error_lexically_valid.sh | ok | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | pass (oracle shfmt failed: shfmt cannot parse: 2:1: `if` statement must end with `fi`) | 0/0/0/0 |
| go | bom.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | cgo_preamble.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | crlf.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | embedded_sql.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | fresh.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | go_members.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_anchors.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| go | lex_block.go | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
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
| java | CharsAndStrings.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | Crlf.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | EmbeddedSql.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | Fresh.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | MalformedComment.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | MalformedTextBlock.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | Nested.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| java | NonAscii.java | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
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
| kotlin | nonascii.kt | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
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
| python | latin1_member.py | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
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
| rust | chars_and_macros.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | crlf.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | embedded_sql.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | inner_attrs.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | malformed_nested.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | malformed_raw.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | nested_comments.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | nonascii.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | ordinary.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
| rust | raw_strings.rs | unsupported:language | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a — not exposed | 0/0/0/0 |
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

- `bash/latin1_edit.sh`
  - over-refusal: valid file uncertain at line 2 (2:6: invalid UTF-8 encoding)
  - refusal: got "uncertain@2", want ""
  - op 1 (annotate member= source=src/latin1.sh stamp=@2026-02-02/bbbbbbbbbb): outcome "refused:uncertain", want "applied"
  - op 1 (annotate member= source=src/latin1.sh stamp=@2026-02-02/bbbbbbbbbb): records after differ: missing line=3 member= key=covers value=src/latin1.sh stamp=@2026-02-02/bbbbbbbbbb origin=comment
- `bash/lex_arith_or_subshell_across_lines.sh`
  - over-refusal: valid file uncertain at line 1 (1:10: not a valid arithmetic operator: `a`)
- `bash/lex_backtick_spanning.sh`
  - policy divergence: line 2 classed Comment (a real comment the M2.2 policy never treats as an annotation line)
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `bash/lex_cmdsubst_of_subshell.sh`
  - over-refusal: valid file uncertain at line 1 (1:13: not a valid arithmetic operator: `"`)
- `bash/lex_cmdsubst_of_subshell_quoted.sh`
  - over-refusal: valid file uncertain at line 1 (1:11: not a valid arithmetic operator: `a`)
- `bash/lex_continuation_line_is_code.sh`
  - policy divergence: line 2 classed Comment (a real comment the M2.2 policy never treats as an annotation line)
  - read: extra line=2 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
- `bash/lex_double_subshell.sh`
  - over-refusal: valid file uncertain at line 1 (1:7: not a valid arithmetic operator: `x`)
- `bash/lex_heredoc_escape_in_quoted_delimiter.sh`
  - over-refusal: valid file uncertain at line 1 (1:5: unclosed here-document `E\x4fF`)
  - refusal: got "uncertain@1", want ""
- `bash/lex_heredoc_in_backticks.sh`
  - silent-uncertain: expect uncertain, got certain
- `bash/lex_heredoc_strip_continuation.sh`
  - FP-writable: line 4 classed Comment (look-alike/read-only)
  - read: extra line=4 member= key=covers value=x stamp=@2026-01-01/0123456789 origin=comment
  - FP-writable: look-alike/read-only line 4 read as a comment annotation
- `bash/syntax_error_lexically_valid.sh`
  - over-refusal: valid file uncertain at line 2 (2:1: `if` statement must end with `fi`)
  - refusal: got "uncertain@2", want ""
