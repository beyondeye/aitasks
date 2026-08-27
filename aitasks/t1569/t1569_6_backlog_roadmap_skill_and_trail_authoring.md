---
priority: high
effort: high
depends: [t1569_5]
issue_type: feature
status: Ready
labels: [skills, artifacts, backlog, documentation]
gates: [risk_evaluated]
anchor: 1569
created_at: 2026-08-27 11:29
updated_at: 2026-08-27 11:29
---

The `aitask-backlog-roadmap` skill and its trail artifact. Slice 6 of 6 for
t1569 — read the parent task and
`aiplans/p1569_background_work_roadmap_trail_for_followup_backlog.md` first.

Depends on t1569_5, which ships the design record and the trail encoding contract
this task implements against.

## Context

The user-facing surface: a **static** (non-profile-aware) skill that runs the
gatherer (t1569_1), the batch derivation (t1569_2), the checker (t1569_3) and the
policy library (t1569_5), and emits a standard `implementation_trail` artifact so
the board's By-Trail view, `drift`, versioning and refresh all work unchanged.

Corpus: Ready follow-ups plus Ready `effort: low` genuine work — **222 + 39 = 261
tasks** as measured. Not the whole Ready backlog; that competes with
`/aitask-pick`.

## Scope

### The skill — 4 files, static

```
.claude/skills/aitask-backlog-roadmap/SKILL.md      # canonical body
.agents/skills/aitask-backlog-roadmap/SKILL.md      # generated wrapper
.opencode/skills/aitask-backlog-roadmap/SKILL.md    # generated wrapper
.opencode/commands/aitask-backlog-roadmap.md        # generated wrapper
```

No `.j2`, no goldens, no render test — phase 1 is purely advisory and read-only,
so there is little genuine per-profile behaviour to vary. Profile-agnostic skills
keep a single `SKILL.md` and skip the template entirely
(`aidocs/framework/skill_authoring_conventions.md:220-222`); `aitask-stats`,
`aitask-work-report` and `aitask-learn-skill` are the working templates.

Generate the three wrappers rather than hand-writing them:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> aitask-backlog-roadmap
# trees: agents | opencode-skill | opencode-command
./.aitask-scripts/aitask_skill_verify.sh
```

Cross-tree parity is the one check a static skill hits — a missing tree fails
verification. Any new `.aitask-scripts/aitask_*.sh` helper the SKILL.md invokes
needs its 5 whitelist entries via `apply-helper-whitelist` (verify the touchpoints
against `aidocs/framework/aitasks_extension_points.md:286-318` first).

### Trail authoring

Author the `implementation_trail` JSON per t1569_5's encoding contract, validate
with `./.aitask-scripts/aitask_trail_depth.sh validate <file> --expect-depth ...`,
then create the artifact:

```bash
ait artifact create <owner> trail.json --kind implementation_trail \
  --handle art:<trail_id> --name "<title>"
```

Parse the `HANDLE:` line from stdout (`aitask_artifact.sh:289-290`). Refresh uses
`ait artifact update <handle> <file>`.

### Two decisions to make in this task's plan step 1 — not during implementation

**1. Member cap / selection rule.** 261 candidates against a schema that requires
`rationale` **and** `confidence` per entry is not authorable in one run, and a
digest over ~500 inputs goes STALE on any status change anywhere — the freshness
signal would degenerate to noise and refresh would be constant. Pick a top-N and
record the corpus size and selection rule in `narrative.method_note`.
`exclusions[]` requires a `reason_code` per excluded task
(`unrelated|non_blocking|already_landed|superseded_scope|deferred_by_user|other`),
so a 200-item tail is **not** free.

**2. Artifact owner.** `owner` is required and the substrate is task-owned, but
this roadmap **outlives t1569**. Pick a standing holder task, not t1569, and
check handle resolution after the owner archives.

### Run summary — honesty requirements

- State plainly that the lanes are an **estimate** — origin/topic evidence,
  in-flight state as of the run, **reserving nothing** — and that `/aitask-pick`
  runs the live preflight (t1569_4) before implementation. A CLEAR estimate must
  never read as an admission decision.
- Never say "safe to run in parallel". Say **"no known conflict at check time"**.
- Surface t1569_5's resolution-quality histogram so the `followup_origins:`
  question stays visible and evidence-backed.

### Docs

- `website/content/docs/skills/_index.md` (the table) + a new skill page.
- A workflows note documenting t1569_4's preflight, **including the residual
  race**: the check is a snapshot and reserves nothing, so overlapping work can
  begin immediately after it passes.
- `docs/README.md` if it lists skills.

Follow `aidocs/framework/documentation_conventions.md` — current-state-only
prose, no version history in doc bodies.

## Follow-ups to create

- **t1343 adoption** — swap the checker's *evidence backend* to the
  declared-claims model (per-task claim store under `.aitask-gates/<id>/`,
  deterministic set intersection). t1343's `depends: [1275]` is now satisfied
  (t1275 landed 2026-08-25). t1569_4's preflight is the consumer surface t1343
  was missing, so this is a **backend swap behind an unchanged verdict
  contract**, not a rewrite — **and it is what closes the point-in-time race**,
  since a claim registry reserves the surface where this checker only observes
  it. `depends: [1343, 1569_4]`. **Add a bidirectional coordination note to
  t1343.**
- **`followup_origins:` enhancement** — a persisted direct-origin field populated
  at every follow-up creation seam (the t1468_1 / t1468_2 shape). **Gated on
  t1569_5's measurement** against the threshold in the design record. It is a
  **ranking-quality** improvement, not a safety one — the preflight makes the
  safety decision. `depends: [1569_6]`. Carry the measured numbers **and their
  sample bias** verbatim in its Problem section, so the justification is
  auditable rather than asserted.

## Reference files for patterns

- `.claude/skills/aitask-stats/` — the 4-file static-skill template.
- `.claude/skills/aitask-trail/SKILL.md.j2` — trail authoring rules (L610-666),
  artifact create/update call sites (L392-393, L579), and the ad-hoc scope
  mapping (`--scope task <ids...> --owner <id>`) — reuse it verbatim rather than
  inventing a scope shape.
- `.aitask-scripts/aitask_artifact.sh` — `cmd_create` L193-229, `cmd_update`
  L317-326, `cmd_get` L615-653, `cmd_versions` L655-670.
- `aidocs/framework/skill_authoring_conventions.md`,
  `aidocs/framework/aitasks_extension_points.md:286-318`.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`
- `shellcheck .aitask-scripts/aitask_*.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` (last line only)
- End-to-end on the live repo: run the skill, confirm the artifact is created and
  `./.aitask-scripts/aitask_trail_gather.sh drift --trail art:<handle>` reports
  `CURRENT`.
- Confirm the emitted trail validates: `aitask_trail_depth.sh validate` ->
  `VALID:<trail_id>`.
