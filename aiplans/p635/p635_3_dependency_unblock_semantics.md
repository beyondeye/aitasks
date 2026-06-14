---
Task: t635_3_dependency_unblock_semantics.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_4_gate_guarded_archival.md, aitasks/t635/t635_5_ledger_driven_reentry.md, aitasks/t635/t635_8_python_gate_ledger_parser.md, aitasks/t635/t635_9_board_inflight_action_view.md, aitasks/t635/t635_14_profile_gate_declaration_unification.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md
Base branch: main
plan_verified: []
---

# t635_3 — Dependency-unblock semantics for gated tasks

## Context

Phase 2 of the gate-framework roadmap (`aidocs/gates/integration-roadmap.md`,
"open problem 1"). Today a `depends:` edge unblocks **purely on file existence**:
`is_task_uncompleted()` (`aitask_ls.sh:162`) returns true iff the upstream's ID is
still in the active-task set; archival removes it → dependents unblock. The board
TUI has its own parallel rule (`aitask_board.py:797`: a dep is unresolved while
`status != 'Done'`).

With **gate-deferred archival** (t635_4 / decision D5), a task whose substantive
work is done but whose human/async sign-off pends for days **stays in the active
set** → `is_task_uncompleted()` keeps returning true → dependents block *longer
than today*. This task designs and implements the explicit unblock point so that
deferred archival does not regress dependent availability. It **must land before
or with t635_4**.

**Decisions taken with the user (this session):**
- **Combined registry + per-task model.** A registry per-gate flag marks a gate
  as **required to pass before dependents unblock**; a per-task frontmatter list
  declares **additional** gates required to unblock *that* task's dependents.
- Better names than the roadmap's straw-man `unblocks_dependents:` / `unblock_after:`
  (see Naming below — confirm at review).
- **Board scope: CLI now; board via t635_8/t635_9.** Implement the shared decision
  in `gate_ledger.py` and wire only `aitask_ls.sh` (the pick/ls path) now; the
  board becomes gate-aware through the shared parser (t635_8) and In-Flight view
  (t635_9). Coordination notes + flagged interim window.

## Design

### The unblock criterion

For an **active** upstream task `U` referenced by a dependent's `depends:`:

1. `declared = U.gates` (frontmatter `gates:` list — authoritative per the
   framework contract; absent/empty = "ungated", behaves exactly like today).
2. `also = U.also_blocks_dependents` (new per-task list; additional required gates).
3. `required(U) = { g ∈ declared : registry[g].blocks_dependents } ∪ also`.
4. **If `required(U)` is empty** → decision `NO_GATES`: fall back to **today's
   file-existence behavior** (U blocks until archived). Covers ungated tasks and
   the footgun where a gated task marks none of its gates as blocking (conservative,
   never unblocks prematurely).
5. **Else** U is *satisfied-for-dependents* ⟺ every gate in `required(U)` has
   derived status `pass` (`derive_status`, last-run-wins). Otherwise `BLOCKED`
   (with the list of still-pending required gates).

The decision is a property of the **upstream** task, evaluated per `depends:` edge.
This makes all chain shapes uniform:
- **Ungated upstream** → file-existence (unchanged).
- **Gated upstream, ungated dependent** → upstream's gate state drives unblock;
  the dependent being ungated is irrelevant.
- **Ungated upstream, gated dependent** → unchanged (dependent's own gates never
  affect when *its* dependencies clear).

### Gate flag assignments (the 5 seeded gates)

The axis is **"once this gate passes, is U's code available for dependents to
build on?"** — *not* machine-vs-human (the roadmap straw-man). Integration gates
are required; pre-code and (future) post-integration sign-off gates are not.

| Gate | `blocks_dependents` | Why |
|------|---------------------|-----|
| `plan_approved` | **false** | No code exists yet |
| `risk_evaluated` | **false** | No code exists yet |
| `build_verified` | **true** | Implementation compiles / verify passes |
| `review_approved` | **true** | Code committed (the integration point for current-branch profiles) |
| `merge_approved` | **true** | Code on the base branch (integration point for worktree profiles) |

Consequence at the **current** stage: the blocking set among the 5 is effectively
`merge_approved` (worktree) / `review_approved` (current-branch) — i.e. **the same
point as today's archival**. So this change introduces **neither a regression nor
a premature unblock now**. The flag becomes load-bearing once later phases add
*post-integration* gates with `blocks_dependents: false` — async human review
(t635_15), `docs_updated` (t635_19), manual-verification — which is exactly the
regression class this task exists to neutralize.

### Dormancy / sequencing (why this is safe to land first)

The new logic only changes behavior for a task that is **active AND has a
non-empty `gates:` field AND has all required gates passed while still active**.
That state is only produced by **deferred archival** (t635_4) and a populated
`gates:` field (t635_14, Phase 4). Until those land, `aitask_ls.sh` finds no
active task with a `gates:` field, the new code path is skipped entirely (grep
guard → zero overhead, zero behavior change), and correctness is proven by
synthetic-fixture tests. This is the right sequencing: t635_3 ships the
**mechanism + contract**, t635_4 flips the switch that makes it matter.

### Relationship to framework open question 4

The framework doc's open question 4 ("cross-task gates", e.g. depend on a
*specific* gate of a *specific* upstream) stays deferred. This design resolves the
**unblock-timing** question by making the upstream's own gate state the unblock
signal; `also_blocks_dependents` lives on the **upstream** (controls when it
releases *all* its dependents), not as a per-edge selector. True per-edge gate
dependencies remain out of scope.

### Naming (confirm at review)

- Registry per-gate boolean: **`blocks_dependents`** — "this gate blocks the
  task's dependents until it passes"; aligns with the existing "blocked"
  vocabulary. (Alt considered: `required_for_dependents`.)
- Per-task list: **`also_blocks_dependents: [gate, …]`** — "these gates *also*
  block this task's dependents" (additive to the registry-required set).
  (Alt considered: `extra_blocking_gates`.)

### Rejected alternatives

- **All-gates-pass (= archival).** Simplest, but inherits the exact slow-sign-off
  regression we exist to fix.
- **Pure machine-unblocks / human-doesn't.** Breaks worktree mode: `merge_approved`
  is a *human* gate but is the point at which code reaches the base branch — a
  dependent unblocked at `build_verified` would branch off a base without the
  upstream's code. The "integration vs pre/post" axis is correct; machine/human
  is not.
- **Per-task-only (no registry default).** Forces every task to re-declare the
  same unblock set → noise; the registry holds the sane default, the per-task
  list augments it.
- **Wire the board now.** Partially does t635_8's shared-parser job and risks
  rework; deferred per the user's decision.

---

## Deliverables (file by file)

### 1. Core decision in the canonical module

**`.aitask-scripts/lib/gate_ledger.py`** (extend; stdlib-only, no PyYAML):
- Refactor `read_declared_gates` to delegate to a generic
  `_read_frontmatter_list(task_file, field)` (inline `[a, b]` and block `- a`
  styles — reuse the existing two regexes); `read_declared_gates` =
  `_read_frontmatter_list(f, "gates")`.
- Extend `read_registry` to capture a per-gate `blocks_dependents` bool
  (`re.match(r"^[ \t]+blocks_dependents:\s*(.+?)\s*$", line)` → truthy on
  `true/yes/1`; default `False`).
- Add:
  ```python
  def required_unblock_gates(declared, also, registry):
      req = [g for g in declared if registry.get(g, {}).get("blocks_dependents")]
      for g in also:
          if g not in req:
              req.append(g)
      return req

  def dependents_status(task_file, registry_file):
      declared = read_declared_gates(task_file)
      also = _read_frontmatter_list(task_file, "also_blocks_dependents")
      registry = read_registry(registry_file)
      required = required_unblock_gates(declared, also, registry)
      if not required:
          return ("NO_GATES", [])
      with open(task_file, encoding="utf-8") as fh:
          state = derive_status(fh.read())
      pending = [g for g in required if state.get(g, {}).get("status") != "pass"]
      return ("BLOCKED", pending) if pending else ("SATISFIED", [])
  ```
- CLI verb `deps-unblock <task-file> [registry]` → prints `SATISFIED` /
  `BLOCKED:<csv>` / `NO_GATES`.

**Decision (deviation from t635_1's bash-primary rule, documented):** the
`deps-unblock` decision is implemented **python-only** (delegated), not awk-primary.
Rationale: it is a brand-new, low-frequency decision (only on `ait ls`, only for
gated active files), and reproducing registry-flag + two-list logic in POSIX awk
would double the code and require parity tests for no hot-path benefit. The
bash-primary rule in t635_1 targeted the high-frequency `append`/`status` path.
`gate_ledger.py` is the canonical derivation home t635_8 extends.

### 2. Bash surface

**`.aitask-scripts/aitask_gate.sh`** (extend): add subcommand
`deps-unblock <task-id>` → resolve file via `resolve_task_file`, then
`delegate_python deps-unblock "$file" "$REGISTRY"` (reuse the existing
`delegate_python` helper and `REGISTRY="${TASK_DIR}/metadata/gates.yaml"`).
Update `--help` and the unknown-subcommand error list.

### 3. Wire into the CLI blocking computation

**`.aitask-scripts/aitask_ls.sh`**:
- After `existing_ids_file` is built (~line 152), add
  `build_dep_satisfied_set()`: grep active parent (`$TASK_DIR/t*.md`) + child
  (`$TASK_DIR/t*/t*_*.md`) files for a non-empty `^gates:` line; **if none, no-op
  (zero overhead — the universal case today).** For each gated file, run
  `aitask_gate.sh deps-unblock <id>`; append IDs returning `SATISFIED` to a new
  `dep_satisfied_file` temp.
- In `is_task_uncompleted()` (line 162): a dep is *completed* if its ID is **not**
  in `existing_ids_file` **OR** it **is** in `dep_satisfied_file`. (Purely
  additive: a gated active task whose required gates all passed now counts as
  satisfied; everything else — ungated, `NO_GATES`, `BLOCKED` — keeps today's
  file-existence behavior.)
- Add the new temp to the `rm` cleanup (line 538).

### 4. Registry: the new flag (5 gates)

**`aitasks/metadata/gates.yaml`** + **`seed/gates.yaml`** (kept identical): add
`blocks_dependents: <true|false>` to each of the 5 gates per the table above, and
a header-comment block documenting the flag (mirroring the existing `type:`
comment). No other registry change.

### 5. Per-task field registration (durability — mirrors t635_1 `gates:`)

A new frontmatter field is **silently dropped** by `aitask_update.sh`'s positional
`write_task_file` reconstruction unless registered (t635_1 decision #2). Mirror the
exact `gates:` plumbing for `also_blocks_dependents`:
- **`aitask_update.sh`**: `CURRENT_ABD` var (mirror `CURRENT_GATES` at :89/:361);
  parse case `also_blocks_dependents)` (mirror :447); new positional param in
  `write_task_file` + serialize line, emitted only when non-empty (mirror :568);
  thread through all `write_task_file` call sites (mirror `CURRENT_GATES` at
  :939/:973/:986/:1468/:1799); optional `--also-blocks-dependents` batch flag
  (replace-all, mirror `--gates`).
- **`aitask_create.sh`**: `--also-blocks-dependents` flag + emit in **both**
  `create_task_file` and `create_draft_file` (t635_1 lesson: the batch
  draft→finalize path bypasses `create_task_file`).
- **`aitask_fold_mark.sh`**: union `also_blocks_dependents` across folded tasks
  (mirror the `gates:` union).

### 6. Design doc

**`aidocs/gates/dependency-unblock-semantics.md`** (new): the full design above —
problem/regression, the chosen model + criterion, the gate-flag table + rationale,
ungated/mixed-chain behavior, edge cases (empty-required fallback; an
`also_blocks_dependents` entry that isn't a declared/run gate stays pending and
blocks — documented, visible), dormancy/sequencing, relationship to open question
4, naming rationale, rejected alternatives. Front-matter consistent with the other
`aidocs/gates/` docs (title/category/tags/sources/confidence/created/updated).

### 7. Tests

**`tests/test_dependency_unblock.sh`** (new, self-contained, `tests/lib/asserts.sh`):
- **Unit (`gate_ledger.py deps-unblock` / `aitask_gate.sh deps-unblock`):**
  required gate passed → `SATISFIED`; required gate pending/absent →
  `BLOCKED:<gate>`; only `blocks_dependents:false` gates declared → `NO_GATES`; no
  `gates:` field → `NO_GATES`; `also_blocks_dependents:[docs_updated]` blocks until
  that run passes.
- **Integration (`aitask_ls.sh -v`, harness modelled on `test_xdeps_blocking.sh`):**
  temp repo with `aitasks/metadata/gates.yaml`; gated upstream with recorded
  `## Gate Runs` + a dependent `depends:[upstream]`.
  - required gate pending → dependent shows `Blocked (by …)`.
  - **regression fix:** required gates pass while a non-required `blocks_dependents:false`
    gate still pends → dependent **not** blocked.
  - ungated upstream (control) → blocked while active, unblocked once archived.
- **Round-trip:** `ait update <id> --status X` preserves `also_blocks_dependents`;
  fold union works.

**Regression (must stay green):** `bash tests/test_gate_ledger.sh`,
`tests/test_gate_frontmatter_roundtrip.sh`, `tests/test_xdeps_blocking.sh`,
`tests/test_yaml_utils.sh`.

### 8. Roadmap + coordination (post-approval, Step 7 — plan mode is read-only)

- **`aidocs/gates/integration-roadmap.md`**: mark "open problem 1" RESOLVED
  (decision recorded; combined registry-flag + per-task model; link the new design
  doc).
- **Coordination notes** (bidirectional, via `./ait git`):
  - **t635_4** — reverse pointer: unblock decision lives in `gate_ledger.py
    dependents_status` + `aitask_ls.sh`; archival stays the *all-gates-pass* event,
    distinct from unblock.
  - **t635_8** — extend `gate_ledger.py` `dependents_status` / `required_unblock_gates`;
    TUIs consume it, do not fork.
  - **t635_9** — wire the same gate-aware unblock into `aitask_board.py`
    `unresolved_deps` (currently `status != 'Done'`, :797) via the shared decision;
    note the interim CLI/board inconsistency window (after t635_4, before t635_9).
  - **t635_14** — when profiles populate `gates:`, the unblock logic goes live;
    document the `also_blocks_dependents` interplay.

### Out of scope (scope guard)
No board edit/widget changes (t635_9); no website docs (deferred to t635_18,
current-state rule — nothing user-facing lands live yet); no archival logic
(t635_4); no orchestrator/verifier (t635_11). No `ait` dispatcher entry for
`deps-unblock` (full-path/internal helper, consistent with t635_1 decision #6).

---

## Risk

### Code-health risk: medium
- Re-touching `aitask_update.sh` `write_task_file` positional reconstruction (load-
  bearing on **every** task update) to register `also_blocks_dependents` · severity:
  medium · → mitigation in-task: round-trip assertions in
  `test_dependency_unblock.sh` + keep `test_gate_frontmatter_roundtrip.sh` and
  `test_update_*` green.
- Modifying `aitask_ls.sh` `is_task_uncompleted` / blocking (consumed by every `ait
  ls` + sort) · severity: medium · → mitigation: change is strictly additive (only
  `SATISFIED` gated active tasks differ); grep-guarded so zero overhead/zero
  behavior when no `gates:` files exist; `test_xdeps_blocking.sh` + new integration
  test green.
- `deps-unblock` implemented python-only (deviates from t635_1's bash-primary rule)
  · severity: low · → mitigation: documented decision; low-frequency path; canonical
  module that t635_8 extends.

### Goal-achievement risk: low
- Mechanism is dormant until t635_4 + t635_14 land (designed against not-yet-live
  surfaces) · severity: low · → mitigation: the design doc fixes the contract;
  synthetic-fixture tests prove correctness independently; sequencing constraint
  (land before t635_4) honored.
- Final naming (`blocks_dependents` / `also_blocks_dependents`) may change ·
  severity: low · → mitigation: confirm at the plan-review checkpoint; names are
  isolated to the registry, one frontmatter field, and the design doc.

### Planned mitigations
None — all risks are bounded and mitigated **in-task** by the test deliverables;
no separate before/after mitigation tasks are warranted.

---

## Verification

1. `shellcheck .aitask-scripts/aitask_gate.sh .aitask-scripts/aitask_ls.sh
   .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_create.sh
   .aitask-scripts/aitask_fold_mark.sh`.
2. `bash tests/test_dependency_unblock.sh` (unit + ls-integration + round-trip).
3. Regression: `bash tests/test_gate_ledger.sh && bash
   tests/test_gate_frontmatter_roundtrip.sh && bash tests/test_xdeps_blocking.sh
   && bash tests/test_yaml_utils.sh`.
4. Manual smoke on a scratch task:
   `./.aitask-scripts/aitask_gate.sh deps-unblock <id>` returns `NO_GATES` for an
   ungated task; add `gates: [build_verified]`, record
   `aitask_gate.sh append <id> build_verified pass` → `SATISFIED`; flip to a
   pending required gate → `BLOCKED:<gate>`.
5. Durability: add `also_blocks_dependents: [docs_updated]` to a task, run `ait
   update <id> --status Editing`, confirm the field survives.
6. macOS static sweep on edited scripts (no awk added here, but per
   `sed_macos_issues.md`): no `grep -P`, `sed -E` for `?`/`+`/`|`, `mktemp`
   template form only.

## Step 9 reference
Post-implementation cleanup and archival follow the shared **Step 9
(Post-Implementation)** flow (current branch — `fast` profile; no worktree/merge).
