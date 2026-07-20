---
Task: t635_30_task_gate_editing_surface.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_24_*.md, aitasks/t635/t635_37_*.md
Archived Sibling Plans: aiplans/archived/p635/p635_*_*.md
Base branch: main
---

# t635_30 — Per-task gate editing surface

## Context

A task's `gates:` frontmatter list is its **declared gating intent**. Today it can
only be set via `ait update --batch --gates <csv>` or by hand-editing the task
file — there is no discoverable way for a human to declare that a task should be
gated. `aitask_gate.sh:8-11` explicitly defers the user-facing gate surface until
"its first real human command"; this task builds it.

Everything around it is already mature: the registry (`aitasks/metadata/gates.yaml`),
the orchestrator, the board's In-Flight gate *display* and human-gate sign-off
(t635_9), and — since t635_33 — the derived `active_gates` tuple materialized at
claim time that is the *enforced* set.

**Scope boundary.** This task owns the **per-task** `gates:` surface. t635_37 owns
the **profile-side** `default_gates`/`rendered_gates` picker; t635_24 owns
profile/registry-level settings config. All three read the same registry.

## The enforcement-fallback asymmetry (drives the `reset` design)

Two different code paths resolve gates, and they do **not** agree on what an
absent `gates:` key means:

| Path | Absent `gates:` means |
|---|---|
| `compute_active_gates` (`gate_ledger.py:738`) — materialization, **profile in scope** | `resolved = list(default_gates)` — profile defaults apply |
| `read_active_tuple_from_text` (`:579`) / `_active_set_csv` (`aitask_gate.sh:524`) — enforcement read, **no profile in scope** | falls back to raw `gates:` → **empty set, nothing enforced** |

So clearing the tuple *and* dropping the key on an `Implementing` task leaves
`ait gates run`, the dependency-unblock check, archive-readiness and
`should-self-record` all seeing **no gates at all** until some future pick
re-materializes. `reset` must therefore never blindly clear a materialized tuple
(see Implementation §2).

Note the asymmetry is safe in the other direction: `add`/`remove` leave a
*non-empty* `gates:`, so the fallback over-enforces (raw intent is a superset of
any profile-filtered set) rather than under-enforcing.

## Design decisions (confirmed with the user)

1. **Removing the last gate writes an explicit `gates: []`** (opt-out), not an
   absent key. A separate `ait gate reset <task>` drops the key to return to
   profile defaults. Three states, three explicit verbs — but `reset` is
   profile-aware, per §2 below.
2. **Gate edits clear the `active_gates` tuple** so `active-gates-status` reads
   `ABSENT` rather than `STALE` — *except* where clearing would under-enforce.
3. **Board surface = `TaskDetailScreen` `GatesField`**, not the In-Flight view.
   In-Flight lists only `Implementing` tasks, but gate declaration matters most
   *before* a pick. `aidocs/framework/aitasks_extension_points.md` also names the
   detail-screen field widget as the mandated pattern for board-editable fields.
4. **`aitask_merge.py` gates-merge semantics are deferred** to a follow-up task
   (recorded as an upstream defect at Step 8b).

## Rejected alternatives

- **`--gates "[]"` in-band sentinel** — rejected. `BATCH_GATES` flows raw into
  `format_yaml_list` (`lib/task_utils.sh:243-251`), which turns `[]` into `[[]]`,
  corrupting the file. The repo's convention here is a *presence flag*
  (`BATCH_*_SET`, `--clear-active-gates`), not an in-band value.
- **Board shelling straight to `aitask_update.sh --gates`** (the `AnchorField`
  pattern) — rejected: it bypasses registry validation, the manual-verification
  allowlist, the archived guard, tuple handling and the ordering rule. The board
  goes through the new shell verbs; this deliberate deviation from `AnchorField`
  is documented in the widget docstring.
- **Blindly clearing the tuple on `reset`** — rejected per the asymmetry above.
- **`reset --profile` that drops the key then re-materializes** — rejected as
  unsafe. `acquire_gate_lock` (`:70-91`) is a **non-reentrant** `mkdir` lock:
  invoking `materialize-active` while `reset` holds the lock retries 20× at 0.3s
  and then `die`s — *after* the key was already dropped, leaving exactly the
  empty-enforcement state the design is meant to prevent. Doing it without the
  lock, or as two sequential writes, has the same failure window. Writing the
  computed tuple and the absent key in one `aitask_update.sh` call would be
  atomic, but requires computing the digest against hypothetical post-write text
  (`build_active_digest` hashes `gates=absent` vs `gates=`), which duplicates
  materialization logic outside its owner. Refusal is provably safe and keeps the
  single materialization path authoritative.
- **Adding the new verbs to `gate-cli.md`** — rejected. That file is agent-facing
  guidance on verbs *workflows* branch on, and renders into four skill trees with
  goldens. These are human commands never workflow-dispatched.

## Implementation

### 1. Shared correctness fixes

**`.aitask-scripts/lib/task_utils.sh` — expose resolve provenance.**
`resolve_task_file` returns tier-3 hits as an **extracted temp path**
(`$_AIT_EXTRACT_RESULT`, `:626-629`) with no provenance, so an `ARCHIVED_DIR`
prefix test cannot detect them and an edit would "succeed" against a throwaway
file while the real task stays unchanged. Set a companion global
`_AIT_RESOLVE_PROVENANCE` (`active` | `archived_dir` | `archive_extract`),
**reset at every entry** to `resolve_task_file` so a stale value from a prior call
can never leak. Same treatment in all four extraction branches (`:628, :661, :720, :749`).

**`.aitask-scripts/aitask_gate.sh`:**
- **`_gate_lock_key <resolved-file>`** — derive the lock key from the resolved task
  file (basename sans `.md`), replacing `local key="${task_id//\//_}"` (`:648`).
  Today `ait gate append t635_30` and `... 635_30` take *different* locks and do
  not mutually exclude. Apply to `materialize-active` and `append` too.
- **`_registry_gate_meta_csv <gate>...`** — validate the **whole** list in ONE
  python call via canonical `gate_ledger.read_registry` (mirroring
  `aitask_gate_pass.sh:46-65`), returning missing names. Missing/unreadable
  registry is a hard `die` — `gates.yaml` lives on the `aitask-data` branch, so
  "no registry" is reachable.
- **`_assert_task_editable`** — `die` when `_AIT_RESOLVE_PROVENANCE` is not
  `active`, or when `status` is `Done`/`Folded`.

### 2. New verbs `add` / `remove` / `reset`

Action verbs — **exactly one line on stdout**, `die` (nonzero) on error:

| Result | Line |
|---|---|
| set changed | `GATES:<csv>` |
| last gate removed | `GATES:(empty)` (file has `gates: []`) |
| key dropped by `reset` | `RESET:cleared` |
| already in that state | `NOOP:unchanged` (file **byte-identical**) |

**Stdout hygiene (contract-critical).** `aitask_update.sh` prints `$final_path`
even under `--silent` (`:2021-2022`). Every delegated write must be invoked with
**stdout redirected to `/dev/null`** (stderr preserved for diagnostics), or the
helper's path line corrupts the single-line contract. Tests assert **full stdout
equality**, never substrings.

**Rules:**
- **`add` appends**, never sorts — gate order is load-bearing
  (`aidocs/gates/aitask-gate-framework.md:118-131`). `remove` preserves the
  relative order of survivors.
- **Manual-verification allowlist:** on `issue_type: manual_verification`, `add`
  **refuses** (die) gates outside `MANUAL_VERIFICATION_REACHABLE_GATES`.
  `filter_gates_for_issue_type` (`lib/task_utils.sh:268`) is called *only* from
  `aitask_create.sh` — the update path has no guard, so this surface would
  otherwise be the easiest way to wedge an MV task (the failure t1156 prevents).
  Refuse rather than silently strip: this is an interactive edit surface.
- **`reset` refuses whenever an `active_gates` key is present** (the §"asymmetry"
  fix). No `--profile` variant — see Rejected alternatives.
  - **No tuple present** (the normal case: a `Ready` task that has never been
    claimed) → drop the key, `RESET:cleared`.
  - **Tuple present** (valid *or* stale) → **refuse**, file byte-identical, with a
    message naming both escapes: "re-pick the task to re-materialize under the
    current profile, or use `ait gate remove` for an explicit opt-out."
    Refusing on mere *presence* is deliberately conservative: a stale tuple is
    already ignored by enforcement, but the check stays a single trivially
    testable predicate rather than a validity-dependent branch.
- **`remove` down to `gates: []` on an `Implementing` task** genuinely disarms
  enforcement — that is the user's explicit opt-out intent, so it proceeds but
  prints a stderr warning saying so.
- **Lock the whole read-modify-write** with `acquire_gate_lock` + `trap release`.
  `cmd_materialize_active` shells out to `aitask_update.sh` *inside* its critical
  section and that helper rewrites the entire frontmatter, so an unlocked `add`
  landing mid-materialize is a silent lost update.
- **Warn on dangling `also_blocks_dependents`** when `remove` strips a gate still
  listed there.

Writes delegate to one invocation:
`aitask_update.sh --batch <id> --gates <csv> --clear-active-gates --silent >/dev/null`
(confirmed atomic: both flags mutate in-memory state with a single
`write_task_file` at `:2005`; the guard at `:2030-2047` rejects
`--clear-active-gates` only against the four `--active-gates*` flags).

### 3. `--gates-empty` flag in `.aitask-scripts/aitask_update.sh`

Additive, no contract change: sets `BATCH_GATES=""` **and** presence true, so
`write_task_file` emits the literal `gates: []` (`:678-689`). `--gates ""` keeps
its documented meaning (delete the key) and backs `reset`. Add to the usage block;
reject `--gates-empty` combined with a non-empty `--gates`.

### 4. `./ait` dispatcher

Add `add|remove|reset` exec arms to the `gate)` case (`:315-326`), extend its
`--help` one-liner and the `*)` "Available:" list, and add the lines to the
`Gates:` block in `show_usage()` (`:51-57`) — **also fixing the pre-existing gap
that `gate pass` is dispatched but undocumented there**. Add `gate|gates` to the
update-check skiplist (`:186`) so the update banner cannot prepend lines to the
single status line callers parse.

### 5. Board — `.aitask-scripts/board/aitask_board.py`

- **`GatesField(Static)`** in `_build_relations_fields` (~`:3413`), mirroring
  `AnchorField` and guarded by the same `if self.manager and not self.read_only`,
  with a `ReadOnlyField` fallback.
- **`GatePickerScreen(ModalScreen)`** — multi-select, ☑/☐ per t1004 (marked = bold
  yellow), space to toggle, `:focus:hover` accent shade. Pattern **copied** from
  `monitor/monitor_shared.py:512-700`, not imported (different package).
- **Invalid existing state stays visible, and the toggle mechanic is asymmetric.**
  Rows are the union of registry-valid gates and *already-declared* gates.
  A declared gate that is unregistered, or unreachable on an MV task, renders as a
  **flagged row (e.g. `☑ plan_approved  ⚠ unreachable on manual_verification`)**
  with this precise mechanic:
  - it starts **checked** (it is genuinely declared today);
  - it **can be unchecked** — that is the whole point, the user must be able to
    remove it;
  - once unchecked it **cannot be re-checked** (the row goes inert), so the picker
    can never *introduce* an invalid gate;
  - an invalid gate that is **not** declared gets **no row at all** — there is
    nothing to remove and it must not be selectable.

  Save emits every still-checked row, including flagged ones, so cancelling or
  saving without touching the row **preserves** it — the picker never silently
  strips invalid state, it only ever surfaces it for deliberate removal. This
  matches the rule t635_37 sets profile-side ("shown, flagged, still removable —
  never silently dropped").
- Save computes the CSV preserving existing declared order, appending
  newly-checked gates in registry order, then shells out to **`aitask_gate.sh`**
  using the `capture_output=True, text=True, timeout=15` +
  `stderr or stdout or "unknown error"` pattern from `_append_human_gate`
  (`:5910-5936`). A footer key offers reset, routed through the plain `reset` verb
  — the board passes **no profile** (there is none to pass), so a task with a
  materialized tuple simply surfaces the verb's refusal message via `notify(...,
  severity="warning")`. The board reimplements none of the rule.
- On success call **`manager.clear_gate_cache()`** before `_reload_detail_screen`
  — that helper only does `task.load()` + re-push, so `gate_state_cache` /
  `gate_registry_cache` would keep serving pre-edit derivation.

### 6. Docs (current-state only)

- New minimal `website/content/docs/commands/gates.md` covering `add`/`remove`/
  `reset` (incl. the profile-aware reset semantics). t635_18's sweep expands it.
- `website/content/docs/commands/_index.md` — new `### Gates` section.
- `website/content/docs/development/task-format.md:60` — amend the `gates` row for
  the three-state semantics and name the editing commands.
- `website/content/docs/tuis/board/reference.md` — `GatesField` row.

## Risk

### Code-health risk: medium
- Changing the gate lock key from raw argument to resolved file alters
  mutual-exclusion for the **existing** `append`/`materialize-active` verbs. A wrong
  derivation over-excludes or under-excludes on a load-bearing path · severity:
  medium · → mitigation: t1183 (gate_lock_characterization)
- Adding `_AIT_RESOLVE_PROVENANCE` to `resolve_task_file` touches a helper used by
  nearly every script; a missed reset-at-entry leaks a stale value into an
  unrelated caller's guard · severity: medium · → mitigation: covered by the
  reset-at-entry test and the archived-task refusal tests below
- `remove` only *warns* on a dangling `also_blocks_dependents` reference rather
  than pruning it · severity: low · → mitigation: also_blocks_dependents_prune

### Goal-achievement risk: low
- The enforcement-fallback asymmetry that would have made `reset` silently disarm
  in-flight tasks was caught in review and is now designed around explicitly; every
  other mechanism was verified against source.
- `reset` is unavailable on a task that already carries a materialized tuple, so
  "return this in-flight task to profile defaults" needs a re-pick rather than a
  single command. Accepted deliberately: the atomic alternative duplicates
  materialization logic outside its owner, and re-pick is the existing,
  already-correct path · severity: low · → mitigation: none (documented in the
  refusal message and the command reference)

### Planned mitigations
- timing: before | created: t1183 | name: gate_lock_characterization | type: test | priority: medium | effort: low | addresses: code-health — gate lock key derivation change | desc: Pin the current mutual-exclusion behavior of aitask_gate.sh append/materialize-active with characterization tests, so the lock-key change from raw argument to resolved task file is provably safe for existing callers
- timing: after | name: also_blocks_dependents_prune | type: enhancement | priority: low | effort: low | addresses: code-health — dangling also_blocks_dependents after gate removal | desc: Offer to prune (not merely warn about) also_blocks_dependents entries left dangling when ait gate remove strips the referenced gate

## Verification

**`tests/test_gate_add_remove.sh`** (new; fixture per `tests/test_gate_cli_wiring.sh:20-27`),
each with its negative control:

- `add` appends: `[b, a]` + `c` → `[b, a, c]`, **never sorted**.
- `remove` last gate → literal `gates: []`, and that `[]` **survives an unrelated
  later edit** (`--batch <id> --priority high`) — the `CURRENT_GATES_PRESENT` path.
- `reset` with no tuple → key **absent**, asserted as `! grep -q '^gates:'` *and*
  via `_gates_half_input` yielding `gates=absent` (not `gates=`) — different digest
  inputs; file text alone misses half the contract.
- **`reset` on a task with a materialized tuple → refused, file byte-identical**
  (the under-enforcement regression test). Negative controls: refusal also fires
  for a **stale** tuple (presence, not validity, is the predicate); and after the
  tuple is legitimately cleared, `reset` on the same task succeeds — proving the
  refusal is tuple-conditional, not a blanket block.
- **Stdout is exactly one line** for every verb — full-equality assertion, proving
  the `aitask_update.sh` path line is redirected.
- Unknown gate → nonzero **and file hash unchanged** (no partial write before die).
- Duplicate `add` / absent `remove` → `NOOP:unchanged` **and file hash unchanged**.
- Tuple cleared: all four `active_gates*` keys gone in **one** write.
- MV task: `add plan_approved` refused.
- Missing registry → die, not silent accept.
- **Archived task resolved from `old.tar.zst` → refused**, with a companion test
  that `_AIT_RESOLVE_PROVENANCE` is reset on a subsequent *active* resolve (the
  stale-global negative control).
- **Concurrency:** background `materialize-active` racing an `add`; assert both
  survive (regression test for the lock-key fix).

**`tests/test_gate_cli_wiring.sh`** — extend (assertions are substring-based so they
won't break; the `gates --help` full-string assertion tolerates appending, not
reordering).

**`tests/test_board_gates_field.py`** (new) — model / Pilot / render tiers per
`tests/test_board_inflight_view.py`; `☑`/`☐` render assertions per
`tests/test_concern_picker_modal.py`; and a spy asserting the **argv** (that it
calls `aitask_gate.sh` and clears the tuple), not merely `returncode == 0`.

The invalid-row mechanic gets its own four assertions, since it is the subtlest
piece of UI logic here:
1. a declared MV-unreachable gate **renders flagged and checked** (not hidden);
2. it **can be unchecked**, and the resulting save argv **omits** it;
3. once unchecked it **cannot be re-checked** (row inert);
4. saving **without touching it** emits argv that still **contains** it — the
   no-silent-strip control;
5. an invalid gate that is *not* declared produces **no row**.

Plus a board test that the reset key on a materialized task surfaces the verb's
refusal as a warning notification and leaves the file unchanged.

**Full suite:** `bash tests/run_all_python_tests.sh`; the gate shell tests
(`test_gate_active_gates.sh`, `test_gate_declaration_backfill.sh`,
`test_gate_effective_gates.sh`, `test_gates_reference_drift.sh`,
`test_create_manual_verification_gates.sh`); plus the broad `resolve_task_file`
consumers (`test_claim_id.sh`, archival/resolution tests) given the provenance
change; `shellcheck .aitask-scripts/aitask_gate.sh .aitask-scripts/aitask_update.sh
.aitask-scripts/lib/task_utils.sh`; `hugo --minify --quiet` from `website/`.

**Manual:** `ait gate add 42 lint` → `ait gate list 42` → `ait gate active-gates-status
42 --profile aitasks/metadata/profiles/fast.yaml` reads `ABSENT`; `ait board` → task
detail → Gates field → picker round-trip.

## Step 9 (Post-Implementation)

Merge, run gates, clean up worktree/branch, archive via
`./.aitask-scripts/aitask_archive.sh 635_30`. Record the `aitask_merge.py`
gates-merge gap as an upstream defect so Step 8b offers the follow-up task.
