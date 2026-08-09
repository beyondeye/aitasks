---
Task: t1427_5_manual_verification_reject_shadow_concerns_suppress_next_rou.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
Strategy: autonomous (auto-verification.md 2a)
---

# p1427_5 — Manual-verification auto-execution record

Retroactive record of what was actually run for each of the 13 checklist items.
All 13 reached `pass`; none were deferred or skipped.

Three verification surfaces were used, in increasing order of fidelity:

1. **CLI / file inspection** — items 1, 2, 3, 4, 13.
2. **Live TUI drive** (real tmux pane → real capture → real modal keystrokes →
   real subprocess → real store file) — items 5, 6, 7, 8, 9.
3. **Real shadow rounds** run by fresh subagents following the production
   producer procedure — items 10, 11, 12. These agents had not read t1427's
   plans, so their compliance with the inlined rule is independent evidence
   rather than self-assessment.

## Execution Log

### Item 1 — test suite + shellcheck (t1427_1)
- Item text: `bash tests/test_shadow_rejected.sh` passes; shellcheck on `aitask_shadow_rejected.sh` clean
- Approach: CLI invocation
- Action run: `bash tests/test_shadow_rejected.sh`; `shellcheck .aitask-scripts/aitask_shadow_rejected.sh`
- Output (trimmed): `Results: 130/130 passed, 0 failed` / `All tests PASSED`, rc 0.
  shellcheck emitted only three `SC1091` *info* notices (not following sourced
  libs). Confirmed as the repo baseline, not a finding: the sibling
  `aitask_shadow_context.sh` produces the same three, and a `-f gcc` run
  filtered of `SC1091` yields nothing.
- Verdict: **pass**

### Item 2 — helper whitelist (t1427_1)
- Item text: `audit-helper-whitelist aitask_shadow_rejected.sh` reports no MISSING touchpoints
- Approach: CLI invocation + positive control
- Action run: `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_shadow_rejected.sh`
- Output (trimmed): empty, rc 0. Because a silent zero-match is
  indistinguishable from a clean pass, the same command was run against
  `aitask_nonexistent_helper.sh` as a positive control: it printed
  `MISSING:1|3|4|6|7`, proving the checker does emit findings and the empty
  result is real.
- Verdict: **pass**

### Item 3 — add/list/remove/prune round-trip (t1427_1)
- Item text: manual smoke round-trip on a scratch task id; `.aitask-shadow/` stays git-ignored
- Approach: CLI invocation in the live repo, scratch id `9999`
- Action run: `add 9999 --producer manual` (two markers, one body containing a
  literal `|`) → `list` → `list --machine` → `remove 9999 r1 r99` → re-`add` →
  `remove 9999 2` (no `r` prefix) → `prune 9999` → `prune 9999` again
- Output (trimmed): `ADDED:2`; `list` printed the body with the
  `<!-- next_id -->` header stripped; `list --machine` round-tripped the
  pipe-laden body intact with the marker line last; `REMOVED:r1` +
  `NOT_FOUND:r99`; the re-add was issued **`r3`, never a reused `r1`**;
  prefix-less `remove 9999 2` resolved to `REMOVED:r2`; `PRUNED:9999` then
  `PRUNED:absent`. `git status --porcelain` was captured before and after and
  was **byte-identical** throughout; `git check-ignore -v` attributed the store
  to `.gitignore:22`.
- Verdict: **pass**

### Item 4 — archive prunes the store (t1427_1)
- Item text: archive a scratch task that has a rejection store and confirm `.aitask-shadow/<id>/` is pruned
- Approach: CLI invocation + a hands-on archive in a throwaway repo
- Action run: `bash tests/test_archive_shadow_prune.sh` (26/26, per-site), then
  a scratch fixture (`setup_fake_aitask_repo` in a temp clone) seeding a real
  store for `t42` **and a decoy for `t77`**, archived with the real
  `aitask_archive.sh 42`
- Output (trimmed): `ARCHIVED_TASK:` + `COMMITTED:567be67`; `.aitask-shadow/42/`
  gone; decoy `.aitask-shadow/77/` intact.
- Note: the first fixture attempt copied the repo's whole `.gitignore` into the
  temp repo, which imported this repo's `aitasks` rule (task data lives on a
  separate branch here) and made archival's commit step fail with
  `paths are ignored`. The prune still fired, but the run was not clean. Fixed
  by appending only the `.aitask-shadow/` rule — with a guard that asserts that
  rule really exists in the real `.gitignore`, so the fixture cannot drift into
  testing a rule the repo does not have.
- Verdict: **pass**

### Items 5, 6, 7, 9 — live picker write path (t1427_2)
- Item text: reject in minimonitor / un-reject via `R` / same in full monitor /
  no-task-id refusal
- Approach: live TUI drive. Scratch probe at
  `scratchpad/probe_live_reject.py`. Everything on the write path is real:
  real tmux pane → `aitask_shadow_capture.sh` → `capture_shadow_text` →
  `parse_concerns` → real `ConcernPickerModal` driven by real keystrokes →
  `ShadowRejectionsMixin.apply_concern_pick_result` → real asyncio subprocess →
  real `aitask_shadow_rejected.sh` → real `rejected.md`. Only the two tmux
  *lookups* were stubbed (which pane is the agent, which is its shadow) —
  exactly the two `tests/test_minimonitor_concern_smoke.py` stubs, for the same
  reason. `AITASK_SHADOW_DIR` was redirected at a temp dir so the repo's own
  store was never touched.
- Action run: 35 assertions across the real `MiniMonitorApp` and the real
  `MonitorApp`
- Output (trimmed): **35/35 passed.** Highlights:
  - `r` → `_state == "rejected"`, renders `[red]✗[/]`, carries the `.rejected`
    dimming class
  - confirming wrote `.aitask-shadow/9001/rejected.md` holding the canonical
    marker line **verbatim** with `producer: picker`, the non-rejected concern
    absent, and the `1 concern(s) rejected — suppressed next round` toast
  - `R` opened `RejectedStoreModal` listing exactly the persisted entry; on
    return the picker was intact
  - **the two-stage contract held**: after the `R` modal's `Enter` the store
    *still contained* the entry, and it was removed only when the **picker**
    was confirmed
  - monitor path identical at `narrow=False`, and monitor's global `r`
    (refresh) / `R` (restart) never fired under the modal
  - `agent-explore-scratch` → task id `None`, `store_unavailable=True`, `R`
    warned instead of opening a list, and confirming produced the
    warning-severity `Rejections not persisted — no task id for this pane`
    with the store root byte-identical
- Verdict: **pass** (all four items)

### Item 8 — `a`/`A` removed, help readable at 24 cols (t1427_2)
- Item text: `a` and `A` no longer do anything in the picker and are absent from both help lines; help stays readable at 24-col width
- Approach: behavioral probe + render-level sweep
  (`scratchpad/probe_aA_dead.py`, `scratchpad/probe_picker_help.py`)
- Action run: pressed `a` then `A` against a live picker with two concerns and
  asserted no row changed `_state`; then pressed `r` and `space` as a
  **positive control**. Separately composited the modal at 40 / 30 / 24 columns.
- Output (trimmed): `a` and `A` left `['none','none']` untouched while `r` →
  `['rejected','none']` and `space` → `['forward','none']` — so "nothing
  happened" is not a probe that failed to deliver keys. No `action_toggle_all` /
  `action_copy_all` anywhere in `monitor/`; neither help string names `a`/`A`.
  At 24 cols the compact line wraps to three rows
  (`↑↓ move · spc fwd · r rej · R list · u raw · ↵ ok · esc`) with
  `_clipped_rows() == []` at every width. `test_concern_picker_modal.py` 47/47.
- Verdict: **pass**

### Item 10 — live two-round suppression (t1427_3)
- Item text: reject a concern, trigger a fresh round, confirm the block omits it and the prose reports `Suppressed N previously-rejected concern(s).`
- Approach: two real shadow rounds by **fresh subagents** following
  `.claude/skills/aitask-shadow/plan-challenge.md` against the same scratch plan
  (`scratchpad/scratch_plan.md`, a deliberately flawed rate-limiter plan),
  differing **only** in the contents of the rejection store for id `9500`
- Action run: round 1 with an empty store → reject one marker line via
  `add 9500 --producer picker` → round 2
- Output (trimmed): round 1 reported *"No previously-rejected concerns were
  found for t9500 (`NO_REJECTIONS`), so nothing was suppressed"* and raised six
  concerns including `[medium | Step 4: cleanup thread]`. Round 2 read the
  printed body and reported verbatim **`Suppressed 1 previously-rejected
  concern(s).`**, and its block omits the cleanup-thread concern while the other
  five return.
- Negative control: round 1's explicit no-suppression statement, produced by the
  same prompt against the same plan, is what makes round 2's omission
  attributable to the store rather than to run-to-run variation.
- Verdict: **pass**

### Item 11 — un-reject makes it return (t1427_3)
- Item text: un-reject the same concern, trigger another round, confirm it returns
- Approach: same harness, third round
- Action run: `remove 9500 r1` → confirmed `NO_REJECTIONS` and a header-only
  store (`<!-- next_id: 2 -->`, so the id was **not** freed for reuse) → round 3
- Output (trimmed): round 3 reported *"ran `aitask_shadow_rejected.sh list 9500`
  — result `NO_REJECTIONS`, so no concerns were suppressed"* and the concern
  **returned** as `[medium | Step 4 sweep thread]`. It came back **reworded** —
  round 1 framed it via test-collection imports, round 3 via `daemon=True` and
  gunicorn preload / autoreload forking. Same substance, different words, which
  is precisely the reworded-match round 2 had to make semantically to suppress
  it.
- Note: the first attempt at this round died on a transient
  `Connection closed mid-response` API error and was simply re-run.
- Verdict: **pass**

### Item 12 — no resolvable task id (t1427_3)
- Item text: run a shadow round for a task with no resolvable task id and confirm the output states suppression was skipped
- Approach: real shadow round by a fresh subagent, no task id in launch args,
  followed window `agent-explore-scratch`
- Output (trimmed): *"No task id was passed to me and the followed window name
  (`agent-explore-scratch`) doesn't match the resolvable pattern, so I could not
  consult the rejection store — suppression was skipped; all concerns below are
  fresh."* All five concerns emitted (fail-open); the failure was never read as
  "nothing was rejected".
- Verdict: **pass**

### Item 13 — docs (t1427_4)
- Item text: `hugo build --gc --minify` clean; the updated pages read coherently and no picker `a`/`A` shortcut references remain
- Approach: CLI invocation + built-HTML anchor resolution + file inspection
- Action run: `cd website && hugo build --gc --minify`; the plan's proven
  whole-tree sweep pattern; an anchor resolver over `website/public/`
- Output (trimmed): build rc 0, 233 pages, only the two pre-existing Docsy
  deprecation warnings (`.Language.LanguageDirection`, `.Site.AllPages` — theme
  code, unrelated). Sweep went **28 → 25 hits**, exactly the three picker lines
  gone; the sole remaining monitor hit is the auto-switch `a`
  (`monitor/how-to.md:242`), classified intentional residual by t1427_4's
  pre-phase. All seven inbound anchors resolve against real ids in the built
  HTML, including the new `#reject-a-concern-so-it-does-not-come-back`.
  `reference.md` changed only its `c` row — no new global `r`/`R` rows, and
  lines 33/45/49 untouched. Documented glyphs, toasts and the
  `Suppressed N previously-rejected concern(s).` line all match source verbatim.
- Note: a first anchor grep searched for `id="…"` and returned nothing, which
  looked like broken anchors. The cause was the grep, not the docs — `--minify`
  emits unquoted attributes (`id=reject-a-concern-…`). Re-run correctly, every
  anchor resolves.
- Verdict: **pass**

## Findings

No defects were found in the t1427 implementation. Every checklist item passed
against the landed code. One pre-existing upstream defect was already recorded
by t1427_4 and is untouched here:
`.aitask-scripts/aitask_shadow_rejected.sh:61`'s header comment documents the
machine format as `REJECTED:<id>|…` while `cmd_list` at `:339` emits
`REJECTED:r<id>|…`.

## Cleanup

Removed at the end of the run:

- `.aitask-shadow/9500/` — `prune 9500` → `PRUNED:9500`; the now-empty
  `.aitask-shadow/` root removed too
- `.aitask-shadow/9999/` — pruned during item 3
- `/tmp/ait_t1427_5_store_*` and `/tmp/ait_t1427_5_tmux_*` probe roots
- the probe's per-PID tmux server (`kill-server`; no stray sockets remain)
- the throwaway archive-smoke repo (self-cleaning `trap`)

Scratch probes are left in the session scratchpad, outside the repo. Verified
after cleanup: `git status --porcelain` empty, `./ait git status --porcelain`
empty.
