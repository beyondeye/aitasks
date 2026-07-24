---
Task: t1210_3_aitask_trail_skill.md
Parent Task: aitasks/t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Sibling Tasks: aitasks/t1210/t1210_4_*.md … t1210_7_*.md (pending)
Archived Sibling Plans: aiplans/archived/p1210/p1210_1_trail_schema_library_and_validator.md, p1210_2_trail_gatherer_and_drift_helper.md
Worktree: (none — profile 'fast', current branch)
Branch: main (current branch)
Base branch: main
---

# Plan: t1210_3 — `/aitask-trail` skill (create + refresh + show)

## Context

**T3** of the Implementation Trails decomposition (RFC §14,
`aidocs/implementation_trail_design.md`; parent t1210). The user-facing
profile-aware `/aitask-trail` skill: create + refresh flows built on the T2
gatherer protocol (`aitask_trail_gather.sh` snapshot/drift) and the T1 schema
contract, with read-only analysis and **one confirmed artifact write** per
flow. Also owns the `trail` codeagent operation registration (seed + live
`.defaults`) and the helper whitelist rows T2 explicitly deferred to T3.

User decisions recorded at planning: **`--show <handle>` IS implemented**
(task AC wins over the RFC's board-side-only J7 inspection; read-only, no
confirmation) and the **`trail` operation defaults to `claudecode/opus4_8`**
(heavy class — analysis depth is the product).

## Key design decisions

1. **Skill shape: profile-aware stub + single `SKILL.md.j2`, aitask-qa as the
   model.** Four committed surfaces: `.claude/skills/aitask-trail/SKILL.md`
   (Claude stub, canonical stub-skill-pattern §3b body, resolver key `trail`),
   `.claude/skills/aitask-trail/SKILL.md.j2` (authoring template,
   `name: aitask-trail-{{ profile.name }}`), `.agents/skills/aitask-trail/SKILL.md`
   (Codex stub, `--agent codex`, Read path `aitask-trail-<profile>-codex-/`),
   `.opencode/commands/aitask-trail.md` (OpenCode wrapper, `@`-includes the two
   opencode prereq files). All three stubs are REQUIRED in this task —
   `aitask_skill_verify.sh` fails the stub-surface check otherwise — so no
   cross-agent port follow-ups are needed (stubs are agent-complete; the
   rendered flow is agent-neutral). **No `{% if agent %}` gates** (avoids the
   Test 1b agent-invariance cascade; per-agent tool mapping stays in the
   prereq files). v1 has no profile-conditional behavior — the `.j2` renders
   identically across profiles except the frontmatter name (the confirmed-write
   contract is NON-SKIPPABLE and must not be profile-bypassable). No rendered
   variants are committed (not a headless-prerender skill). Discovery is
   glob-driven everywhere — no registry/list edits.

2. **Pinned argument surface** (task AC + RFC §3): bare invocation,
   `<task_id>`, `--topics <r1>,<r2>`, `--refresh <handle>`, `--show <handle>`.
   Free-text arguments that are not one of these are auto-detected (a bare
   number/`N_M` → task id; `art:trail-*` or `trail-*` token → treated as a
   handle for show/refresh disambiguation via one question). **Latency rule:**
   no I/O before the first AskUserQuestion beyond what the opening question
   needs (bare invocation asks scope kind first; `<task_id>` reads only that
   task file to phrase the task-vs-topic question).

2b. **Ad-hoc scope: executable representation (gatherer has no `ad_hoc`
   mode — `trail_gather.py:1023` accepts only `task|topic|multi_topic`).**
   An ad-hoc selection (J1's "explicitly chosen scope" / J4) maps to the
   gatherer's **task scope**: `snapshot --scope task <selected ids...>`,
   which is exactly selected-member inputs with owner validation (`--owner`
   is accepted on every scope and validated against the universe;
   multiple ids → `OWNER:none` → the same explicit-owner question as
   multi-topic). The trail JSON then records `scope.kind: "ad_hoc"` (schema
   enum allows it) with a `selection_note` naming how the set was chosen;
   `scope.topics` = the observed topic csv from the `SCOPE:` line. This is
   sound because drift never branches on `scope.kind` — its scans read only
   `scope.topics` ∪ stored refs (`trail_gather.py:822-827`) — so refresh
   works identically. **Pinned gatherer semantics disclosed to the user at
   selection time:** a parent id pulls its active children into the member
   set (`cmd_snapshot` task-scope loop); users wanting an exact set pass
   child ids directly. The J2 "task-only" flow writes `scope.kind: "task"`;
   only a user-chosen ad-hoc selection writes `ad_hoc`. No T2 change needed
   (rejected alternative: adding an `ad_hoc` gatherer mode — it would
   duplicate task-scope semantics under a second name and reopen the pinned
   T2 protocol).

3. **Create flow (J1–J4), exactly RFC §3/§7:**
   - Scope resolution: bare → AskUserQuestion (task / topic / multi-topic /
     ad-hoc, free text for ids). `<task_id>` → question: task-only vs the
     task's canonical topic (J2). `--topics r1,r2` → multi_topic. Ad-hoc →
     decision 2b mapping (`--scope task <ids...>`, children disclosure,
     JSON `scope.kind: ad_hoc`).
   - Snapshot: `./.aitask-scripts/aitask_trail_gather.sh snapshot --scope
     <task|topic|multi_topic> [--owner <id>] <ids...>`. Parse
     SCOPE/OWNER/MEMBER/INPUT/DIGEST; any `ERROR:` line → surface and stop
     (staged errors are exit-0; nonzero exit = infra, diagnose). If
     `OWNER:none` (multi-topic/ad-hoc, J4) → **explicit owner
     AskUserQuestion** (options = member/topic-root candidates + free text),
     then re-run snapshot with `--owner <choice>` so the output validates the
     owner and is directly attachable.
   - Analysis per RFC §7 steps 3–5: classify every member
     (`hard_prerequisite|preferred_predecessor|core|coordination_only|optional`),
     form waves with required narrative (`purpose` per wave; `rationale` +
     `confidence` per entry; `why_now`/`expected_outcome`/`why_order_matters`
     where meaningful), record exclusions with reason codes, observations
     ONLY evidence-backed (`evidence_refs` minItems 1), `method_note` states
     what was NOT verified. **The trail must never be a bare ranked list.**
     Anti-fabrication (§7.5): no estimates, progress claims, or commitments.
   - **Scope expansion is propose-and-confirm, never silent** (§7 step 3): a
     discovered outside-scope blocker → AskUserQuestion (add as observation /
     expand scope / ignore); expansion re-runs snapshot with the wider scope.
   - Render the FULL proposed trail (waves, entries with classification +
     rationale, observations, exclusions, evidence) in the reply, then
     **⚠️ NON-SKIPPABLE confirm** AskUserQuestion (create / revise / abort).
   - Slug: propose `trail-<slug>` derived from the owner/topic name; user
     can override (free text). `trail_id` = handle minus `art:`; must match
     `^trail-[a-z0-9][a-z0-9_-]{2,63}$`.
   - Author `trail.json` with the **Write tool** to a temp path (no shell
     needed): `schema_version: "1.0.0"`, refs copied EXACTLY as the gatherer
     emitted them (canonical `<project>#<id>` — never re-spell),
     `generation.inputs` = the INPUT (kind, ref) pairs, `input_digest` = the
     DIGEST line, `generated_at` UTC ISO-8601, `generator.agent_string` from
     `$AITASK_AGENT_STRING` when set (codeagent launch) else the
     model-self-detection procedure (`.claude/skills/task-workflow/model-self-detection.md`),
     `generator.skill: "aitask-trail"`. Entry `snapshot`s populate
     status + depends + gates_pending from the INPUT task lines (T2:
     incomplete snapshots degrade residual attribution). `freshness` =
     `{state: current, checked_at: <now>}`.
   - **Pre-write validation reusing the whitelisted wrapper** (no new python
     whitelist rows): run `./.aitask-scripts/aitask_trail_gather.sh drift
     --trail <tmpfile>`. Expected `CURRENT`; `ERROR:invalid_trail` → fix the
     JSON (details on stderr) and re-validate; `STALE` → the repo moved
     mid-analysis → inform user, re-run snapshot and re-author.
   - Single write: `./.aitask-scripts/aitask_artifact.sh create <owner_id>
     <tmpfile> --kind implementation_trail --handle art:trail-<slug>
     [--name "<title>"]`. Parse the `HANDLE:` stdout line. Nonzero exit with
     "handle … already exists" → **re-prompt slug** (collision rule) and
     retry; other errors → surface and stop. (Owner id for the CLI is the
     local task id form `N`/`N_M` from the owner ref.)

4. **Refresh flow (J5/J6), RFC §8.2/§8.3:**
   - Load: `./.aitask-scripts/aitask_artifact.sh get <handle> --out <tmp>`;
     record the **base current version**: `aitask_artifact.sh versions
     <handle>`, the `* sha256:` line.
   - Drift: `./.aitask-scripts/aitask_trail_gather.sh drift --trail
     art:<handle-id>` (wrapper resolves the handle). `ERROR:*` → surface,
     stop. `CURRENT` with no reasons → tell the user the trail is current;
     AskUserQuestion: refresh anyway (agent-judged reasons, e.g.
     `premise_invalidated`) / exit without writing.
   - Targeted re-analysis (§8.3): re-analyze ONLY drifted waves/entries —
     completed entries move to landed presentation via refreshed snapshots,
     new related tasks are evaluated for membership (propose-and-confirm if
     outside scope), invalidated premises re-open only the affected wave.
     The agent MAY author `premise_invalidated` drift reasons (T2's helper
     never emits it). Re-run `snapshot` (same scope/owner from the stored
     trail) for the fresh digest + records; unchanged waves/entries carry
     over with updated snapshots only.
   - Present a **diff-style summary** (waves/entries added, retired, moved;
     reasons consumed), then **⚠️ NON-SKIPPABLE confirm**.
   - Author the new version JSON (same rules as create; `trail_id`, handle
     unchanged), validate via `drift --trail <tmpfile>` as in create.
   - **Stale-base re-read guard (§8.3, exact):** immediately before writing,
     re-run `aitask_artifact.sh versions <handle>` and compare the `*` line
     to the recorded base. If it moved → warn via AskUserQuestion (re-load
     and re-analyze / overwrite anyway / abort). Then the single write:
     `./.aitask-scripts/aitask_artifact.sh update <handle> <tmpfile>`
     ("already current — nothing to do" is a clean no-op).

5. **Show flow (`--show <handle>`, read-only, zero writes, no confirm):**
   `get <handle> --out <tmp>` → render human-readable (title, owner, scope,
   freshness, waves → entries with classification/rationale/confidence,
   observations, exclusions) → run `drift --trail art:<handle-id>` and report
   the verdict + named reasons; on STALE suggest `--refresh <handle>`.

6. **Hard invariants restated in the skill body:** no task metadata mutations
   anywhere (no `depends`/`priority`/`boardidx`/`anchor` writes — RFC §2/§4.5);
   at most ONE artifact write per flow, always after explicit confirmation;
   no `anchor` key anywhere in the JSON; the skill never touches
   manifests/blobs directly (`aitask_artifact.sh` is the only write path).

7. **Codeagent `trail` operation registration** (t1162_2 pattern):
   - `.aitask-scripts/aitask_codeagent.sh`: add `trail` to
     `SUPPORTED_OPERATIONS`; add the whitespace fail-closed guard (extend the
     work-report guard to `work-report|trail` — trail args are ids/handles/
     csv, whitespace would split undetectably in slash-command text); add
     per-agent arms: claudecode `CMD+=("/aitask-trail ${args[*]}")`, codex
     inner composer `trail) prompt=$(build_skill_prompt "\$aitask-trail"
     "${args[@]}") ;;` (CRITICAL — the missing-inner-arm defect from p1162_2),
     opencode `CMD+=("--prompt" "/aitask-trail ${args[*]}")`; add `trail` to
     the `show_help` Operations line.
   - `.defaults` entries `"trail": "claudecode/opus4_8"` in **both**
     `seed/codeagent_config.json` and live
     `aitasks/metadata/codeagent_config.json` (live commits via `./ait git`).
   - `verified["trail"]` mirrors `verified["explain"]` (where `explain`
     exists) in all 6 models files: `aitasks/metadata/models_{claudecode,codex,opencode}.json`
     (via `./ait git`) + `seed/models_{claudecode,codex,opencode}.json`.
   - `.aitask-scripts/lib/agent_command_screen.py`: add `"trail"` to
     `_FRESH_WINDOW_OPERATIONS` (T4's board launch consumes it; harmless now).

8. **Whitelists — 10 rows (the T2-deferred deliverable + artifact calls).**
   The skill body invokes helpers by full path (codex rules have no `./ait`
   dispatcher shapes; the audit matcher is helper-path based), so whitelist
   `aitask_trail_gather.sh` AND `aitask_artifact.sh` on all five surfaces,
   exact shapes:
   - `.claude/settings.local.json` + `seed/claude_settings.local.json`:
     `"Bash(./.aitask-scripts/aitask_trail_gather.sh:*)"`,
     `"Bash(./.aitask-scripts/aitask_artifact.sh:*)"` in `permissions.allow`
     (alphabetical placement).
   - `seed/opencode_config.seed.json`:
     `"./.aitask-scripts/aitask_trail_gather.sh *": "allow"`, same for
     `aitask_artifact.sh`.
   - `.codex/rules/default.rules` + `seed/codex_rules.default.rules`:
     `prefix_rule(pattern = ["./.aitask-scripts/aitask_trail_gather.sh"],
     decision = "allow", justification = "Aitasks helper script")`, same for
     `aitask_artifact.sh`.

## Files

- **New:** `.claude/skills/aitask-trail/SKILL.md` (stub),
  `.claude/skills/aitask-trail/SKILL.md.j2` (flow),
  `.agents/skills/aitask-trail/SKILL.md`, `.opencode/commands/aitask-trail.md`
- **New:** `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`
- **New:** `tests/test_skill_render_aitask_trail.sh` (mirrors
  `test_skill_render_aitask_qa.sh`: golden eq + agent invariance),
  `tests/test_trail_skill_contract.sh` (mirrors
  `test_work_report_skill_contract.sh`: load-bearing prose markers asserted
  in ALL THREE committed goldens — see Verification),
  `tests/test_codeagent_trail.sh` (mirrors `test_codeagent_work_report.sh`:
  per-agent dry-run construction spies, codex no-plan/no-sandbox pin,
  seeded-config resolution = `claudecode/opus4_8`, no-config heavy fallback,
  whitespace fail-closed guard, verified-score parity vs `explain` across the
  6 real models files)
- **Modified:** `.aitask-scripts/aitask_codeagent.sh`,
  `.aitask-scripts/lib/agent_command_screen.py`,
  `seed/codeagent_config.json`, `seed/models_{claudecode,codex,opencode}.json`,
  `.claude/settings.local.json`, `seed/claude_settings.local.json`,
  `seed/opencode_config.seed.json`, `.codex/rules/default.rules`,
  `seed/codex_rules.default.rules`
- **Modified (task-data, via `./ait git`):**
  `aitasks/metadata/codeagent_config.json`,
  `aitasks/metadata/models_{claudecode,codex,opencode}.json`

## Implementation steps

1. **Author the skill**: `SKILL.md.j2` first (flow per decisions 2–6, with
   the NON-SKIPPABLE banners on both confirm prompts and the invariants
   box), then the three stubs (copy aitask-qa's stubs, swap names/resolver
   key `trail`).
2. **Render + goldens**: `aitask_skill_render.sh aitask-trail --profile
   <p> --agent claude` per profile; generate the three goldens with
   `skill_template.py` (the documented loop); add
   `tests/test_skill_render_aitask_trail.sh`.
3. **Codeagent registration** (decision 7) + `tests/test_codeagent_trail.sh`.
4. **Whitelist rows** (decision 8).
5. **Verify** (below), then commit: code commit `feature: Add aitask-trail
   skill (t1210_3)` (skills, stubs, goldens, tests, scripts, seed files,
   whitelists — explicit pathspec, never `aitasks/`/`aiplans/`); task-data
   commit via `./ait git` for live codeagent_config + models files.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` — clean (render, closure,
  stub-surface markers for all three agents).
- `bash tests/test_skill_render_aitask_trail.sh`,
  `bash tests/test_trail_skill_contract.sh`,
  `bash tests/test_codeagent_trail.sh`,
  `bash tests/test_codeagent_work_report.sh` (unchanged, still green) — all
  PASS.
- **Rendered-skill contract assertions** (`test_trail_skill_contract.sh`) —
  the e2e smoke proves T1/T2/artifact plumbing, NOT the skill's behavior, so
  the skill's required instructions are pinned as prose-contract markers,
  asserted per-golden (default, fast, remote) so no profile render can drop
  them: (a) both `⚠️ NON-SKIPPABLE` confirm banners (create + refresh);
  (b) the stale-base guard sequence (re-run `versions` and compare the `*`
  line immediately before `update`); (c) `--show` is read-only (zero writes,
  no confirmation, drift verdict displayed); (d) mandatory pre-write
  `drift --trail <tmpfile>` validation with the CURRENT/invalid/STALE
  branches; (e) the no-task-metadata-mutations invariant sentence;
  (f) `HANDLE:` parse + collision → re-prompt slug; (g) `OWNER:none` →
  explicit owner question before any create; (h) the ad-hoc mapping
  (`--scope task` + `scope.kind: "ad_hoc"` + children disclosure);
  (i) single-confirmed-write-per-flow sentence. Each marker greps a
  distinctive literal from the golden, so dropping the instruction turns
  the suite red. Invocation-level live execution of the rendered skill is
  not automatable headlessly (the `claude -p` caveat in shell conventions;
  billing surcharge) — the in-task e2e smoke plus t1210_7 manual
  verification own that layer, and the smoke is explicitly labeled a
  plumbing check.
- `shellcheck .aitask-scripts/aitask_codeagent.sh` clean.
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist
  aitask_trail_gather.sh` and `... aitask_artifact.sh` → zero `MISSING:`.
- `./ait codeagent resolve trail` → `AGENT_STRING:claudecode/opus4_8`;
  `./ait codeagent --dry-run invoke trail 1210` → `DRY_RUN:` containing
  `/aitask-trail 1210`.
- **E2E plumbing smoke on a throwaway task** (in-task, then cleaned up): author a
  minimal valid trail for a scratch task via the real flow pieces — snapshot,
  JSON, `drift --trail <tmp>` = CURRENT, `aitask_artifact.sh create` →
  `HANDLE:`; `ait artifact ls <task>` shows the handle; mutate a member
  status → `drift` = STALE + reason; `update` produces v2 (`versions` shows
  2, `*` on the new one); then `aitask_artifact.sh rm` + revert the status.
- Step 9 (post-implementation): `./ait gates run 1210_3` (`risk_evaluated`
  via orchestrator), archive via `aitask_archive.sh 1210_3`.

## Out of scope (owned by siblings)

Board By-Trail view and refresh launch key (T4, t1210_4 — consumes
`_FRESH_WINDOW_OPERATIONS` + the wrapper's `drift --trail art:` first-token
parse); move-to-column commands (T5, t1210_5); user-facing docs incl. the RFC
§8.2 `premise_invalidated` wording sync (T6, t1210_6); manual verification
(t1210_7). No `ait trail` dispatcher case (helpers stay full-path; the skill
is reachable via `/aitask-trail` and `ait skillrun trail`).

## Risk

### Code-health risk: low
- `aitask_codeagent.sh` is a load-bearing dispatcher touched in four places; bounded by mirroring the work-report arms verbatim and the construction-spy test asserting all three agents' built commands · severity: low · → mitigation: TBD
- Ten new whitelist rows across five surfaces could drift from the audit matcher's expected shapes; bounded by running `audit-helper-whitelist` for both helpers as a verification gate · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- The skill flow is prose executed by an agent, not code: an agent could author schema-invalid or fabricated trail JSON; bounded by the mandatory pre-write `drift --trail <tmp>` validation (schema + digest currency through the real validator), the NON-SKIPPABLE confirm gates, and the per-golden prose-contract markers in `test_trail_skill_contract.sh`; live flow-quality remains provable only by the in-task plumbing smoke and t1210_7 manual verification · severity: medium · → mitigation: TBD
- Refresh correctness (targeted re-analysis + stale-base guard) depends on the agent honoring the §8.3 procedure; bounded by pinning exact CLI sequences and the versions-compare guard in the skill text · severity: low · → mitigation: TBD
