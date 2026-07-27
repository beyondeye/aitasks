---
Task: t635/t635_27_docs_updated_live_verify.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_*.md
Archived Sibling Plans: aiplans/archived/p635/p635_*_*.md
Base branch: main
---

# t635_27 — `docs_updated` gate live verification (autonomous)

Strategy: **autonomous** (agent picked the approach per item on the fly). All 6
checklist items reached a terminal `pass`.

The live drive used four scratch tasks created via `ait create --batch` +
`--finalize`, each declaring `gates: [docs_updated]`:

| Scratch | Purpose |
|---|---|
| t1252 | Item 1 (headless deferral) + Item 2 (full Step 8 dispatch, `pass`) |
| t1253 | Item 6 (unrun gate blocks archival) + Item 3 (`_index.md` footgun rule) |
| t1254 | Item 4 (no-docs-needed → `skip`) |
| t1255 | Item 5 (user-rejected → `fail`, archival blocked, then resolved) |

All four were deleted after verification.

## Execution Log

### Item 1 — headless deferral (`needs agent`, no shell exec, exit 0)

- **Item text:** Declare `gates: [docs_updated]` on a scratch/real task and confirm
  `ait gates run <id>` reports it **needs agent** (deferred, no shell exec, exit 0).
- **Approach:** CLI invocation against the real outermost surface (`ait gates run`,
  not the orchestrator module directly).
- **Action run:** `./ait gates run 1252`, capturing stdout+stderr and `$?`; before/after
  `grep -c "gate:"` on the task file; `ls .aitask-gates/1252`.
- **Output (trimmed):**
  `docs_updated: needs agent (procedure-backed gate — run via task-workflow / aitask-resume)`,
  `rc=0`, gate-marker count `0 → 0`, no `.aitask-gates/1252` directory created.
  `procedure-gates 1252` → `docs_updated`; `archive-ready 1252` → `BLOCKED:docs_updated`.
- **Verdict: pass**

### Item 2 — full Step 8 dispatch (`begin-procedure` → skill → `pass`)

- **Item text:** Run task-workflow Step 8: `procedure-gates` lists it; `begin-procedure`
  opens a running block + prints RUN_ID/ATTEMPT; the `aitask-gate-docs-updated` skill
  fires, inspects the change, infers the right doc page, confirms with the user,
  applies, and appends `pass` via `append --only-if-running`.
- **Approach:** Live execution of the real Step 8 dispatch seam against a real,
  uncommitted implementation change (the state Step 8 actually runs in — procedure
  gates run *before* review so their edits land in the task's commit).
- **Action run:**
  1. Authored a real doc-relevant change: new `ait lock --count` subcommand in
     `.aitask-scripts/aitask_lock.sh` (`count_locks()`, help entry, case arm).
     Smoke-tested (`./ait lock --count` → `8`); `shellcheck` showed only pre-existing
     info-level notes.
  2. `aitask_gate.sh procedure-gates 1252` → `docs_updated`.
  3. `aitask_gate.sh begin-procedure 1252 docs_updated` → `RUN_ID:2026-07-26T14:08:53Z`,
     `ATTEMPT:1`; running block appended.
  4. Read-and-followed `.claude/skills/aitask-gate-docs-updated/SKILL.md` with
     `1252 1 2026-07-26T14:08:53Z`:
     - Step 1 resolved the guide via
       `aitask_resolve_config_path.sh doc_update.guide` → `aitasks/metadata/doc_update_guide.md`.
     - Step 2 gathered the change surface (`git log --grep`, `git diff --name-only HEAD`,
       `git ls-files --others`).
     - Step 3 applied the map row "`ait` subcommand added/changed → `website/content/docs/commands/`"
       to infer `website/content/docs/commands/lock.md`.
     - Step 4 confirmed with the user via `AskUserQuestion` → **Apply**.
     - Step 5 added the `--count` row to the Commands table.
     - Step 6 wrote the sidecar log and appended the terminal block with
       `append --only-if-running`.
- **Output (trimmed):** terminal block `status=pass attempt=1`; `status 1252` →
  `docs_updated: pass`; `archive-ready 1252` → `ALL_PASS`; `procedure-gates 1252` → empty.
  **Negative control:** a second `append --only-if-running` with the same run-id and
  `fail` no-opped (rc=0, zero `DOUBLE-APPEND` blocks, still exactly one `pass` block) —
  the terminal append is genuinely once-per-run.
- **Verdict: pass**

### Item 3 — the `_index.md` manual-list footgun rule

- **Item text:** The `_index.md` manual-list rule: a NEW `workflows/*.md` page without
  its `_index.md` bullet is flagged.
- **Approach:** Fixture creation + live gate run.
- **Action run:** Created `website/content/docs/workflows/scratch-gate-probe.md` (a NEW
  workflows page) with **no** bullet in `workflows/_index.md`.
  `begin-procedure 1253 docs_updated` → `RUN_ID:2026-07-27T05:14:33Z`-era run
  `2026-07-26T14:24:10Z`, `ATTEMPT:1`. Confirmed mechanically that the guide carries the
  rule in two places: the map row (line 34) and the `### Known footgun` section (line 36).
  `grep scratch-gate-probe website/content/docs/workflows/_index.md` → missing.
- **Output (trimmed):** The missing bullet was flagged and surfaced in the user
  confirmation, then added to the grouped body list. Terminal `pass`;
  `archive-ready 1253` → `ALL_PASS`.
- **Verdict: pass**

### Item 4 — no-docs-needed change records `skip`, not `pass`

- **Item text:** No-docs-needed change → skill records **`skip`** (not pass);
  `archive-ready` still `ALL_PASS`.
- **Approach:** Fixture creation (test-only change) + live gate run.
- **Action run:** Created `tests/test_scratch_gate_probe.sh` as the sole change surface.
  `begin-procedure 1254 docs_updated` → `RUN_ID:2026-07-26T14:36:21Z`, `ATTEMPT:1`.
  No map row matches `tests/`; the guide's terminal-outcome rule (line 88) defines SKIP
  as "no doc-relevant user-facing surface". User confirmed **Not needed / skip**.
  Appended `skip` via `append --only-if-running`.
- **Output (trimmed):** ledger marker uses the distinct `skip` glyph; `status 1254` →
  `docs_updated: skip`; `grep -c "status=pass"` → **0** (no pass was written);
  `archive-ready 1254` → `ALL_PASS`; `procedure-gates 1254` → empty. So `skip` is
  terminal-satisfied *and* stays distinct from `pass`.
- **Verdict: pass**

### Item 5 — user-rejected doc work records `fail`; archival BLOCKED until resolved

- **Item text:** User-rejected doc work → `fail`; archival BLOCKED until resolved.
- **Approach:** Live gate run with a deliberately doc-warranted change, rejected at the
  confirmation, then resolved on a second dispatch.
- **Action run:**
  1. Added an `ait lock --count` example to the help Examples block — a genuine
     `commands/lock.md` doc obligation.
  2. `begin-procedure 1255 docs_updated` → `RUN_ID:2026-07-26T14:44:12Z`, `ATTEMPT:1`.
     User chose **Reject** → appended `fail`.
  3. `archive-ready 1255` → `BLOCKED:docs_updated`;
     `aitask_archive.sh 1255` → **exit 2**, `GATE_PENDING:docs_updated` +
     `GATE_BLOCKED: cannot archive until all declared gates pass (use --ignore-gates to override)`;
     task file stayed in `aitasks/`, never moved to `aitasks/archived/`.
  4. **"Until resolved" half:** after the `fail`, `procedure-gates 1255` still listed
     `docs_updated` (a `fail` is not terminal-satisfied). Re-dispatched, applied the doc
     fix, appended `pass` → `status 1255` → `pass`, `archive-ready` → `ALL_PASS`,
     `procedure-gates` → empty.
- **Verdict: pass**

### Item 6 — archive fail-safe: a declared-but-unrun gate blocks archival

- **Item text:** Archive fail-safe: a declared-but-unrun `docs_updated` blocks archival.
- **Approach:** CLI invocation on a freshly created task with an empty ledger.
- **Action run:** t1253 with `gates: [docs_updated]` and **0** gate markers (never run).
  `archive-ready 1253` → `BLOCKED:docs_updated`; `aitask_archive.sh 1253` → exit 2 with
  `GATE_PENDING:docs_updated` + `GATE_BLOCKED`; `ls aitasks/archived/t1253_*.md` → absent.
- **Verdict: pass**

## Cleanup

All performed:

- Deleted `website/content/docs/workflows/scratch-gate-probe.md` and
  `tests/test_scratch_gate_probe.sh`.
- Reverted the three tracked files the drive touched — `.aitask-scripts/aitask_lock.sh`,
  `website/content/docs/commands/lock.md`, `website/content/docs/workflows/_index.md` —
  via a **path-scoped** `git checkout --`. Each was verified clean at baseline first, so
  no concurrent session's uncommitted work was in range. (A concurrent session's syncer
  edits appeared in the tree mid-run and were deliberately left untouched.)
- Removed the scratch gate logs `.aitask-gates/{1252,1253,1254,1255}`.
- Deleted scratch tasks t1252–t1255 and committed the removals.

## Final Implementation Notes

- **Actual work done:** All 6 checklist items driven live against the real CLI surfaces
  and marked `pass`. The gate's core contract holds end to end: the headless engine
  defers procedure gates without executing anything; the attended dispatch allocates a
  run, the skill infers the correct doc page from the *configured project guide*,
  confirms with the user, applies, and closes the run exactly once; `pass`/`skip` are
  both terminal-satisfied but distinct; `fail` and never-run both fail-safe against
  archival.
- **Deviations from plan:** None in substance. One setup deviation: the task's
  `## Verification checklist` was authored with plain `- ` bullets, which
  `aitask_verification_parse.sh` does not recognize (it requires `- [ ]`), so the task
  parsed as `TOTAL:0`. The bullets were converted in place (text preserved verbatim)
  with the user's confirmation before the loop could run.
- **Issues encountered:** See upstream defects below.
- **Key decisions:** Used four separate scratch tasks rather than reusing one, so each
  terminal status (`pass` / `skip` / `fail` / unrun) was exercised on a clean ledger
  instead of being confounded by prior runs. Ran the drive against real repo surfaces
  (a real `ait lock --count` subcommand, a real new workflows page) rather than
  `TMPDIR` fixtures, because the item under test is *doc-page inference*, which a
  synthetic fixture cannot exercise.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_gate.sh:833-842 — begin-procedure's attempt counter advances by 2 per attempt. It derives `attempt` as "existing gate-run marker count for this gate + 1", but each completed attempt leaves TWO markers (the `running` block it opens plus the terminal block the skill appends). Observed live on t1255: attempts reported 1 → 3 → 5. Impact is confined to the recorded `attempt=` field and the `<attempt>` argument passed to the gate skill — the orchestrator's retry budget uses `gate_orchestrator.py:_attempts_used()`, which counts terminal `fail`/`error` runs and is therefore correct and unaffected. So this is a ledger-accuracy/reporting defect, not a gating-correctness one.
  - `.aitask-scripts/aitask_gate.sh:217-229 — cmd_append's auto-increment path for `pass`/`fail` uses the same marker-count derivation and will mis-number identically whenever `attempt=` is not passed explicitly.
  - `.claude/skills/aitask-gate-docs-updated/SKILL.md:78-84 — the change-surface gather has no per-task attribution for *uncommitted* work: `git diff --name-only HEAD` and `git ls-files --others` return the whole dirty tree, including files belonging to other tasks or concurrent sessions. During this run it surfaced four unrelated pre-existing dirty paths (`.claude/settings.local.json`, `.antigravitycli/`, `.opencode/package-lock.json`, `aidocs/slack/`), which had to be filtered by judgement. On a busy shared checkout this could drive the gate to infer doc obligations for another task's change.
  - `.aitask-scripts/aitask_verification_parse.py:32,33 + .claude/skills/task-workflow-*/manual-verification.md §1 — a manual-verification task whose checklist is authored with plain `- ` bullets parses as `TOTAL:0`, and the only offered recovery ("Seed from plan") cannot run: `cmd_seed` hard-fails with "verification checklist section already exists" because `SECTION_RE` *does* match the existing heading. The task is stuck unless the bullets are hand-converted to `- [ ]`. Either `seed` should be able to rewrite an existing section, or the TOTAL:0 branch needs a "convert existing bullets" option.
- **Notes for sibling tasks:**
  - **t635_28 (`docs_updated_activation`) is unblocked by this task passing** — the gate's
    live behavior is confirmed on all six axes, including both fail-safes.
  - The `_index.md` footgun is real and the guide already encodes it in two places; any
    future doc-guide edit should keep both the map row and the `### Known footgun` section
    in sync.
  - When driving procedure gates by hand, pass `attempt=` explicitly to `append` — do not
    rely on the auto-increment, for the reason above.
  - `aitask_archive.sh` documents `--ignore-gates` in its own refusal message; that is the
    sanctioned override when a gate genuinely cannot be satisfied.
