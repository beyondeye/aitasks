---
priority: high
effort: high
depends: [t1468_1]
issue_type: feature
status: Implementing
labels: [task_workflow, task_metadata]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1468
created_at: 2026-08-10 16:28
updated_at: 2026-08-10 22:19
---

## Context

Parent: t1468 — mark auto-spawned follow-up tasks with a machine-readable kind.
Depends on **t1468_1**, which registers the `followup_kind:` frontmatter field
and its `--followup-kind` flag on `aitask_create.sh` / `aitask_update.sh`.

This child makes every seam that auto-creates a follow-up actually **set** the
kind. Twelve seams were audited: nine route through the shared batch procedure,
three are shell helpers.

Read the parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md` for the
design decision and the full seam table.

## Key files to modify

### The shared creation contract
`.claude/skills/task-workflow/task-creation-batch.md` — **this is the source
file**, and although it is a `.md` (not `.md.j2`) it *is* Jinja-rendered by the
closure dep-walker. Only skill entry points use `.md.j2`; transitively-referenced
procedure files stay `.md` and are rendered anyway.
- Input table `:7-23` — the `followup_kind` row is added by **t1468_1**; verify
  it is present rather than re-adding it.
- `### Optional flags` `:115-124` — add the flag emission here.

### The nine skill caller sites → expected kind

| caller | site | kind |
|---|---|---|
| `task-workflow/risk-mitigation-followup.md` Part 2 ("before") | `:385-392` | `risk_mitigation` |
| `task-workflow/risk-mitigation-followup.md` Part 3 ("after") | `:505-515` | `risk_mitigation` |
| `task-workflow/upstream-followup.md` | `:67` | `upstream_defect` |
| `aitask-qa/follow-up-task-creation.md` **child branch** | `:32-41` | `qa_test_gap` |
| `aitask-qa/follow-up-task-creation.md` **parent branch** | `:48-57` | `qa_test_gap` |
| `aitask-review/SKILL.md.j2` single-task | `:183` | `review_finding` |
| `aitask-review/SKILL.md.j2` parent | `:199` | `review_finding` |
| `aitask-review/SKILL.md.j2` children | `:213` | `review_finding` |
| `aitask-docs-gap/SKILL.md` | `:160-170` | `docs_gap` |

**`aitask-docs-gap` bypasses the shared template entirely** — it inlines a raw
`aitask_create.sh --batch --commit` command with no `--gates` injection and no
`followup_of`. Add the flag inline there and leave a comment noting the
divergence (do not silently rewrite it to use the template — that is a larger
change with its own gate-injection consequences).

### The three shell helpers → expected kind

| helper | site | kind |
|---|---|---|
| `.aitask-scripts/aitask_create_manual_verification.sh` | `create_args` `:108-131` (already passes `--verifies` at `:116`) | `manual_verification` |
| `.aitask-scripts/aitask_archive.sh` `create_carryover_task()` | `create_args` `:602-610` | `carry_over` |
| `.aitask-scripts/aitask_verification_followup.sh` | `:208-216` | `verification_failure` |

### Cheap independent fix, in scope here
`upstream-followup.md` passes **no `--followup-of`**, which is why 58 follow-ups
are topic roots and cannot cluster with their origin in the board's By-Topic
view. Add it (the origin task id). Compare `aitask_verification_followup.sh:200-206`,
which builds `followup_args` conditionally and fails safe to a topic root when
the origin does not resolve.

## Regeneration (do not skip, and stage deliberately)

`task-creation-batch.md` has **9 rendered copies** — 3 profiles × 3 agent trees:
- `.claude/skills/task-workflow-{default,fast,remote}-/task-creation-batch.md`
- `.agents/skills/task-workflow-{default,fast,remote}-codex-/task-creation-batch.md`
- `.opencode/skills/task-workflow-{default,fast,remote}-/task-creation-batch.md`

Rerender with **one call per profile** (the driver takes a **positional** profile
name — not `--profile` — and loops all three agent trees internally):

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

- `task-creation-batch.md` has **no goldens of its own**, but its *callers* do —
  regolden `tests/golden/procs/task-workflow/risk-mitigation-followup-*.md` and
  `tests/golden/skills/aitask-review/SKILL-*-claude.md`.
- **Git tracking is asymmetric:** `.gitignore:47` ignores the rendered trees, but
  the three **`remote`** copies are force-tracked committed prerenders and must
  be committed.
- **Stage with an explicit path allowlist.** The sweep touches dozens of files;
  never `git add -A`.
- Run `./.aitask-scripts/aitask_skill_verify.sh` (no flags; verifies against the
  default profile and walks the reference closure).

## Verification steps

**Tests must cover every seam, not two.** A seam that silently omits
`--followup-kind` still renders consistently and keeps `aitask_skill_verify.sh`
green — the sweep proves nothing on its own. Two complementary **table-driven**
suites keyed by `(seam → expected kind)`:

1. **argv assertions** for the three shell helpers. `tests/test_archive_carryover.sh`
   already has exactly the harness to copy (`:32-90` stubs `aitask_create.sh` and
   logs argv). Assert the expected `--followup-kind` value for each of
   `aitask_archive.sh`, `aitask_create_manual_verification.sh`,
   `aitask_verification_followup.sh`. Add a **real-file** assertion for at least
   one, per `tests/test_archive_carryover_anchor.sh` (which uses the real
   `aitask_create.sh` and asserts the emitted line).
2. **rendered-content assertions** for the nine skill call sites — grep the
   **rendered** profile variants (not the source) for the expected value at each
   site. The table must be **exhaustive by construction**: fail if a listed seam
   is missing, *or* if a `Batch Task Creation Procedure` call site exists that
   the table does not name.

Plus:
3. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
4. `bash tests/run_all_python_tests.sh` (read the LAST line for the verdict).
5. Create one real follow-up end to end (e.g. drive the carry-over path) and
   confirm the created file carries the right `followup_kind:` line.
6. Confirm `upstream-followup.md`'s new `--followup-of` produces an `anchor:` on
   a real upstream-defect task.
