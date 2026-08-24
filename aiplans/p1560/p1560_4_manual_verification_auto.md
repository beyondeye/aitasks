---
Task: t1560_4_manual_verification_serialize_step9_merge.md
Parent Task: aitasks/t1560_serialize_step9_merge_across_concurrent_tasks.md
Archived Sibling Plans: aiplans/archived/p1560/p1560_1_merge_mutex_and_broker_script.md, aiplans/archived/p1560/p1560_2_wire_step9_across_rendered_surfaces.md, aiplans/archived/p1560/p1560_3_document_merge_mutex_and_audit_merge_paths.md
Base branch: main
Output branch: main
---

# t1560_4 — Auto-verification execution record

Strategy: **autonomous** (approach picked per item, executed inline, recorded here).

## Fixture

A throwaway git repo and lock base under the session scratchpad, driven from
**real tmux panes on the dedicated `ait` socket** so every holder carries a
genuine session anchor (`lib/pid_anchor.sh::get_session_anchor_pid` →
`ait_tmux_self_pane_pid`). The first attempt used the `default` socket and every
`begin` returned `NO_SESSION_ANCHOR` — the gateway's same-server guard doing its
job, and itself a small confirmation of the anchor precondition.

- repo: `<scratch>/mv1560/repo` — `main` plus `aitask/tA` (clean),
  `aitask/tC1` / `aitask/tC2` (mutually conflicting on `shared.txt`), `aitask/tW`
  (+ a real worktree at `<scratch>/mv1560/aiwork/tW`)
- `AITASKS_LOCK_DIR=<scratch>/mv1560/locks` — an isolated lock base. The
  `.ait_merge_test_seams` marker was **never** created, so no test seam was
  active: every result below came from the shipped code path.
- panes: tmux session `mv1560` on socket `ait`

## Execution Log

### Item 2 — WAITING progress visible on stderr in a live terminal

- Approach: TUI/terminal interaction — two real panes, capture-pane sampled over time.
- Action: pane 1 `begin tA main aitask/tA`; pane 2 `begin tB main aitask/tC1 --wait-secs 12`.
- Output: pane 2 accumulated `WAITING:tA:0`, `:3`, `:5`, `:7`, `:9` roughly 2s
  apart while the holder was live, terminating in `BUSY:tA:12`. Progress on
  stderr, single verdict on stdout.
- Verdict: **pass** — a long queue reads as queued, not hung.

### Item 3 — real conflict-parked merge

- Approach: drive the real conflict end to end across two panes.
- Action / output:
  1. pane 1 `begin tC1` → `MERGE_OK`, `finish tC1` → `RELEASED`
  2. pane 1 `begin tC2` → `MERGE_CONFLICT:shared.txt`; `status` → `HELD:tC2|<pid>|alive|main|…`;
     real tree shows `UU shared.txt`, `.git/MERGE_HEAD` present, conflict markers in place
  3. pane 2 `begin tD --wait-secs 4` → `WAITING:tC2:0`, `WAITING:tC2:3`, `BUSY:tC2:5`;
     A's conflicted tree completely untouched
  4. pane 1 `abort tC2` → `ABORTED`; tree clean, `shared.txt=C1`, `HEAD=main`
  5. pane 2 `begin tD` → `MERGE_OK`
- Verdict: **pass** — the retention across a parked conflict is the fix, and it holds.

### Item 4 — stale-holder reclaim, live holder never displaced

- Approach: five real waiter panes + `tmux kill-pane` on the holder.
- Action / output:
  - **Live half:** with holder `tD` alive, all five waiters reported `WAITING:tD:0`,
    and `force-release --yes --expect <token>` returned
    `REFUSED_LIVE_HOLDER:tD:1750576` with the lock still `HELD`.
  - **Dead half:** `kill-pane` on the holder → **exactly one** waiter (`W4`)
    reclaimed and reported `MERGE_OK`; the other four reported `BUSY:W4:26`.
    Zero git-level errors, no second entrant.
- Verdict: **pass**.

### Item 5 — wedge path and recovery

- Approach: CLI, with `env -u TMUX -u AIT_AGENT_PID` to remove every anchor source.
- Action / output:
  - `begin tA main aitask/tA` → `NO_SESSION_ANCHOR`, exit 0, `status` → `FREE`
    (refused **before** acquiring; nothing left behind).
  - Both remedies are named in the rendered procedure
    (`merge-broker-default.md` § `begin / NO_SESSION_ANCHOR`): "set `AIT_AGENT_PID`
    to a live process, or run inside a tmux pane".
  - Planted wedge (anchored to a `sleep`, then killed): `status` →
    `HELD:tA|1743667|dead|main|…`. Dry run printed lock dir, holder, anchor +
    liveness, acquired-at, residue → remedy, the `rmdir` guard hint, and a
    copy-verbatim armed command; stdout carried only `DRY_RUN:<token>`.
  - Negative control: `--expect 0000…` → `HOLDER_CHANGED:tA`, lock still `HELD`.
  - Armed command with the printed token → `FORCE_RELEASED:tA` → `status` `FREE`.
- Verdict: **pass**.

### Item 7 — merge-approval question at realistic pane widths

- Approach: render the question text extracted verbatim from the rendered Step 9
  into real tmux panes at 163 / 120 / 100 / 80 columns and read it back.
- Output: at 163, 120 and 100 columns the question renders as one complete line —
  `Proceed with merge of code changes into the main branch (plan header)? Queued
  behind t1560.` At 80 only the trailing clause wraps. The pinned phase anchor
  leads the string and the queued-behind clause is appended, so no wrap can push
  the anchor off-screen.
- Verdict: **pass**. Residual: rendered through a real terminal but not through
  Claude Code's own AskUserQuestion widget, whose word-wrap and padding differ.

### Item 8 — every broker verdict has a branch; no in-flight exit reaches cleanup

- Approach: file inspection + coverage cross-check against the live vocabulary.
- Action / output:
  - `aitask_merge_task.sh --list-verdicts` cross-checked against
    `SKILL-default.md` Step 9 + `merge-broker-default.md`: every `begin` /
    `finish` / `abort` / `cleanup` / `status` token is present. Only
    `force-release` tokens are absent, and deliberately so — it is a human
    recovery verb, excluded at `tests/test_merge_broker_rendered_verdicts.sh:116`
    and documented on the website locks page instead.
  - Read the § `Re-entry — release decision` table: every row whose `continues-to`
    is `stop-in-flight` or `re-run` carries `cleanup: no`; only the two rows
    continuing to `archival` carry `--task-complete`.
  - `bash tests/test_merge_broker_rendered_verdicts.sh` → 25/25.
- Verdict: **pass**.

### Item 9 — monitor / minimonitor classify the merge-approval prompt

- Approach: render the widget shape (chip boundary + question) in real tmux panes,
  capture, and run the shipped classifier over the capture.
- Action / output: `workflow_phase.phase_from_screen(capture, "claude")` returned
  `('POSTIMPL', 'WAITING', 'merge_approval anchor inside the current question
  block')` at all four widths. Two negative controls both returned `None`:
  rewording the anchor, and removing the `☐` chip (i.e. not a live widget), so the
  pass is not vacuous. `bash tests/test_workflow_phase_prompt_drift.sh` → 17/17.
  `minimonitor_app.py` and `review_loop.py` consume this same module, so both
  surfaces share the verdict.
- Verdict: **pass**. Residual: the widget was reproduced faithfully rather than
  emitted by a live agent CLI at Step 9.

### Item 10 — POSTIMPL resume after an in-flight verification exit

- Approach: real branch + real worktree in the fixture, driven across two panes.
- Action / output:
  - `begin tW main aitask/tW` → `MERGE_OK:2e9e33a…`
  - in-flight exit: `cleanup tW tW` (no flag) → `CLEANUP_REQUIRES_COMPLETION`
    (refused, changed nothing); `finish tW` → `RELEASED`
  - `aitask/tW` still present at `2e9e33a`; `aiwork/tW` worktree still registered
    and on disk; lock `FREE`
  - resume from a **different** pane: `begin tW` → `MERGE_OK:2e9e33a…` — same sha,
    no new commit ("already up to date"), lock re-`HELD`
  - positive control: `cleanup tW tW --task-complete` → `CLEANED`, branch and
    worktree both removed — so the refusal above discriminates rather than
    always-refusing.
- Verdict: **pass**.

### Item 12 — no real repository named, no diffviewer in a TUI list

- Approach: file + rendered-page inspection of both changed pages.
- Output: zero `diffviewer` hits on either page; no list-of-TUIs (the only TUI
  mention is "the board TUI", singular); no external URLs, no `github.com` /
  `gitlab.com` / sibling-directory paths, no real repository names.
- Verdict: **pass**.

### Items 1, 6, 11 — left pending for the interactive loop

- **1** (two REAL agent sessions to Step 9): needs two full agent runs. The
  mechanism it targets was proven live in items 2/3/4 with real tmux panes and
  real session anchors, but not with two agents driving Step 9.
- **6** (no permission prompt from a skill): the whitelist entry
  `Bash(./.aitask-scripts/aitask_merge_task.sh:*)` is present in
  `.claude/settings.local.json`, `seed/claude_settings.local.json`,
  `.codex/rules/default.rules`, `seed/codex_rules.default.rules` and
  `seed/opencode_config.seed.json`, the prefix matches the invocation form the
  rendered Step 9 uses, and the broker ran from this Claude Code session with no
  prompt observed. Whether a prompt **UI** appeared is only observable by the
  human at the terminal, and this session's permission mode is not knowable from
  inside it — so the verdict is theirs.
- **11** (read the two pages in a browser): the site builds clean
  (`hugo build --gc --minify`, 237 pages, rc=0) and both pages were read as
  served. The locks page carries `The merge mutex` → `What the merge mutex
  excludes` (the table), `Before a merge can start: the session anchor` (the
  precondition) and `Recovering a stuck merge mutex` (the numbered ladder), all
  three in the sidebar TOC; `parallel-development` carries a `Serialized
  Merge-Back` section that cross-links to both. The Chrome extension is not
  connected in this session, so the actual browser rendering — table overflow in
  particular — was not seen.

## Cleanup

- tmux session `mv1560` on socket `ait` — killed.
- `hugo server` on port 1319 — stopped.
- scratch repo, worktree and lock base under the session scratchpad — removed.
- No file outside `aitasks/` (the checklist) and this plan was mutated.
