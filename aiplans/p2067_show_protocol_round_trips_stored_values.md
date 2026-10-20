---
Task: t2067_show_protocol_round_trips_stored_values.md
Base branch: main
Output branch: main
---

# t2067 — Make the per-record store read lossless

## Context

`agent_sessions.py show <id>` prints `key:value` lines, and
`agent_frozen_ops.parse_show` (behind `store_show`) reads them by stripping each
value, cutting it at its first `str.splitlines` break, and letting a later
`key:value` line override an earlier key. Every action that reads a record through
`store_show` therefore acts on a mangled record: restore (`agent_restore._reread`),
reopen (`reopen_one`), drop / reconcile / freeze backfills (`agent_freeze`). E.g. a
`root` with surrounding whitespace names a different project, and a field holding
`\nstate:live` changes the state those actions read.

t2041 papered over the mismatch for the reopen listing (`agent_reopen._as_shown`
renders each verbatim `list --full` record as `show` prints it and re-parses it).
This task fixes the protocol: `store_show` reads JSON, so an action reads the stored
value, and the listing's render-and-parse step goes away.

## Design decisions

- **JSON form via `show <id> --json`**, printing exactly one `RECORD:<json>` line —
  the same encoding `list --full` already uses (one shared helper). Plain `show`
  keeps its `key:value` text for humans and the shell tests that `sed` it
  (`tests/test_frozenagent_standin_stamp.sh`, `test_session_hook_live.sh`,
  `test_agent_sessions_concurrency.sh`). The read still goes through
  `frozen_ops.store(...)` (seam rule kept).
- **Identifier usability is a reader rule, not a write-time rejection.** Under a
  lossless read, a stored session id of `" "` or `"\nsess"` would become a
  resumable id. One predicate, `frozen_ops.usable_identifier(value)` — non-empty,
  every char printable, no whitespace — decides whether `codeagent_session_id` /
  `task_id` can be launched with. Used by `resume_blocker` / `repick_blocker` /
  `build_resume_argv` / `build_repick_argv` (offer and action share these, so they
  still agree) and by `agent_freeze._backfill_task_ref` (keeps its fail-closed
  "must end up holding a re-pickable task id" guarantee).
  **Write-time rejection: decided NO.** `upsert` from the SessionStart hook would
  then fail the whole record (location, window) over one bad field — worse than a
  stored id the readers refuse; and a hand-edited / legacy store would still need
  the reader rule. No follow-up task.
- **tmux-side window reads must be verbatim too** (review finding, verified).
  `frozen_ops.window_facts` and `pane_facts` strip every field, so once the stored
  window is verbatim, `agent_reopen._rename` (`facts["window"] == final`) and
  `frozen_ops.rename_window_if_stamped` (`after["window"] == final`) compare a
  stripped tmux name against an unstripped `final`: a record whose window is
  `" agent-pick-1847 "` renames successfully, fails verification, and reopen
  returns `REOPEN_FAILED|…|rename` with cleanup; restore's gone-pane rename warns
  and leaves the attempt name. Fix at the source: both readers keep the `window`
  field verbatim (it is a tmux NAME, where spaces are legal; ids / pids / options
  keep their strip). Also `agent_restore`'s gone-pane collision set reads
  `set(out.split())`, which splits names on spaces — use `splitlines()`.
- **Wire hardening:** the reopen listing now carries verbatim `window` / `task_id`
  / `frozen_at` into `GONE:` lines, where they used to arrive break-free.
  `agent_reopen._field` replaces only `\n`; make it drop every `str.splitlines`
  break so a `\r` / ` ` in a window name cannot split a wire line.

## Steps

1. **`.aitask-scripts/lib/agent_sessions.py`**
   - Add `_record_line(rec) -> str` returning `"RECORD:" + json.dumps(vars(rec))`;
     use it in `list --full`.
   - `show`: accept `--json` anywhere in `rest`; take the id as the first
     non-flag argument; with `--json` print `_record_line(rec)`, else the existing
     `key:value` loop.
2. **`.aitask-scripts/aitask_agent_sessions.sh`** — `cmd_show`: validate the id,
   accept an optional trailing `--json` (anything else → `die_usage`), pass it
   through. Update the header verb doc (`show <id> [--json]`, one sentence: the
   lossless single-record form `store_show` reads) and the `usage` line.
3. **`.aitask-scripts/lib/agent_frozen_ops.py`**
   - Factor the RECORD-line decoding out of `store_records` into
     `_decode_record(line) -> dict[str, str] | None` (JSON object → `{str: str}`).
   - `store_show`: `store("show", id, "--json")`; `{}` on rc≠0, and `{}` unless
     exactly one `RECORD:` line decodes (folded stderr noise skipped, as in
     `store_records`). Docstring: values verbatim.
   - Delete `parse_show`; fix `store_records`' docstring (no longer contrasts with
     the parser). Update the module docstring if it names the parser.
   - Add `usable_identifier(value: str) -> bool` with a docstring stating it is THE
     launchability rule offer and action share.
   - `window_facts` / `pane_facts`: strip every field except `window`, which is
     returned as tmux reported it (comment: compared against the stored name, which
     is read verbatim).
4. **`.aitask-scripts/lib/agent_reopen.py`** — delete `_as_shown` and
   `_VERBATIM_FIELDS`; `_frozen_records` uses `store_records` output directly;
   harden `_field` (above).
5. **`.aitask-scripts/lib/agent_restore.py`** — the four functions above use
   `frozen_ops.usable_identifier`; `resume_blocker` docstring notes the rule.
   Gone-pane launch: `existing = set(out.splitlines())` instead of `out.split()`.
6. **`.aitask-scripts/lib/agent_freeze.py`** — `_backfill_task_ref`: both
   `task_id` truthiness checks use `frozen_ops.usable_identifier`.
7. **Tests**
   - `tests/test_agent_sessions.py`: new test — `show --json` is one RECORD line
     equal to the matching `list --full` record, and round-trips hostile values
     verbatim (seed via `upsert --session-id " x\ny "` / window with spaces as the
     CLI allows); plain `show` unchanged.
   - `tests/test_agent_frozen_ops.py`: `store_show` fake answers a RECORD line;
     calls == `[("show", "abc123", "--json")]`; values kept whole (newline,
     surrounding spaces, a `"\nstate:live"` value does not override `state`); `{}`
     for no RECORD line / undecodable / non-object. Swap `parse_show` for
     `usable_identifier` in `PROMISED_CALLABLES`; table test for the predicate.
   - `tests/test_agent_reopen.py`: fake `Store` answers `show … --json` with a
     RECORD line; call-tuple assertions gain `"--json"`.
     `test_the_offer_lists_the_eligibility_restore_applies` stays the parity test:
     whitespace / line-break cases still list `no_session`/`no_task_id` and restore
     refuses identically; the `later_field_overrides` case now expects the record
     **eligible** (stored `sess-1`/`1847` are not overridden) — assert listed
     `ok|ok` and `resume_blocker(store_show(rid)) == repick_blocker(...) == ""`.
     Replace `test_listing_reads_like_show_except_paths` with
     `test_listing_reads_exactly_what_show_reads`: listed record == `store_show`,
     with `window`/`pane_id`/paths all verbatim. Add a `gone_line` test: a window
     with `\r` / ` ` yields one line.
     **Full reopen regression (the review finding):** a gone record whose stored
     window is `" agent-pick-1847 "` → `reopen_one` returns `REOPENED:…|fresh|`
     with the final name verbatim and the World window carries it; and the
     stranded/adopt route with the same name commits. Red-proof: run each against
     the pre-fix `window_facts` (temporarily stripping) and confirm it fails with
     `rename`, then restore.
   - `tests/test_agent_frozen_ops.py`: `window_facts` / `pane_facts` return a
     spaced window verbatim while ids/options are still stripped;
     `rename_window_if_stamped` verifies `True` for a spaced final name.
   - `tests/test_agent_freeze.py`: fake `_dispatch` `show` answers RECORD when
     `--json` is given; add a `_backfill_task_ref` case: stored task id `" "` →
     raises `OSError` (fail-closed preserved).
   - `tests/test_agent_restore.py`: blocker cases for `" "`, `"\nsess"`,
     `" x"` → `no_session` / `no_task_id`.
8. Step 9 (Post-Implementation): archival per the workflow.

## Verification

```bash
python3 -m pytest -q tests/test_agent_sessions.py tests/test_agent_frozen_ops.py \
  tests/test_agent_reopen.py tests/test_agent_freeze.py tests/test_agent_restore.py
bash tests/test_frozenagent_standin_stamp.sh
bash tests/test_agent_sessions_concurrency.sh
bash tests/test_ide_frozen_offer.sh
shellcheck .aitask-scripts/aitask_agent_sessions.sh
bash tests/run_all_python_tests.sh   # last line verdict
```
Manual: `./.aitask-scripts/aitask_agent_sessions.sh show <id> --json` on a real
record prints one RECORD line; `show <id> --bogus` exits 2.

## Risk

### Code-health risk: medium
- Every `store_show` consumer (restore, reopen, drop, reconcile, freeze backfills)
  now reads verbatim values, so `window` / `pane_id` / `last_error` with stray
  whitespace reach tmux targets and comparisons unstripped. These are store-written
  from tmux facts, and verbatim is the true value, but the change is wide · severity: medium · → mitigation: none (covered by the plan's own suite runs in Verification)
- Readers that compared stripped tmux values against stripped store values now see
  a verbatim store value; any comparison not moved to verbatim on the tmux side
  fails (found and fixed: window name in rename verification and the restore
  collision set; pane ids / session names are not store-vs-tmux comparisons of
  free text) · severity: medium · → mitigation: none (full reopen regression test in the plan)
- A test fake left answering `show` in text form makes `store_show` return `{}`;
  that surfaces as loud `no_record` failures, not silent passes · severity: low · → mitigation: none (Verification runs every faking suite)

### Goal-achievement risk: low
None identified.
