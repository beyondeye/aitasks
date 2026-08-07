---
Task: t635_23_port_gate_skills_codex_opencode.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_*.md
Archived Sibling Plans: aiplans/archived/p635/p635_*_*.md
Worktree: (none — current-branch mode, profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t635_23 — Port the three gate skills to the Codex CLI and OpenCode trees

## Context

t635_11 and t635_19 shipped three **plain** (non-Jinja, non-profile-aware) Claude
skills — `aitask-run-gates`, `aitask-gate-template`, `aitask-gate-docs-updated`.
Plain skills do not auto-render to the other agent trees, so all three exist only
under `.claude/skills/`. The repo's own auditor confirms the gap:

```
$ ./.aitask-scripts/aitask_audit_wrappers.sh discover
GAP:{agents,opencode-skill,opencode-command}:aitask-gate-docs-updated
GAP:{agents,opencode-skill,opencode-command}:aitask-gate-template
GAP:{agents,opencode-skill,opencode-command}:aitask-run-gates
```

This is a **live** defect, not a latent one: the task-workflow Step-8 procedure-gate
dispatch is already rendered into the Codex and OpenCode trees
(`.agents/skills/task-workflow-fast-codex-/SKILL.md`,
`.opencode/skills/task-workflow-fast-/SKILL.md`) and instructs those agents to
resolve `aitask-gate-<name>` **in their own skill tree** — where the file does not
exist. `docs_updated` is therefore Claude-only today.

Intended outcome: the three skills carry their wrapper surface in every installed
agent tree, the prose that says otherwise stops saying it, and the helper scripts
those skills shell out to are permitted in every agent's policy file.

**Scope boundary (from the task file):** this ports the wrapper FILES only.
Making the Step-8/Step-9 dispatch *resolution* formally agent-aware, and per-gate
code-agent/model selection, belong to **t635_29** and are out of scope here.

## Design

The framework already owns the generator: `aitask_audit_wrappers.sh` renders each
tree's stub from the canonical Claude `SKILL.md`
(`render_agents_skill` / `render_opencode_skill` / `render_opencode_command`,
`.aitask-scripts/aitask_audit_wrappers.sh:250-372`). All three skills are plain
(no `SKILL.md.j2`), so `_skill_is_templated()` is false and each gets the legacy
"Source of Truth" pointer stub plus the per-agent tool-mapping reference.

**Key decision — ship pure generator output, hand-edit nothing.** The stubs are
pointers, not copies: tool-name translation lives in the shared mapping docs
(`.agents/skills/codex_tool_mapping.md` maps `AskUserQuestion` →
`functions.request_user_input`; `.opencode/skills/opencode_tool_mapping.md` maps it
→ `ask`), which the stubs already reference. Hand-editing a generated stub is what
produced the existing drift in `aitask-contribute`'s OpenCode surfaces
(`aidocs/framework/adding_a_new_codeagent.md` §12c) and would break
`apply-wrapper --force` refresh. Agent-specific wording that *is* needed goes into
the **canonical Claude body** instead (Phase B), where it propagates transitively.

All three trees get all three skills: `cmd_parity()` compares wrapper-set
membership across trees, so shipping two of three would newly emit
`PARITY_GAP` and fail `aitask_skill_verify.sh`.

## Implementation

### Phase A — Generate the 9 wrappers

```bash
for s in aitask-run-gates aitask-gate-template aitask-gate-docs-updated; do
  for t in agents opencode-skill opencode-command; do
    ./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper "$t" "$s"
  done
done
```

Expect exactly 9 `WROTE:` lines (no `--force` — none of the targets exists, and a
refusal would mean an unexpected pre-existing file). Targets:
`.agents/skills/<skill>/SKILL.md`, `.opencode/skills/<skill>/SKILL.md`,
`.opencode/commands/<skill>.md`.

### Phase B — Retire the now-false "Claude-only" prose

Each edit is in the **canonical Claude source**; the wrappers point at it, so no
per-tree duplication.

1. `.claude/skills/aitask-gate-template/SKILL.md:128` — `(a
   `.claude/skills/aitask-gate-<name>/`)` → an agent-tree-agnostic phrasing
   (`an `aitask-gate-<name>/` skill dir in each agent's skill tree`).
2. `.claude/skills/aitask-gate-template/SKILL.md:147` — `Read-and-follow
   `.claude/skills/aitask-gate-<name>/SKILL.md`` → `Read-and-follow the
   `aitask-gate-<name>` skill's `SKILL.md` **in your agent's skill tree**`,
   matching the wording already used at `.claude/skills/task-workflow/SKILL.md:475`.
3. `.claude/skills/aitask-gate-template/SKILL.md` `## Notes` — add the durable
   authoring instruction this task's own gap proves is missing: a new
   `aitask-gate-<name>` skill must also ship its three wrapper surfaces via
   `./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper {agents,opencode-skill,opencode-command} aitask-gate-<name>`,
   because plain skills do not auto-render.
4. `.claude/skills/aitask-gate-docs-updated/SKILL.md:147` — replace
   "Codex / OpenCode ports of the gate skills are tracked under **t635_23**." with a
   current-state line naming the three shipped surfaces (current-state-only rule,
   `aidocs/framework/documentation_conventions.md`).
5. `.aitask-scripts/gates_reference.yaml:182` **and** `aitasks/metadata/gates.yaml:182`
   (same line in both; the second is data-branch) — the comment
   `# The verifier names a SKILL (.claude/skills/aitask-gate-docs-updated/), not a`
   → agent-tree-agnostic.
6. `.claude/skills/task-workflow/SKILL.md:475` (Jinja closure) — drop the clause
   "Gate skills currently ship in the Claude tree; per-agent Codex/OpenCode wrappers
   are tracked in **t635_23**." Keep the surrounding sentence and the
   t635_19-follow-up clause about per-gate agent/model selection.

   The block is gated on `{% if profile.record_gates %}`, so only the **fast**
   profile renders it. Re-render and regenerate goldens:

   ```bash
   ./.aitask-scripts/aitask_skill_rerender.sh default
   ./.aitask-scripts/aitask_skill_rerender.sh fast
   ./.aitask-scripts/aitask_skill_rerender.sh remote

   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for p in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       .claude/skills/task-workflow/SKILL.md \
       aitasks/metadata/profiles/$p.yaml claude \
       > tests/golden/procs/task-workflow/SKILL-$p.md
   done
   ```

   Only these should change; every other rerender target must be diff-clean:
   - `.claude/skills/task-workflow-fast-/SKILL.md`
   - `.agents/skills/task-workflow-fast-codex-/SKILL.md`
   - `.opencode/skills/task-workflow-fast-/SKILL.md`
   - `tests/golden/procs/task-workflow/SKILL-fast.md`

### Phase C — Helper-script whitelist coverage

The gate skills shell out to helpers that are not permitted in every agent's policy
file, so a ported skill would stall on a permission prompt:

- `aitask_resolve_config_path.sh` — invoked at `aitask-gate-docs-updated/SKILL.md:53`;
  currently missing from **all five** touchpoints (`MISSING:1,3,4,6,7`).
- `aitask_run_gates.sh` — missing from touchpoint 1 (`.claude/settings.local.json`).

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_resolve_config_path.sh
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_run_gates.sh
```

Touchpoints: `.claude/settings.local.json` (1), `.codex/rules/default.rules` (3),
`seed/claude_settings.local.json` (4), `seed/codex_rules.default.rules` (6),
`seed/opencode_config.seed.json` (7).

## Commit routing

- **Code branch (plain `git`):** `.agents/**`, `.opencode/**`, `.claude/skills/**`,
  `.aitask-scripts/gates_reference.yaml`, `.claude/settings.local.json`,
  `.codex/rules/default.rules`, `seed/**`, `tests/golden/**`.
- **Data branch (`./ait git`):** `aitasks/metadata/gates.yaml`.

Stage every path explicitly — the rerender driver walks every closure for a profile
and concurrent sessions may have unrelated files dirty in the tree.

### Post-phase (risk mitigations)

1. `[sweep_path_allowlist]` After the Phase B6 rerender + golden regeneration, run
   `git status --porcelain` and reconcile it against the expected path set for this
   task. The **only** rerender-produced paths permitted in the commit are:
   `.claude/skills/task-workflow-fast-/SKILL.md`,
   `.agents/skills/task-workflow-fast-codex-/SKILL.md`,
   `.opencode/skills/task-workflow-fast-/SKILL.md`,
   `tests/golden/procs/task-workflow/SKILL-fast.md`.
2. `[sweep_path_allowlist]` **Non-destructive rule — never revert an unexpected
   path.** A rerender sweep cannot distinguish accidental churn from another
   session's in-progress work or pre-existing drift, so no `git checkout --`,
   `git restore`, `git stash`, or `git clean` runs here. For any dirty path
   outside the four-path allowlist: inspect its diff, **leave it untouched**, and
   report it to the user by path with a one-line characterization (looks like
   rerender churn / looks like foreign work / unclear). Ownership is the user's
   call; the commit proceeds without those paths either way.
3. `[sweep_path_allowlist]` Stage the explicit path list only — never `git add -A`
   or `git add <dir>`.
4. `[sweep_path_allowlist]` Diff each of the four allowed paths and confirm the
   change is exactly the removed "Gate skills currently ship in the Claude tree…"
   clause — an unrelated diff means a template regression, not a rerender artifact.

## Verification

1. **Negative control (already captured, pre-change):**
   `./.aitask-scripts/aitask_audit_wrappers.sh discover` lists 9 `GAP:` lines for the
   three gate skills; `audit-helper-whitelist aitask_resolve_config_path.sh` prints
   `MISSING:1,3,4,6,7`.
2. **After Phase A/C:** `discover` emits **no** line for the three gate skills (only
   the pre-existing `aitask-explorechat` triple remains — out of scope, see below);
   `audit-helper-whitelist` for both helpers prints nothing.
3. `./.aitask-scripts/aitask_audit_wrappers.sh parity` → no `PARITY_GAP:` / `ORPHAN:`.
4. `./.aitask-scripts/aitask_skill_verify.sh` → passes (it runs `parity` and the
   prerender-freshness check that Phase B's closure edit affects).
5. `bash tests/test_opencode_setup.sh` (Test 0 is the parity assertion).
6. `bash tests/test_skill_render_task_workflow.sh` (goldens, agent byte-identity).
7. `bash tests/test_skill_dispatch_contract.sh`.
8. `bash tests/test_gate_procedure_docs.sh` (15/15 — unchanged by this task; proves
   the engine side still behaves).
9. Spot-read one rendered wrapper per tree to confirm the description was scraped
   from the canonical frontmatter and the tool-mapping pointer is present.

No `.sh` files are edited, so no `shellcheck` run is required.

### What checks 1–9 do and do not establish

Checks 1–9 are **static**: they prove the wrapper files exist, that the three
trees agree, that the generated bodies carry the right description and
tool-mapping pointer, that the policy files contain the right permission strings,
and that no closure/golden drifted. They do **not** execute anything in Codex CLI
or OpenCode. Nothing here shows that either agent can actually run
`aitask-gate-docs-updated`: that its tool mapping translates the
`AskUserQuestion` confirmation step into a real prompt, that
`aitask_resolve_config_path.sh` runs without a permission interruption under the
newly added policy entries, or that the terminal ledger block is appended.

**Acceptance condition for the end-to-end claim.** The port is
`aitask-gate-docs-updated` **is runnable on Codex and OpenCode** only once
`cross_agent_gate_live_verify` (the spawned `after` manual-verification task)
passes. Until then this task's completion claim is scoped to *"the wrapper
surfaces exist, agree across trees, and the helpers they invoke are permitted"* —
the Final Implementation Notes and the task's closing summary must say exactly
that and name the MV as the outstanding gate. Do **not** describe the port as
verified end-to-end on the strength of checks 1–9.

## Out of scope (recorded, not fixed)

- `aitask-explorechat` has the same 3-tree gap. It is a machine-spawned chatlink
  gateway skill ("Not a user task command"), not a gate skill — deliberately left.
- `.claude/settings.local.json` is also missing the `aitask_gate_{build,fail,lint,
  log,pass,risk,record,tests_pass}.sh` verifiers that `seed/` and the Codex rules
  already carry. Not required by this port; recorded as an upstream defect.

## Step 9

Reference **Step 9 (Post-Implementation)** of the shared task-workflow for cleanup,
archival (child → `aitasks/archived/t635/`), and merge.

## Risk

### Code-health risk: medium
- Phase B6 edits the **shared** `task-workflow/SKILL.md` closure (consumed by every
  task-based skill) and then runs `aitask_skill_rerender.sh`, which walks *every*
  rendered closure for a profile — a generated sweep whose diff can pick up churn
  unrelated to this task, and a missed variant leaves committed prerenders stale
  (`PRERENDER_FAIL` in `aitask_skill_verify.sh`) · severity: medium ·
  → mitigation: inline post-phase sweep_path_allowlist
- Phase A/C write only generator output and script-applied whitelist entries; both
  are additive, idempotent, and re-derivable (`apply-wrapper --force`) ·
  severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- The port's *purpose* is that a Codex or OpenCode agent can actually complete
  `aitask-gate-docs-updated` end-to-end. Pointer stubs make the file resolve, but
  nothing here proves the tool mapping carries the `AskUserQuestion` confirmation
  step or that the new whitelist entries are honoured in a live session — this is
  agent-driven behavior, not unit-testable · severity: medium ·
  → mitigation: t1457 (its pass is the explicit acceptance
  condition for the end-to-end claim — see "What checks 1–9 do and do not
  establish")
- **Recurrence:** `cmd_discover` (the only check that walks the Claude tree for
  missing wrappers) is *not* wired into `aitask_skill_verify.sh`; `cmd_parity` only
  compares wrapper trees to each other, so a skill absent from *all* trees is
  invisible. That is precisely why these three sat unported. After this lands the
  same hole remains open for the next Claude-only skill · severity: medium ·
  → mitigation: t1458

### Planned mitigations
- timing: post-phase | name: sweep_path_allowlist | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "rerender sweep drags unrelated churn / stale prerenders" | desc: after the Phase B6 rerender, reconcile `git status` against an explicit four-path allowlist and stage only those paths.
- timing: after | name: cross_agent_gate_live_verify | type: manual_verification | priority: medium | effort: low | inline_risk: high | added_complexity: high | addresses: goal-achievement "pointer stubs prove resolution, not agent behavior" | desc: drive aitask-gate-docs-updated end-to-end from a live Codex CLI session and a live OpenCode session — wrapper resolves, the tool mapping carries the AskUserQuestion confirmation step, aitask_resolve_config_path.sh runs unprompted, and the terminal ledger block lands. ACCEPTANCE-GATING: this task's end-to-end "runnable on Codex/OpenCode" claim is not established until this MV passes. | created: t1457
- timing: after | name: wire_discover_into_verify | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement "recurrence — a skill absent from ALL wrapper trees is invisible to parity" | desc: wire `aitask_audit_wrappers.sh discover` into `aitask_skill_verify.sh` behind an explicit Claude-only exemption list (aitask-explorechat is deliberately unported), so the next plain Claude skill cannot silently ship without wrappers. | created: t1458

## Final Implementation Notes

- **Actual work done:** Generated the 9 missing wrapper surfaces via
  `aitask_audit_wrappers.sh apply-wrapper` — `aitask-run-gates`,
  `aitask-gate-template` and `aitask-gate-docs-updated` each now ship
  `.agents/skills/<skill>/SKILL.md`, `.opencode/skills/<skill>/SKILL.md` and
  `.opencode/commands/<skill>.md`. Retired the now-false Claude-only prose at its
  canonical sources: `aitask-gate-template/SKILL.md` (the two hardcoded
  `.claude/skills/aitask-gate-<name>/` references → agent-tree-agnostic), plus a new
  Notes entry making "a new gate skill must also ship its three wrapper surfaces" a
  durable authoring rule; `aitask-gate-docs-updated/SKILL.md` (t635_23 port ticket →
  current-state description of the shipped surfaces); `task-workflow/SKILL.md`
  Step-8 dispatch (dropped "Gate skills currently ship in the Claude tree…") with the
  `SKILL-fast.md` golden regenerated; and the `docs_updated` verifier comment in both
  `.aitask-scripts/gates_reference.yaml` and `aitasks/metadata/gates.yaml`.
  Closed the helper-whitelist gaps the ported skills depend on:
  `aitask_resolve_config_path.sh` (invoked by the docs gate, previously whitelisted in
  **none** of the 5 touchpoints) and `aitask_run_gates.sh` (missing from touchpoint 1).

- **Deviations from plan:** (1) **Scope-reducing** — the plan's Phase B6 assumed the
  three rendered `task-workflow-fast-` closures were tracked files requiring
  `aitask_skill_rerender.sh` across all three profiles. They are **gitignored
  per-user artifacts** (`.gitignore` ignores `*-/` in all three skill roots; only the
  `remote` headless prerenders are committed), and the edited clause is
  `record_gates`-gated so only `fast` renders it — meaning the committed prerenders
  are unaffected. Rendered via `aitask_skill_render.sh aitask-pick --profile fast
  --agent {claude,codex,opencode}` instead, whose closure walk refreshes exactly the
  three local fast closures. Tracked footprint of the closure edit is therefore the
  Jinja source plus one golden, and the `sweep_path_allowlist` mitigation found **zero**
  rerender churn to reconcile. (2) `aitask_skill_rerender.sh` could not have been
  targeted at `task-workflow` directly anyway: it skips rendered dirs with no
  authoring template, and `task-workflow` has no `SKILL.md.j2` — it is only reachable
  through an entry-point skill's closure walk. (3) `test_gate_procedure_docs.sh` is
  34 assertions now, not the 15 the archived p635_19 plan recorded; all pass.

- **Issues encountered:** None blocking. The working tree carried an unrelated
  concurrent session's in-flight work (board-groups / merge / sync: `aitask_sync.sh`,
  `aitask_fold_mark.sh`, `aitask_update.sh`, `board/aitask_merge.py`,
  `lib/task_yaml.py`, `lib/board_groups.py`, four `tests/*`, and
  `aidocs/framework/aitasks_extension_points.md`). Per the post-phase mitigation's
  non-destructive rule those were inspected, left untouched, reported to the user, and
  excluded from this task's commit — nothing was reverted or stashed.

- **Key decisions:** Ship **pure generator output** for all nine wrappers and
  hand-edit none of them. The stubs are pointers, not copies — tool translation lives
  in `.agents/skills/codex_tool_mapping.md` / `.opencode/skills/opencode_tool_mapping.md`,
  which the stubs already reference — so any agent-specific wording belongs in the
  canonical Claude body, where it propagates transitively. This keeps
  `apply-wrapper --force` a safe refresh and avoids the drift that hand-editing
  produced in `aitask-contribute`'s OpenCode surfaces. All three trees got all three
  skills because `cmd_parity()` compares wrapper-set membership across trees; a
  partial port would newly fail `aitask_skill_verify.sh`.

- **Scope-honesty — what is and is not established:** Every check run here is
  **static** (existence, cross-tree parity, generated body content, policy strings,
  golden/prerender freshness). Nothing was executed in Codex CLI or OpenCode. The
  verified claim is *"the wrapper surfaces exist, agree across trees, and the helpers
  they invoke are permitted."* Whether a Codex or OpenCode agent can actually complete
  `aitask-gate-docs-updated` end-to-end — tool mapping translating the
  `AskUserQuestion` confirmation, `aitask_resolve_config_path.sh` running unprompted,
  the terminal ledger block landing — remains gated on **t1457**
  (`cross_agent_gate_live_verify`), the MV created at Step 8d.

- **Upstream defects identified:**
  - .aitask-scripts/aitask_skill_verify.sh:212-244 — wires only `aitask_audit_wrappers.sh parity` (wrapper-tree vs wrapper-tree), never `discover` (Claude-tree vs wrappers), so a skill absent from ALL wrapper trees is invisible to the mandated pre-commit check; this is why these three skills sat unported. Tracked as the `wire_discover_into_verify` mitigation.
  - .claude/settings.local.json:30 — missing the `aitask_gate_{build,fail,lint,log,pass,risk,record,tests_pass}.sh` verifier entries that `seed/claude_settings.local.json`, `.codex/rules/default.rules` and `seed/opencode_config.seed.json` all carry; the runtime Claude policy is a subset of its own seed mirror.
  - .aitask-scripts/aitask_audit_wrappers.sh:226 — `discover` still reports the `aitask-explorechat` GAP triple. Deliberately out of scope here (machine-spawned chatlink gateway, not a gate skill), but it is the one remaining unported plain skill.

- **Notes for sibling tasks:** Procedure gates are no longer Claude-only — the Step-8
  dispatch's "resolve in your agent's skill tree" now succeeds in all three trees, so
  **t635_29** (procedure-gate generalization) inherits a working wrapper layer and only
  needs to make the *resolution* formally agent-aware plus add per-gate agent/model
  selection. When authoring any future `aitask-gate-<name>` skill, follow the new
  `aitask-gate-template` Notes rule: plain gate skills do not auto-render, so run
  `apply-wrapper` for `agents` / `opencode-skill` / `opencode-command` in the same
  change, and whitelist every helper the skill shells out to across all 5 touchpoints.
