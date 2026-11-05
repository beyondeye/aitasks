# Sitrep harvest fixtures (t2175_2)

Inputs for `tests/test_sitrep_harvest.py` and `tests/test_sitrep_harvest.sh`.

**Every file here is synthetic.** Real frozen captures and agent transcripts hold
other projects' content and conversation text, so they are not committed. Each
fixture was written by hand to reproduce the layout measured on real Claude Code
captures (`~/.config/aitasks/frozen/<id>/capture.txt`, November 2026):

- the closing message starts with `● ` and its continuation lines are indented
  two spaces;
- tool calls are `● Name(…)` with output under `  ⎿  `;
- the workflow-end banner is indented two spaces, its field lines four;
- lines are padded with trailing spaces to the terminal width;
- inline code is rendered without backticks and `**bold**` without asterisks,
  and the capture renders some spaces as NBSP (U+00A0);
- the pane ends with the prompt box and status-bar lines.

| file | shape |
|---|---|
| `pick_complete_nofollowups.txt` | Complete run, `follow-ups created: none`, captured form |
| `pick_complete_piped.txt` | the SAME run as the agent pipes it: raw markdown, banner in a ```` ```text ```` fence |
| `pick_complete_followups.txt` | Complete run with local and cross-repo follow-ups, the list wrapped onto a continuation line |
| `pick_stopped_a.txt` / `pick_stopped_b.txt` | two Stopped runs with identical banner fields and different prose |
| `pick_stopped_marker.txt` | a Stopped run whose capture shows the harvest call's `HARVEST_RUN:` first output line before the closing message |
| `explore_created.txt` | an explore agent's `aitask_create.sh` calls with their `Created:` lines |
| `raw_no_banner.txt` | a raw agent: no banner, nothing to harvest |
| `truncated_top.txt` | the capture starts mid-message (no `●` line before the banner) |
| `truncated_banner.txt` | the capture ends after the banner's first line |
| `trail_mention.txt` | trail handles inside and outside a wrap-up passage |
| `joined_banner.txt` | a Complete banner shown WITHOUT its text fence: fields joined onto the first line, terminal-wrapped (t2175_6; parsed since `PARSER_REV` 2) |

## `corpus/` — promoted review cases (t2175_6)

Each `corpus/<name>/` is a harvest review case promoted from a local sitrep
store with `ait sitrep case export <case> --out <dir>`: `input.txt` (the raw
input) and `case.json` (what the current parser must extract: `expect_class`,
`expect_refs`, `expect_kinds`; plus `reasons_before`, the `gap` it illustrates
and the fixing `parser` revision). `tests/test_sitrep_corpus_fixtures.py` runs
`case check-fixture` over every directory.

Raw cases stay in the git-ignored store (`.aitask-sitrep/raw/`). A case is
committed here only after review and redaction: remove other projects' content
and conversation text from `input.txt`, then re-run `check-fixture` on the
redacted copy.

| case | gap |
|---|---|
| `corpus/joined_banner/` | banner shown without its text fence (synthetic, from workflow-end.md's fence rule) |

`harvest_other_agent_captures` (a follow-up of t2175_2) replaces the
Claude-Code-only assumptions with fixtures for other code agents once finished
captures from them exist.
