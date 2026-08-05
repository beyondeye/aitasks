---
Task: t1427_reject_shadow_concerns_suppress_next_round.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# t1427 — Reject shadow concerns; suppress them next review round (decomposition plan)

### Pre-phase (risk mitigations)

1. **[contended_append_negative_control]** Child 1's `tests/test_shadow_rejected.sh`
   MUST include a two-writer contention test: fire two concurrent
   `aitask_shadow_rejected.sh add` invocations against the same task store and
   assert **both** entries land with distinct ids (no lost update), proving the
   `registry_lock` + `ait_atomic_render` composition. The test must be able to
   fail: verify it exits 1 when the lock acquisition is bypassed (negative
   control run documented in the child plan).
2. **[rejections_only_result_negative_control]** Child 2's callback test suites
   (`tests/test_monitor_concern_action.py`,
   `tests/test_minimonitor_concern_action.py`) MUST each assert that a
   `ConcernPickResult` with **empty `forwarded` and non-empty `rejected`**
   still triggers rejection persistence and does not early-return — pinning
   the explicit `is None` check against a truthiness regression.

## Context

The concern picker (`c` in `ait monitor` / `ait minimonitor`) lets the user
forward shadow concerns to the code agent but offers **no way to reject one**.
Every re-review re-raises everything, so the user re-triages the same dismissed
items each round. Nothing in the pipeline can express "already rejected": the
picker is pure-UI with zero persistence, dedup is per-block and in-memory,
`Concern` has no stable cross-round identity, and the shadow has no round
memory. Matching a fresh concern against a rejected one must therefore be
**semantic and performed by the shadow agent** (it re-words bodies between
rounds), backed by a **durable per-task rejection store** consulted by every
producer before it emits its concern block.

This is the substrate task; t1159 consumes it as the "dismiss" arm of its triage
loop (reverse pointer recorded there) and must not re-implement rejection.

**User decisions (recorded at planning):**
- Decompose into child subtasks (store-first, spike-first ordering).
- Un-reject is **TUI-only**: in-modal toggle for same-session mis-press plus a
  picker-side view of persisted rejected items with un-reject keys. The helper's
  `remove` subcommand exists as machinery invoked by the TUI, but is **not
  documented as a user-facing CLI**.
- Store is **pruned on archive** (own-root safety check, sharing the mutation
  lock as a defensive safeguard), and a separate follow-up task is created to
  evaluate an appropriate pruning procedure for `.aitask-gates/` (which
  currently grows monotonically).
- The picker's `a`/`A` **bulk shortcuts are removed entirely** — only per-row
  forward/reject actions remain, so rejection state is never overridden by a
  bulk action.
- **No stale-data UI conflict handling or refresh behavior**: concurrent
  editing of the store across UI sessions is out of scope.

## Architecture (binding for all children)

### Store: `.aitask-shadow/<task_id>/rejected.md`

- Bare task id, no `t` prefix (`1427`, `1427_2`) — mirrors `.aitask-gates/`.
- Repo-root-relative, lazy `mkdir -p` by the writer, git-ignored, never
  committed. Gitignore rule installed via a new `setup_shadow_store_gitignore()`
  in `aitask_setup.sh` modeled on `setup_gate_logs_gitignore` (lines ~1956–1987:
  `grep -qxF` idempotence, rationale comment, best-effort auto-commit), called
  right after it in the main setup sequence (~line 3719). The repo-root
  `.gitignore` also gets the line directly in the same commit.
- File format — markdown the shadow reads back as prompt context (AgentCrew
  precedent: markdown for prompt content). One entry block per rejection:

  ```markdown
  ### r<N> | <ISO-8601 UTC> | producer: <name|unknown>
  - [<priority> | <region>] <body>
  ```

  `r<N>` is a monotonic entry id (max+1). The canonical marker line is stored
  verbatim so the shadow has the full text to match against.

### Helper: `.aitask-scripts/aitask_shadow_rejected.sh`

Invoked by path (shadow-helper convention). Sources `terminal_compat.sh`,
`task_utils.sh`, `lib/registry_lock.sh`, `lib/atomic_write.sh`. Task-id
validation identical to `aitask_shadow_context.sh` (strip leading `t`,
`^[0-9]+(_[0-9]+)?$`, die on malformed — the one hard error).

Subcommands:
- `add <task_id> [--producer <name>]` — canonical marker lines on stdin (one
  per line; each must match the `- [` marker shape; producer sanitized at the
  write site: no `|` or newline). Locked read-modify-write. Output `ADDED:<n>`.
- `list <task_id> [--machine]` — no lock (atomic rename gives whole-old-or-new
  reads). Default prints the store file verbatim (shadow prompt context);
  `--machine` emits `REJECTED:<id>|<ts>|<producer>|<marker line>` per entry
  (marker line **last** — it contains `|`; parse with `split('|', 3)`).
  `NO_REJECTIONS` sentinel when empty/missing. Always exit 0 for resolution
  outcomes (shadow_context.sh line-protocol convention).
- `remove <task_id> <id>...` — locked RMW; outputs `REMOVED:<csv>` and/or
  `NOT_FOUND:<csv>`. TUI-invoked only (un-reject machinery).
- `prune <task_id>` — deletes `.aitask-shadow/<task_id>/` with an own-root
  realpath prefix check (aitask_explain_cleanup.sh pattern). Called from
  `aitask_archive.sh` at archive time, best-effort. **Lock-coordinated with
  `add`/`remove`**: the lock dir (`rejected.md.lockd`) lives *inside* the
  directory being pruned, so an unlocked delete could yank the mutex from a
  mid-write mutation and discard its rename. Prune therefore (1) acquires the
  same registry lock first — on busy it exits 3 (`LOCK_BUSY`), **deleting
  nothing**; (2) under the lock, removes the store content but **not** the
  held `.lockd`; (3) releases the lock (which removes the `.lockd`); (4)
  finishes with plain `rmdir` — never `rm -rf` — so if a concurrent waiter
  re-created a lock in the meantime the dir is simply left behind (best-effort,
  re-prunable). A post-prune `add` lazily recreating the dir is accepted and
  documented: prune runs at archival, the recreated dir is re-pruned by any
  later prune, and resurrection is bounded to explicitly re-added entries.

Concurrency contract (`ait monitor` and `ait minimonitor` can both be open):
every mutation holds `registry_lock_acquire "<store>.lockd" <timeout>` (mkdir
mutex, owner-token release, dead-PID-only steal) and lands through
`ait_atomic_render` (every fallible renderer command `|| return 1`). Never an
open-coded mktemp-then-mv. Exit codes copy `aitask_agent_marks.sh`: 0 ok,
2 usage, 3 `LOCK_BUSY` (nothing written), 4 error.

Whitelist: producers reference the helper from SKILL.md files, so register via
`./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist
aitask_shadow_rejected.sh` (covers all 5 touchpoints, alphabetical insertion
after `aitask_shadow_context.sh`).

### Picker tri-state and dismiss contract

- `_ConcernRow` gains a tri-state (none / forward / rejected), mutually
  exclusive, replacing the `_selected` bool. Glyphs: `☐` none,
  `[bold yellow]☑[/]` forward, `[red]✗[/]` rejected (single-width — keeps
  `_NARROW_PREFIX_COLS = 8` valid). New CSS class `rejected` (muted/dim red).
  `Space` toggles forward (clears rejected); `r` toggles rejected (clears
  forward) — both handled in `_ConcernRow.on_key`.
- **Bulk shortcuts removed entirely** (user decision): the `a` (toggle-all
  actionable) and `A` (copy-all) bindings, `action_toggle_all`,
  `action_copy_all`, their help-string entries, and their tests
  (`test_copy_all_dismisses_with_every_concern`, the toggle-all suite) are
  **deleted**, so no bulk action can ever override per-row rejection state.
  The picker offers only per-row forward/reject plus confirm/cancel.
- New named result in `monitor_shared.py`:
  `ConcernPickResult(forwarded: list[Concern], rejected: list[Concern],
  unrejected: tuple[str, ...])` — `unrejected` carries store entry ids. The
  modal dismisses with `ConcernPickResult | None` (None on Esc/Cancel). All
  dismiss sites (confirm, cancel, button handler) and the class docstring
  change together; both `_on_concerns_picked` callbacks (`monitor_app.py`,
  `minimonitor_app.py`) switch from truthiness (`if not selected`) to an
  explicit `is None` check.
- **Rejected-store view** (`R` in the picker): the app pre-fetches
  `list --machine` entries at `action_pick_concerns` time and passes them into
  `ConcernPickerModal`; `R` pushes a new `RejectedStoreModal` on the App
  (pattern: `action_inspect_unrecovered` / `ConcernBlockInspectModal`) showing
  persisted entries with a per-row un-reject toggle; its dismissal feeds the
  picker's `_unreject_ids`, returned in the final result. The modal stays
  pure-UI — all disk I/O is app-side. **Out of scope** (user decision):
  stale-data conflict handling and refresh behavior for the pre-fetched
  entries — concurrent editing of the same store across UI sessions is not
  handled; the prune/mutation lock is the only cross-process safeguard.
- Persistence wiring (both apps): on result, forwarded → clipboard payload +
  notify (unchanged); rejected → resolve
  `task_id = self._task_cache.get_task_id_for_pane(snap.pane)` and invoke the
  helper `add` (subprocess off the event loop), rendering each concern with a
  new shared `concern_marker_line(c)` extracted in `concern_parser.py` (also
  used by `build_clipboard_payload` — one canonical renderer); unrejected →
  helper `remove`. **Unresolvable task id is a visible refusal, never a silent
  no-op**: notify "Rejections not persisted — no task id for this pane", and
  the `R` view shows a "no task id" notice instead of entries.

### Producer-side suppression rule

The rule lives in `concern-format.md` (source of truth) **and inlined in each
producer** — `plan-challenge.md`, `plan-assumptions.md`,
`plan-diagnose-errors.md`, `impl-challenge.md` — because Step 2 context fetch is
optional and a context-fetch-only design has an unreachable trigger. Rule
content (common wording, placed as a pre-emit directive at the head of each
emit step plus a bullet in the rules list):

> Before emitting the block, if a source task id is known, run
> `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>`. Drop any fresh
> concern that is **substantively the same** as a rejected entry, even when
> reworded. Report `Suppressed N previously-rejected concern(s).` in the prose
> before the block whenever N ≥ 1. When **unsure** whether a fresh concern
> matches a rejected one, **keep it and say why** (fail-open — consistent with
> `needs_addressing()`). When no task id is resolved, state that rejection
> suppression was skipped.

Drift guards: a third test class `TestProducerRejectionSuppressionRule` in
`tests/test_concern_parser.py`, one-for-one mirror of
`TestProducerRegionRequiredRule` (module-level predicate matching two collapsed
substrings, e.g. `"previously-rejected"` + `"aitask_shadow_rejected.sh list"`;
reuse `SHADOW_DIR`/`PRODUCER_MARKER`/`KNOWN_PRODUCERS` by reference; duplicate
`test_producer_set_is_the_known_set`; offenders test; negative control that
mutates no repo file). Extend `TestRenderedShadowDocsKeepTheGuarantees` with
the rendered-tree check for the new rule. `SKILL.md.j2` Step 2 gains a sentence
noting that resolving the task id also enables rejection suppression;
regenerate goldens + run `aitask_skill_verify.sh` in the same commit.

Producers live **only** in the Claude tree (per `concern-format.md`), so no
cross-agent skill port tasks are needed; the whitelist apply covers the Codex /
OpenCode permission surfaces.

### Lifetime

`prune` on archive: `archive_parent` and `archive_child` in
`aitask_archive.sh` call
`"$SCRIPT_DIR/aitask_shadow_rejected.sh" prune "$task_num" 2>/dev/null || true`
after lock release (best-effort; archival never blocks on it — a `LOCK_BUSY`
prune leaves the store in place, and any later prune of the same id can finish
the job). Reasoning: a
rejection is scoped to the task under review and is meaningless once the task
archives; pruning at the archival seam keeps the store self-cleaning, unlike
`.aitask-gates/` — whose pruning is deliberately out of scope here and covered
by the follow-up task below.

## Children to create (post-approval, spike-first)

Children auto-depend on prior siblings (sequential).

1. **t1427_1 `rejection_store_helper`** — the substrate spike:
   `aitask_shadow_rejected.sh` (add/list/remove/prune), store format,
   `setup_shadow_store_gitignore()` + root `.gitignore` line, archive-time
   prune hooks in `aitask_archive.sh`, whitelist registration, bash tests
   (`tests/test_shadow_rejected.sh`): add/list/remove round-trip, machine
   protocol with `|`-laden bodies, malformed-id refusal, LOCK_BUSY path, a
   **two-writer contention test** proving no lost update, prune own-root
   refusal (negative control), **prune-vs-add lock coordination** (prune
   returns `LOCK_BUSY` and deletes nothing while an `add` holds the lock),
   each regression proven able to exit 1.
2. **t1427_2 `picker_reject_tristate`** — `_ConcernRow` tri-state + `r` key,
   removal of the `a`/`A` bulk actions (bindings, action methods, help
   entries, tests), `ConcernPickResult` dismiss contract, `RejectedStoreModal`
   + `R` view, both app callbacks + persistence wiring + task-id refusal
   notice, `concern_marker_line()` extraction, help-string retuning (readable
   down to 24 cols), updates to `tests/test_concern_picker_modal.py`,
   `tests/test_monitor_concern_action.py`,
   `tests/test_minimonitor_concern_action.py` + new tri-state/view tests.
3. **t1427_3 `producer_suppression_rule`** — `concern-format.md` section, the
   inlined rule in all four producers, `SKILL.md.j2` Step 2 sentence, the new
   drift-guard test class + rendered-tree check, goldens regeneration,
   `aitask_skill_verify.sh` clean.
4. **t1427_4 `rejection_docs`** — website
   (`workflows/shadow-agent.md`, `tuis/minimonitor/how-to.md` keybinding table,
   `tuis/monitor/how-to.md` + `reference.md`) and
   `aidocs/framework/shadow_agent.md`: new `## Concern rejection store` section
   between "Feedback freshness" and "Configuration", framed as **producer-side
   filtering, never a gate** (the doc's no-gating principle); Step 2 bullet +
   sub-procedure list sentences. Present un-reject as TUI-only, and scrub the
   removed `a`/`A` bulk shortcuts from every keybinding table / how-to that
   mentions them.

Also at decomposition time:
- Create standalone follow-up task **`evaluate_aitask_gates_pruning`**
  (user-requested): evaluate an appropriate pruning/GC procedure for
  `.aitask-gates/`, referencing the new archive-time prune seam as prior art.
- Offer the **aggregate manual-verification sibling** (≥2 children): live
  two-round check — reject a concern in the picker, let the shadow re-review,
  confirm the rejected concern is suppressed with a visible "Suppressed N"
  report, un-reject via the `R` view, confirm it returns.

## Verification (end-to-end, after all children land)

- `bash tests/test_shadow_rejected.sh` — store/helper contract.
- `bash tests/run_all_python_tests.sh --test-dir tests` — picker, callbacks,
  producer drift guards (check the last stderr line, `PIPESTATUS[0]`).
- `./.aitask-scripts/aitask_skill_verify.sh` — stub/goldens surface.
- `shellcheck .aitask-scripts/aitask_shadow_rejected.sh`.
- Live: the manual-verification sibling's checklist (two-round suppression).

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.

## Risk

### Code-health risk: low
- Dismiss-contract change ripples through 4 dismiss sites, 2 app callbacks and
  3 pinning test files; a surviving truthiness check (`if not selected`) would
  silently drop a valid result carrying only rejections · severity: low
  (residual — addressed by inline pre-phase
  rejections_only_result_negative_control) · → mitigation: inline pre-phase
  rejections_only_result_negative_control
- Locked RMW append mis-composition (lock without atomic render, or renderer
  relying on `set -e`) could lose a concurrent rejection silently ·
  severity: low (residual — addressed by inline pre-phase
  contended_append_negative_control) · → mitigation: inline pre-phase
  contended_append_negative_control
- Narrow-width picker budget regression from the new glyph/keys ·
  severity: low (existing width-tier tests at 24/30/40 cols pin readability) ·
  → mitigation: none
- Post-inline reassessment: with both negative controls binding on the
  children, no medium-severity code-health concern remains; level lowered
  medium → low.

### Goal-achievement risk: medium
- Suppression correctness rests on the shadow's semantic matching — a prompt
  rule that cannot be deterministically unit-tested; it may under- or
  over-suppress in live rounds · severity: medium (fail-open rule + visible
  "Suppressed N" reporting bound the damage; live coverage via the
  manual-verification sibling) · → mitigation: none (candidate
  live_two_round_suppression_check dropped — covered by the planned
  manual-verification sibling)
- Producers can run without a resolved task id, making suppression silently
  unavailable for that round · severity: low (the rule mandates stating that
  suppression was skipped — visible, not silent) · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: contended_append_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: locked RMW append mis-composition loses a concurrent rejection | desc: two-writer contention test in child 1's bash suite proving both concurrent adds land; negative control proves it can fail
- timing: pre-phase | name: rejections_only_result_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: dismiss-contract truthiness regression silently drops rejection-only results | desc: callback tests in child 2 assert empty-forwarded/non-empty-rejected results still persist rejections
