---
Task: t635_35_remote_web_lane_active_gates_materialization.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_16_*, t635_23_*, t635_34_*, t635_36 (archived)
Archived Sibling Plans: aiplans/archived/p635/p635_33_gate_activation_render_time.md (primary reference), p635_36_taskworkflown_rendered_set_migration.md
Base branch: main
---

# t635_35 — Remote/web lane active_gates materialization

## Context

t635_33 landed the `active_gates` model: a four-field derived tuple
(`active_gates`, `active_gates_filtered`, `active_gates_profile`,
`active_gates_digest`) is materialized at claim time via
`aitask_gate.sh materialize-active` and consumed by every enforcer. The
remote/web lanes (`aitask-pickrem`, `aitask-pickweb`) were carved out to bound
blast radius — their ownership steps never materialize, so a task picked
through those lanes falls back to raw `gates:` at every enforcer. A task with
a literal `gates: [risk_evaluated]` picked under `remote` (which renders no
gate machinery) would block archival with nothing able to satisfy the gate.
This task closes the gap.

Key exploration findings that shape the design:

- **pickrem** (`.claude/skills/aitask-pickrem/SKILL.md.j2`) has a real
  ownership claim (Step 5, `aitask_pick_own.sh`, lines 135–162) and full
  task-data access. The direct `materialize-active` call fits there,
  mirroring task-workflow Step 4.
- **pickrem is prerendered per-profile** — there is no runtime
  `active_profile_filename` variable, and its render test (Test 3b) *forbids*
  runtime profile-resolution tokens. The profile file path must be baked at
  render time.
- **Baking `{{ profile.name }}.yaml` would be wrong** under a `local/<name>.yaml`
  profile override: `aitask_skill_render.sh` resolves profiles by name via the
  scanner (which prefers `local/`), so the rendered machinery could come from
  `local/remote.yaml` while a name-derived path points at the shipped file —
  a silent ceiling mismatch (the t1147 bug class; the digest cannot catch it
  because materialize would consistently read the wrong input). Fix: inject
  the actual resolved **`profile_filename`** into the render context
  (`remote.yaml` / `local/remote.yaml` — same semantics as task-workflow's
  `active_profile_filename`).
- **pickweb makes no task-metadata writes in-session by design** ("NO
  `aitask_update.sh`", "NO `./ait git`" — SKILL.md.j2 lines 14–17); its
  render test pins those absences. Everything is deferred to the local
  `aitask-web-merge` skill via the completion marker
  (`.aitask-data-updated/completed_t<id>.json`), exactly like agent
  attribution (`implemented_with` stored in the marker, applied by web-merge
  Step 5). A tuple written in the web sandbox would also be lost — the web
  branch only carries code + `.aitask-data-updated/`. And no enforcer runs
  during the web session; the consumer is `aitask_archive.sh`'s gate guard at
  web-merge time, locally.
- `aitask-web-merge` is a static (non-templated, non-profile) skill;
  `.agents/` and `.opencode/` mirrors are redirect wrappers (no port needed).
- `remote.yaml` (live + `seed/profiles/remote.yaml`) has neither
  `default_gates` nor `rendered_gates`. The seed copy is also missing
  `headless: true` (present in the live copy) — the flag
  `aitask_skill_verify.sh` uses to discover prerender profiles.

## Design decisions (explicit, incl. one AC deviation)

1. **pickrem**: direct, always-rendered (never Jinja-gated) `materialize-active`
   call in Step 5, immediately after the claim output parsing — the
   task-workflow Step-4 call shape verbatim (all five status lines), with the
   nonzero-exit path routed to pickrem's **Abort Procedure**.
2. **pickweb — completion-marker routing (AC deviation, anticipated by the
   task):** the task's Scope 2 says "same call" but explicitly flags "may need
   the completion-marker variant like agent attribution uses". Chosen: pickweb
   does NOT call `materialize-active` in-session (would violate its
   no-metadata-writes contract and the write would not survive the sandbox);
   instead the completion marker records the profile provenance and
   **`aitask-web-merge` materializes locally**, where `aitask_update.sh`/
   task-data access exist. Review hardening (5 user concerns, all confirmed
   valid):
   - **Provenance = file identity, not just name.** The marker persists BOTH
     `"profile": "{{ profile.name }}"` and
     `"profile_filename": "{{ profile_filename }}"`. Web-merge resolves
     EXACTLY `aitasks/metadata/profiles/<profile_filename>` — no name-based
     re-resolution, no local/-preference logic — so a same-named override
     cannot silently swap the gate ceiling between web start and merge.
   - **Content drift is deliberately ACCEPTED; file identity is pinned.** This
     is the t635_33 claim-time-snapshot governance applied to the web lane:
     materialization always reads the named file's CURRENT contents (exactly
     like a local re-pick after a profile edit); what is never allowed to
     drift is WHICH file governs.
   - **Strict marker validation (the field is an authority input):**
     `profile_filename` must match `^(local/)?[A-Za-z0-9._-]+\.yaml$` (no
     `..`, no absolute paths, no other slashes), resolve inside
     `aitasks/metadata/profiles/`, and the loaded YAML's `name:` must equal
     the marker's `profile` value. Any violation is a hard validation failure,
     never a silent skip or fallback to another profile.
   - **Every materialization failure STOPS the branch before archival.** The
     helper's clear-on-fail is best-effort (t635_33 CR3F: a failed clear
     leaves an old tuple authoritative), so web-merge must never continue
     into archival after a nonzero materialize. Placement: materialization
     runs AFTER the code merge succeeds, immediately before
     attribution/archival (Step 5) — NOT before the merge: a pre-merge tuple
     write would stamp a gates-suppressing `active_gates: []` (remote) onto a
     task whose implementation never lands if the merge conflicts or is
     abandoned, wrongly unblocking dependents / satisfying the archival guard
     from profile-less readers until some later pick re-materializes. After a
     successful merge the implementation has landed, so a retained tuple is
     consistent state. Failure recovery: interactive Retry (fix + re-run the
     step) / Abort this branch (code stays merged — already committed — task
     stays unarchived; re-running `aitask-web-merge` later resumes with a
     no-op merge, or the user repairs via `aitask_gate.sh
     materialize-active` + `ait archive` manually).
   - **Legacy markers** (no `profile`/`profile_filename` fields) skip the
     call — raw-`gates:` fallback governs (never guess). Skip ≠ failure:
     validation failures on a PRESENT field always stop.
   - **Helper-script seam for testability:** the parse→validate→resolve→
     materialize sequence is encapsulated in a whitelisted helper (extend
     `aitask_web_merge.sh` with a `materialize <task_id> <marker_json>` mode)
     emitting structured one-line output, so the web handoff is unit-testable
     instead of prose-only.
3. **`profile_filename` render-context variable** (small additive change to
   `lib/skill_template.py`): derived from the profile YAML path actually used
   for the render (`local/<name>.yaml` when under `local/`, else
   `<name>.yaml`); threaded through both CLI render paths. Strict-undefined
   semantics: templates that don't use it are unaffected; using it in a
   context that doesn't supply it fails loudly.

## Implementation steps

### 1. `lib/skill_template.py` — inject `profile_filename`
- Add helper `_profile_filename(profile_yaml: Path) -> str`: `local/<basename>`
  when the file's parent dir is `local`, else `<basename>`.
- `render_skill(template_path, profile, agent_name, profile_filename=None)`:
  include `profile_filename` in the render context only when not None.
- Thread it at both call sites: `_main_legacy` (line ~449) and the
  `walk_render` loop (line ~359; `walk_render` already receives
  `profile_yaml`). Direct library callers (e.g.
  `test_profile_editor_rendered_gates.py`) are unaffected.

### 2. `.claude/skills/aitask-pickrem/SKILL.md.j2` — Step 5 materialize
Insert after the claim output parsing (after current line 162, before
`### Step 6`), unconditional (no Jinja gate):

```markdown
- **Materialize the active-gates tuple (ALWAYS runs — never profile-omitted):**
  With ownership held, derive and persist the task's enforced gate set under
  this profile:

  ```bash
  ./.aitask-scripts/aitask_gate.sh materialize-active <task_num> --profile aitasks/metadata/profiles/{{ profile_filename }}
  ```

  Parse the single stdout line:
  - `MATERIALIZED:<csv>` — active set persisted and committed.
    `MATERIALIZED:(empty)` means a fully profile-filtered (or ungated) task —
    that persisted empty set is what makes a declared-but-unrendered gate
    invisible to every enforcer. Continue.
  - `MATERIALIZED_UNCOMMITTED:<csv>` — tuple written and enforced locally, but
    the path-scoped git commit failed. Display warning and continue; a later
    `./ait git` commit of `aitasks/` picks it up.
  - `NOOP:unchanged` — re-pick under the same profile, nothing rewritten. Continue.
  - `NOOP_UNCOMMITTED:pending-persist` — unchanged but a prior commit is still
    pending. Warn as for `MATERIALIZED_UNCOMMITTED` and continue.
  - Nonzero exit — re-derivation failed; the helper clears any stale tuple
    (stderr says whether the clear succeeded), but the raw-`gates:` fallback
    does not include this profile's `default_gates`, so continuing could
    silently under-enforce. Display "active-gates materialization failed
    (<output>)" and trigger the **Abort Procedure**. Do NOT proceed to Step 6.
```

Also add a `rendered_gates` row to the Extended Profile Schema table
(render-time gate ceiling; key-presence semantics; remote ships `[]`).

### 3. `.claude/skills/aitask-pickweb/SKILL.md.j2` — marker provenance fields
- Step 8 marker JSON: add `"profile": "{{ profile.name }}"` and
  `"profile_filename": "{{ profile_filename }}"` (after `"implemented_with"`).
- Step 6/Overview: extend the deferred-operations notes — active-gates
  materialization is deferred to `aitask-web-merge` (marker provenance fields
  are the signal), alongside the existing lock/status/archival deferrals.

### 4. `aitask_web_merge.sh` — `materialize` mode (the testable seam)
Extend `.aitask-scripts/aitask_web_merge.sh` with a subcommand:

```
aitask_web_merge.sh materialize <task_id> <marker_json_file>
```

Behavior (uses the resolved ait python for JSON parsing, mirroring existing
helper conventions):
- Marker unreadable / not JSON → `WEBMAT_INVALID:bad-marker` (exit nonzero).
- Neither `profile` nor `profile_filename` present → `WEBMAT_SKIP:no-profile`
  (exit 0; legacy marker — raw-`gates:` fallback governs).
- Present but malformed → `WEBMAT_INVALID:<reason>` (exit nonzero). Checks:
  `profile_filename` matches `^(local/)?[A-Za-z0-9._-]+\.yaml$`; resolved
  path `aitasks/metadata/profiles/<profile_filename>` exists and stays inside
  the profiles dir; loaded YAML `name:` equals the marker `profile` value.
  One field present without the other is also `WEBMAT_INVALID` (a v1 marker
  always writes both).
- Validation OK → run `./.aitask-scripts/aitask_gate.sh materialize-active
  <task_id> --profile <resolved_file>`; forward its status:
  `WEBMAT_OK:<status-line>` (exit 0) for the MATERIALIZED/NOOP forms
  (including the `*_UNCOMMITTED` variants, which the caller warns about), or
  `WEBMAT_FAIL:<exit>:<output>` (exit nonzero) on a nonzero materialize exit.
Add the subcommand to the skill-bash whitelist if one applies (check
`aitask-audit-wrappers` helper coverage conventions).

### 5. `.claude/skills/aitask-web-merge/SKILL.md` — materialize after merge, before archival + hard stop
New sub-step at the TOP of Step 5 (after the Step 3 merge and Step 4 plan
copy succeeded, before attribution/archival — the implementation has landed,
so the tuple write cannot stamp gate suppression onto an unlanded task):

```markdown
**Materialize the active-gates tuple (before attribution/archival):**

  ./.aitask-scripts/aitask_web_merge.sh materialize <task_id> <marker_json_file>

- `WEBMAT_SKIP:no-profile` — legacy marker; raw `gates:` fallback governs.
  Continue.
- `WEBMAT_OK:<status>` — continue; if `<status>` is
  `MATERIALIZED_UNCOMMITTED:*` or `NOOP_UNCOMMITTED:*`, warn that the tuple
  is enforced locally but not yet committed.
- `WEBMAT_INVALID:<reason>` or `WEBMAT_FAIL:<exit>:<output>` — do NOT
  continue to archival: a failed re-derivation may leave a previous tuple
  authoritative (the helper's clear is best-effort), so proceeding could
  enforce the wrong gate set. Use `AskUserQuestion`: "Active-gates
  materialization failed for t<task_id> (<reason>). Retry after fixing, or
  abort this branch?" — Options: "Retry" (re-run this sub-step) / "Abort
  this branch" (the code merge is already committed and stays; the task
  stays unarchived — re-running `aitask-web-merge` later resumes with a
  no-op merge, or repair manually via `aitask_gate.sh materialize-active` +
  `ait archive`). Never self-append a gate result to work around the
  failure.
```

Plus a gate-guard note on the Step 5 archive call (mirroring pickrem Step
10's backstop): if `aitask_archive.sh` exits nonzero with
`GATE_PENDING:<csv>`, archival did NOT happen — surface the pending gates
(reviewer runs `ait gate pass` / `ait gates run <task_id>`, then re-runs
`aitask-web-merge`); never self-signal a human gate.

### 6. Profiles: `rendered_gates: []`
- `aitasks/metadata/profiles/remote.yaml`: add `rendered_gates: []` (the
  explicit render-nothing override — key-presence semantics from t635_33).
- `seed/profiles/remote.yaml`: same; **also add the missing `headless: true`**
  (explicit small scope addition: without it a seeded project's remote profile
  is not discovered as a prerender profile by `aitask_skill_verify.sh`).
- Predict: this YAML edit alone produces ZERO render diff (remote's
  `rendered_set` was already `[]` via the no-`default_gates` fallback) —
  verify before layering the template edits.

### 7. Rerender + goldens (same commit as template edits)
- `./.aitask-scripts/aitask_skill_rerender.sh remote` — re-renders the
  committed `-remote-` trees across `.claude/`, `.agents/`, `.opencode/`
  (incl. the transitive `task-workflow-remote-` closure, which should be
  unchanged).
- Regenerate `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md` and
  `tests/golden/skills/aitask-pickweb/SKILL-remote-claude.md` via the
  documented `skill_template.py` loop; review the diff (expected: exactly the
  new blocks).
- `./.aitask-scripts/aitask_skill_verify.sh` must pass.

### 8. Tests
- `tests/test_skill_render_aitask_pickrem.sh`: assert the remote render
  contains the `materialize-active` call with the literal
  `--profile aitasks/metadata/profiles/remote.yaml` (proves
  `profile_filename` resolved, not leaked) and the abort-on-failure line; add
  an all-profiles loop (default/fast/remote) asserting each render contains
  the call with its own profile path (verification bullet "all profiles");
  add a `profile_filename` context check rendering a fixture profile from
  `local/` → path renders as `local/<name>.yaml` — exercised through BOTH
  paths: the direct renderer CLI AND the production
  `aitask_skill_render.sh` walk path (create a temporary
  `aitasks/metadata/profiles/local/<name>.yaml` fixture profile, run
  `aitask_skill_render.sh aitask-pickrem --profile <name> --agent claude`
  so the scanner+walk_render chain resolves it, assert the rendered
  `SKILL.md` embeds `--profile aitasks/metadata/profiles/local/<name>.yaml`,
  and do the same for pickweb asserting the marker emits
  `"profile_filename": "local/<name>.yaml"`; trap-clean the fixture profile
  and the rendered `-<name>-` variant dirs). This pins the threading of
  `profile_filename` through the walk/scanner path so neither CLI path can
  regress silently.
- `tests/test_skill_render_aitask_pickweb.sh`: assert the remote render
  contains `"profile": "remote"` AND
  `"profile_filename": "remote.yaml"` in the marker JSON and does NOT contain
  `materialize-active` (pins the routing decision); add a producer/consumer
  drift guard — `.claude/skills/aitask-web-merge/SKILL.md` must reference
  `aitask_web_merge.sh materialize` and the marker provenance fields, and the
  helper must exist and mention `materialize-active`.
- **New `tests/test_web_merge_materialize.sh`** — the web-handoff fixture
  matrix (fixture cwd + `TASK_DIR`, real `aitask_web_merge.sh` +
  `aitask_gate.sh`), covering the full marker→resolution→persistence→archival
  chain:
  - valid marker (`profile: remote`, `profile_filename: remote.yaml`, fixture
    profile with `rendered_gates: []`) on a task with literal
    `gates: [risk_evaluated]` → `WEBMAT_OK:MATERIALIZED:(empty)`, tuple
    present in the task file, `archive-ready` → `NO_GATES`;
  - **pre-existing tuple**: task already carrying a fast-stamped
    `active_gates: [risk_evaluated]` tuple → re-materialized to `[]` under
    the marker profile (supersedes, not preserves);
  - legacy marker (no profile fields) → `WEBMAT_SKIP:no-profile`, task file
    untouched, raw `gates:` governs (`archive-ready` → `BLOCKED`);
  - invalid markers → `WEBMAT_INVALID` + nonzero exit + task file untouched:
    path traversal (`../evil.yaml`), absolute path, nonexistent file,
    `name:` mismatch between YAML and marker `profile`, one provenance field
    without the other, non-JSON marker;
  - materialization failure (marker points at a malformed profile, e.g.
    scalar `rendered_gates`) → `WEBMAT_FAIL` + nonzero exit; assert the
    prior-tuple state is NOT silently trusted (tuple cleared, or the test
    documents the helper's clear-failed warning path).
- `tests/test_gate_active_gates.sh`: add the remote-lane negative control
  against the REAL profile — fixture task with `gates: [risk_evaluated]`
  materialized with the repo's `aitasks/metadata/profiles/remote.yaml` →
  `MATERIALIZED:(empty)`, then `archive-ready` → `NO_GATES`.
- **Seed parity guard** (in `test_web_merge_materialize.sh` or the pickweb
  render test): `seed/profiles/remote.yaml` and
  `aitasks/metadata/profiles/remote.yaml` both contain `headless: true` and
  `rendered_gates: []` — pins the seeded-project prerender-discovery path.
- Run: the two render tests, the new web-merge test,
  `test_gate_active_gates.sh`, `test_profile_editor_rendered_gates.py`
  (remote.yaml round-trip is covered by its existing `rendered_gates: []`
  cases), `aitask_skill_verify.sh`, `shellcheck` on the edited helper.

## Files touched
- `.aitask-scripts/lib/skill_template.py`
- `.aitask-scripts/aitask_web_merge.sh` (new `materialize` subcommand)
- `.claude/skills/aitask-pickrem/SKILL.md.j2`
- `.claude/skills/aitask-pickweb/SKILL.md.j2`
- `.claude/skills/aitask-web-merge/SKILL.md`
- `aitasks/metadata/profiles/remote.yaml`, `seed/profiles/remote.yaml`
- Rendered `-remote-` trees (`.claude/`, `.agents/`, `.opencode/`) + 2 goldens
- `tests/test_skill_render_aitask_pickrem.sh`,
  `tests/test_skill_render_aitask_pickweb.sh`,
  `tests/test_gate_active_gates.sh`, new `tests/test_web_merge_materialize.sh`

## Verification (end-to-end)
1. Both render tests + new `test_web_merge_materialize.sh` +
   `test_gate_active_gates.sh` + `test_profile_editor_rendered_gates.py`
   pass; `aitask_skill_verify.sh` passes; `shellcheck` clean on
   `aitask_web_merge.sh`.
2. Golden diffs contain exactly the new blocks (predict-render-diff).
3. Remote-lane negative control (helper-level, real remote.yaml): literal
   `gates: [risk_evaluated]` → `active_gates: []` → archivable with no manual
   append — plus the same flow through the web-marker helper seam.
4. Step 9 (Post-Implementation): cleanup, archival (fast profile: current
   branch, no worktree/merge).

## Risk

### Code-health risk: medium
- `skill_template.py` render-context change touches the shared render seam
  every skill goes through; a regression breaks rendering framework-wide ·
  severity: medium · → mitigation: additive-only signature (default None),
  strict-undefined fails loudly, full `aitask_skill_verify.sh` + goldens regen
  in-task
- Prose-coupled producer/consumer contract (pickweb marker provenance fields
  ↔ web-merge materialize step) can drift silently · severity: medium · →
  mitigation: helper-script seam (`aitask_web_merge.sh materialize`) +
  drift-guard asserts in `test_skill_render_aitask_pickweb.sh` (in-task)
- Marker provenance is an authority input for gate selection; a malformed or
  altered marker could select an unintended profile/path · severity: medium ·
  → mitigation: strict validation in the helper (filename pattern, in-dir
  resolution, name↔filename cross-check) + `WEBMAT_INVALID` fixture matrix
  (in-task)
- Rendered-tree blast radius (3 agent roots × remote closure + 2 goldens);
  partial regen ships stale prerenders · severity: low · → mitigation:
  `aitask_skill_verify.sh` freshness check + same-commit goldens rule

### Goal-achievement risk: low
- The full remote/web lane cannot be exercised end-to-end in automated tests
  (needs a live Claude Web session / headless pickrem run); the web handoff
  chain is now unit-tested via the helper seam, but the live lane remains
  manual · severity: low · → mitigation: t1224 (remote_lane_gate_live_verify)

### Planned mitigations
- timing: after | name: remote_lane_gate_live_verify (created: t1224) | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement lane e2e coverage | desc: Live remote-lane verification — run /aitask-pickrem on a throwaway task with literal gates: [risk_evaluated]; confirm the tuple materializes as [] at claim, the task archives without a manual gate append, and a pickweb marker round-trips its profile field through aitask-web-merge materialization.

## Post-Review Changes

### Change Request 1 (2026-07-23 18:20)
- **Requested by user:** Four review concerns, all confirmed: (1, high)
  `_profile_filename` used `Path.resolve()`, which follows a
  `profiles/local/foo.yaml` symlink to its target before the `local/` parent
  check — the renderer then baked `foo.yaml` instead of `local/foo.yaml`, so
  materialization could read the shipped profile instead of the local
  override (the exact ceiling mismatch the change exists to prevent);
  additionally `_main_walk` / `_main_walk_verify` pre-resolve the profile
  path before it ever reaches the helper. (2, medium) The new materialize
  procedures were inlined into `aitask-pickrem/SKILL.md.j2` and
  `aitask-web-merge/SKILL.md` despite the skill-authoring convention that
  substantial new procedures live in their own file with a thin caller
  reference. (3, medium) `cmd_materialize` captured only stdout from
  `materialize-active`, but the failure diagnostic goes to stderr — so
  `WEBMAT_FAIL:<rc>:<output>` usually ended with an empty reason and the
  interactive retry prompt could not say what failed. (4, low) the render
  test wrote a FIXED `local/zzt63535.yaml` fixture unconditionally (could
  overwrite a same-named user file) and its glob cleanup could remove
  matching user artifacts.
- **Changes made:** (1) `_profile_filename` now normalizes lexically only
  (`os.path.normpath`, never `resolve()`), and the provenance filename is
  derived from the ORIGINAL CLI argument in `_main_legacy`, `_main_walk`,
  and `_main_walk_verify` before any `resolve()`, then threaded through a
  new `walk_closure(profile_filename=...)` parameter (library callers keep a
  derive-from-`profile_yaml` fallback). New regression: a symlinked
  `local/<name>sym.yaml` fixture renders `local/<name>sym.yaml`, not the
  target's name. (2) Extracted both procedures into their own files with
  thin caller references: `.claude/skills/aitask-pickrem/materialize-active.md`
  (Jinja `{{ profile_filename }}`, part of the rendered closure across all
  3 agent roots) and `.claude/skills/aitask-web-merge/materialize-gates.md`;
  render tests updated to assert the procedure files and the SKILL
  references. (3) `cmd_materialize` captures stderr separately: success
  passes advisory WARNs through to its own stderr; failure appends the
  stderr diagnostic to the `WEBMAT_FAIL` line — with a test asserting the
  reason is non-empty. (4) The fixture name is now unique per run
  (`zzt63535_$$_$RANDOM`), the test refuses to run if the path already
  exists, and `local/` dir removal only happens when the test created it.
- **Files affected:** `.aitask-scripts/lib/skill_template.py`,
  `.aitask-scripts/aitask_web_merge.sh`,
  `.claude/skills/aitask-pickrem/SKILL.md.j2`,
  new `.claude/skills/aitask-pickrem/materialize-active.md`,
  `.claude/skills/aitask-web-merge/SKILL.md`,
  new `.claude/skills/aitask-web-merge/materialize-gates.md`,
  `tests/test_skill_render_aitask_pickrem.sh`,
  `tests/test_skill_render_aitask_pickweb.sh`,
  `tests/test_web_merge_materialize.sh` (61 asserts), rendered `-remote-`
  trees (+ new `materialize-active.md` closure files) and both goldens.

### Change Request 2 (2026-07-23 18:35)
- **Requested by user:** (medium) The symlinked-local-profile regression was
  tested only through the direct renderer CLI; the production
  `aitask_skill_render.sh` walk test still used a regular local file — but
  the original bug lived in the walk path AFTER its `resolve()`, so the
  suite would not catch a regression that moves `profile_filename`
  derivation after the resolve again.
- **Changes made:** Added walk-path symlink coverage (Test 10 Path B2): a
  base `profiles/<name>.yaml` plus `local/<name>.yaml` symlinked to it — the
  scanner's same-filename merge selects the local/ layer, so
  `aitask_skill_render.sh --profile <name>` renders from the symlink — and
  the rendered `materialize-active.md` must retain
  `local/<name>.yaml` in the baked path. Verified as a live negative
  control: temporarily reintroducing the resolve-first derivation in
  `_main_walk` makes exactly this assert fail; the restored fix passes.
  Fixture names remain unique-per-run with refuse-to-overwrite checks and
  exact-path cleanup.
- **Files affected:** `tests/test_skill_render_aitask_pickrem.sh` (67
  asserts now).

## Final Implementation Notes
- **Actual work done:** Landed the full plan: `profile_filename` render-context
  variable in `lib/skill_template.py` (lexical derivation from the original
  CLI argument in all three entry points, threaded via a new
  `walk_closure(profile_filename=...)` parameter); pickrem Step-5
  materialization as its own procedure file
  (`.claude/skills/aitask-pickrem/materialize-active.md`, thin caller
  reference, task-workflow Step-4 status handling, abort-on-failure) plus a
  `rendered_gates` schema-table row; pickweb completion-marker provenance
  fields (`profile` + `profile_filename`) with the deferral documented;
  `aitask_web_merge.sh materialize <task_id> <marker_json>` validating
  helper (strict fail-closed marker validation: filename pattern, in-dir
  realpath containment, YAML-name↔marker cross-check, partial/non-string
  rejection; separate stderr capture so WEBMAT_FAIL carries the real
  diagnostic; WEBMAT_OK/SKIP/INVALID/FAIL protocol); web-merge Step-5
  materialization procedure file (`materialize-gates.md`) running after the
  merge and hard-stopping before archival on any failure, plus a
  GATE_PENDING backstop on the archive call; `rendered_gates: []` in live
  remote.yaml and the seed copy (which also gained the missing
  `headless: true`); rerendered `-remote-` trees across the 3 agent roots
  (new `materialize-active.md` closure files committed) and both goldens.
  Tests: new `tests/test_web_merge_materialize.sh` (61 asserts — valid /
  supersede-prior-tuple / legacy-skip / 10-case invalid matrix /
  local-profile / failure-clears-stale + non-empty diagnostic); pickrem
  render test +Tests 9-10 (per-profile procedure render, local/ + SYMLINKED
  local/ threading through BOTH the direct CLI and the production
  scanner+walk path); pickweb render test +Tests 10-11 (marker provenance,
  producer/consumer drift guards, seed/live profile parity); gate test
  +remote-lane negative control against the real remote.yaml (99/99).
- **Deviations from plan:** (1) The pickweb lane uses the completion-marker
  routing (as the plan decided — the task's "same call" wording was
  explicitly conditioned on this variant); pickweb itself renders NO
  materialize call, pinned by test. (2) Two review rounds (see Post-Review
  Changes): symlink-safe lexical provenance derivation + original-argument
  threading, procedure-file extraction per the authoring convention,
  stderr-carrying WEBMAT_FAIL, unique/refuse-overwrite test fixtures, and
  walk-path symlink regression coverage verified by a live negative control.
  (3) The `active_gates_profile` stamp for local/ profiles is path-derived
  (`local/<stem>`, t635_33 `_profile_stamp_name`) — the web-merge helper's
  name cross-check validates the YAML `name:` against the marker's `profile`
  field instead (file identity and declared name are both pinned).
- **Issues encountered:** bash command substitution strips NUL, so the
  helper's non-string JSON sentinel uses `\x01`; the initial local-profile
  test expectation assumed the YAML name is stamped (it is the path-derived
  scanner-style name); pre-commit "matches HEAD" freshness asserts in both
  render tests fail by design until this change is committed.
- **Key decisions:** file-identity provenance (marker records BOTH `profile`
  and `profile_filename`; merge-time resolution uses EXACTLY the recorded
  filename — no name-based re-resolution); content drift between web start
  and merge is deliberately accepted (t635_33 claim-time-snapshot
  governance), file identity is not; materialization in web-merge runs AFTER
  a successful merge and before archival (a pre-merge write could stamp
  gate-suppressing state onto an unlanded task); every materialization
  failure stops the branch (the helper's clear-on-fail is best-effort);
  legacy markers skip (never guess), but validation failures on a present
  field always stop; `profile_filename` derivation is lexical-only —
  `Path.resolve()` would follow local/ symlinks and drop the override
  provenance.
- **Upstream defects identified:** seed/profiles/remote.yaml:1 — pre-existing:
  the seed copy was missing `headless: true` (present in the live profile),
  so a seeded project's remote profile would not be discovered as a
  prerender profile by aitask_skill_verify.sh; fixed in this task (seed
  parity now pinned by test), no follow-up needed.
- **Notes for sibling tasks:** the `profile_filename` render-context variable
  is available to every skill template (scanner-style, `local/`-aware,
  symlink-safe); reuse it wherever a prerendered lane needs a baked profile
  path. The `aitask_web_merge.sh materialize` verb is the canonical
  web-marker → tuple bridge; t635_23 (codex/opencode gate wrappers) and
  t635_16 (remote projection) should route any web-lane gate work through
  it rather than re-parsing markers. The remote lane's declared ceiling is
  now explicit (`rendered_gates: []` in remote.yaml both live and seed).
