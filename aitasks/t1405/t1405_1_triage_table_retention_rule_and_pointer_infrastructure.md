---
priority: high
effort: high
depends: []
issue_type: documentation
status: Ready
labels: [documentation, agents_md, docs]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1405
created_at: 2026-08-04 13:45
updated_at: 2026-08-05 18:24
---

## Context

First child of t1405. It is the **spike**: it freezes the memory-store
inventory, classifies every entry, builds the doc/entrypoint/guard scaffolding
the other six children write into, and proves the condensation format before any
bulk promotion happens. Children t1405_2..t1405_7 depend on this one and consume
its triage table.

The store is at `~/.claude/projects/-home-ddt-Work-aitasks/memory/` — **outside
the repo**. Its deletions and `MEMORY.md` rewrite appear in no git diff. Only the
`aidocs/`, `CLAUDE.md`, `AGENTS.md`, `.codex/`, `.opencode/`, `.gitignore` and
`tests/` changes are committable; say so explicitly in the Final Implementation
Notes so the commit is not mistaken for the whole deliverable.

Read the parent plan `aiplans/p1405_triage_agent_memory_store_into_aidocs.md`
first — it carries the full ground-truth table, the per-memory decision gate, and
the store-concurrency rules that bind every child.

## Deliverables

### 0. Freeze the manifest FIRST, before reading any memory

The store is live and has a concurrent writer (the auto-memory mechanism), which
honours no lock: it grew 148 -> 149 files *during t1405 planning*. So snapshot
first:

- Write `name / bytes / sha256` for every file to
  `.aitask-memtriage/manifest_names.txt` (names) plus a full table in this
  child's plan. That frozen list defines the classified set for all seven
  children.
- Confirm the pinned baseline. The 148 baseline is the sorted names minus the
  one known post-start arrival `project_t1224_done_unblocks_t1109`, digesting to
  `sha256 84db208094ef3b8997b79efc39c0288d3324475dbe8539ede7bfcc5f2c66207d`.
  If the digest matches with only that file removed, it is the sole arrival.
  Otherwise bisect and **name every additional arrival**.
- Write the arrivals to `.aitask-memtriage/post_freeze_arrivals.txt`. They are
  out of scope: not triaged, not deleted, not counted.
- Add `.aitask-memtriage/` to `.gitignore` next to the existing `.aitask-*/`
  per-run entries.

### 1. The triage table

Every manifest memory gets one row in this child's plan, plus a
machine-readable block:

```
name<TAB>type<TAB>proposed<TAB>owning-child<TAB>target-doc#heading<TAB>reason
```

Each memory is assigned to **exactly one** owning child — that is what stops a
memory falling between two clusters. The destination is `doc#heading`, not just
`doc`, so t1405_7 can rewrite `[[wikilinks]]` into references that resolve.
The table is a **proposal**; the binding disposition is the user's ruling in
that memory's decision gate (see the parent plan).

Provisional cluster assignment (confirm or revise it):
t1405_2 testing/verification -> `testing_conventions.md`;
t1405_3 code+API design -> `code_conventions.md`;
t1405_4 derived state/concurrency -> new `state_and_concurrency_conventions.md`;
t1405_5 planning/plan-review -> `planning_conventions.md`;
t1405_6 TUI + shell/security + skill authoring;
t1405_7 documentation + gates + shared-checkout hazards + final sweep.

### 2. Verify the DISCARD candidates

Use `./.aitask-scripts/aitask_query_files.sh task-status <id>` (an archived task
resolves to `Done`) and `archived-task <id>` (it searches inside the
`aitasks/archived/_b*/old*.tar.zst` bundles). Do **NOT** use `archived-children`
— it does not look inside the bundles and returns a false `NO_ARCHIVED_CHILDREN`.

Verified during t1405 planning — re-confirm, do not re-derive from scratch:

| Memory | Verdict |
|---|---|
| `project_t891_deferred_behind_t756` | DISCARD — t891, t891_5, t756 all archived |
| `project_t929_carveout_dropped` | DISCARD — t929 + children archived |
| `project_t986_2_postponed_shadow_not_phase_gated` | DISCARD — t986_2 was **deleted**, never implemented (commit 027ffcf94) |
| `project_t986_4_shadow_user_invocable_capture` | DISCARD — t986_4 + parent t986 archived; check `aidocs/framework/shadow_agent.md` already covers the contract |
| `project_t952_5_guard_scope_layer_split` | DISCARD — t952_5 + parent archived |
| `project_t635_29_split_procedure_gate` | KEEP — t635_29/31/32 all still Ready |
| `feedback_geminicli_to_agy_migrate_dont_close`, `project_agy_cli_no_model_flag` | KEEP — the whole t835 tree (parent + 7 children) is still Ready |

### 3. `aidocs/framework/README.md` — the canonical manifest

Index all 18 existing docs + the 4 new ones with a trigger sentence each, in
**two explicitly labelled lists**:

- **Entrypoint-advertised** — must be reachable from `CLAUDE.md` *and* all three
  appendices. Promoted docs go here.
- **Reachable-only** — deliberately kept out of every agent context, reached
  from a sibling doc or a skill: `model_reference_locations.md`,
  `agent_runtime_guards_audit.md`, `python_tui_performance.md`, and
  `sed_macos_issues.md` (already reached via the `shell_conventions.md` trigger).

The split is the policy statement: universal exposure is **not** the rule, so
adding an audit doc later does not force it into every agent's context.

### 4. `aidocs/framework/agent_memory_conventions.md` — the retention rule

- What earns a memory: operator-/machine-specific facts; live coordination state
  that names the task it dies with.
- What belongs in `aidocs/` instead: anything durable and agent-agnostic.
- When a `project_*` memory must be deleted (when the tasks it names archive)
  and exactly how to check (`aitask_query_files.sh task-status`, and the
  `archived-children` tar-bundle caveat above).
- A memory must never restate a skill contract — cross-reference the promoted
  `feedback_prefer_source_enforcement_over_memory` entry.
- The new-file-vs-new-`##`-section rule for `aidocs/framework/` (currently
  documented nowhere).

### 5. Entrypoint appendices

Append a `## Specialist rules (aidocs/framework)` section listing every
entrypoint-advertised doc + trigger, **after** the closing `<<<aitasks` marker
in all three of `AGENTS.md`, `.codex/instructions.md`, `.opencode/instructions.md`.

**Load-bearing mechanics.** All three files are 100% machine-generated: every
line sits between `>>>aitasks`/`<<<aitasks`, and `AGENTS.md`'s body is
byte-identical to `seed/aitasks_agent_instructions.seed.md`. `update_agentsmd()`
(`.aitask-scripts/aitask_setup.sh:1371`, called unconditionally at `:2501`)
awk-replaces everything **inside** the markers on every `ait setup`. Out-of-marker
prose survives — that is exactly what test T21 in `tests/test_agent_instructions.sh`
proves. Do **NOT** put the pointers in `seed/aitasks_agent_instructions.seed.md`:
`aidocs/` never ships to bootstrapped projects, so every path would dangle there.

### 6. `tests/test_aidocs_pointer_parity.sh`

Three assertions:

1. every `aidocs/framework/*.md` appears in `README.md` **exactly once**, in one
   of the two lists (no doc goes unindexed — costs no agent context);
2. every **entrypoint-advertised** doc is referenced from `CLAUDE.md` and from
   each of the three appendices;
3. every **reachable-only** doc has at least one in-repo referrer (`grep -rl`
   outside `README.md` itself).

`README.md` is exempt from assertion 1 (it is the manifest; listing itself is
meaningless) but **is** required in all four entrypoint surfaces.

Ship a **negative control**: remove one entrypoint-advertised doc's pointer from
one appendix in a temp copy and the test must exit 1 **naming that doc**. Prove
the harness itself can fail — a negative control that *passes* means the test is
wrong, not the docs.

Expect the guard to flag `model_reference_locations.md` (referenced from skills
and the website, never from `CLAUDE.md`). Classify it **reachable-only** rather
than inventing a trigger — it is a design-spec audit, not a convention.

### 7. CLAUDE.md

Add triggers for the 4 new docs. **Widen the `testing_conventions.md` trigger**,
which currently reads "when designing tests for a threading / asyncio migration"
and will be badly under-scoped once t1405_2 lands ~25 general testing rules.

### 8. Run the decision gate over the DISCARD candidates

Per-memory user ruling (see the parent plan's three-phase gate), then execute,
journalling each ruling to `.aitask-memtriage/t1405_1.tsv` **before** mutating
and flipping `state` to `done` after.

## Key files

- `aidocs/framework/README.md` (new), `agent_memory_conventions.md` (new)
- `AGENTS.md`, `.codex/instructions.md`, `.opencode/instructions.md` — appendix
  after `<<<aitasks` only
- `CLAUDE.md` — new triggers + widened testing trigger
- `tests/test_aidocs_pointer_parity.sh` (new), `.gitignore`

## Reference files for patterns

- House style for an aidocs convention entry: `aidocs/framework/code_conventions.md`
  (rule-as-heading, rule paragraph, rationale paragraph, examples). Terse-rule
  style: `aidocs/framework/shell_conventions.md` (flat bullets, no `##`).
- CLAUDE.md trigger phrasing: the blockquote pointers under `## TUI Development`
  and `## Planning / Testing / Code Conventions`.
- Marker/append semantics: `insert_aitasks_instructions()` and
  `update_agentsmd()` in `.aitask-scripts/aitask_setup.sh`; tests T18-T21 in
  `tests/test_agent_instructions.sh`.

## Verification

- `bash tests/test_aidocs_pointer_parity.sh` passes, and its negative control
  exits 1 naming the removed doc.
- `bash tests/test_agent_instructions.sh` still passes (T21 marker survival).
- `./ait setup` then `git diff --stat AGENTS.md .codex/instructions.md
  .opencode/instructions.md` — the appendices must survive regeneration.
- `grep -c "aidocs/framework" AGENTS.md` is no longer 0.
- Every DISCARD ruling is journalled `state=done` and the file is gone from both
  disk and `MEMORY.md`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T15:24:40Z status=pass attempt=1 type=human
>
> Note: deferred
