---
Task: t1569_6_backlog_roadmap_skill_and_trail_authoring.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_1_*.md, aitasks/t1569/t1569_2_*.md, aitasks/t1569/t1569_3_*.md, aitasks/t1569/t1569_4_*.md, aitasks/t1569/t1569_5_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
---

# t1569_6 — `aitask-backlog-roadmap` skill and trail authoring

The user-facing surface. Implements against t1569_5's design record and encoding
contract — read `aidocs/framework/background_work_roadmap.md` first.

## Step 1 (before implementation) — two decisions

### 1a. Member cap and selection rule

261 candidates (222 Ready follow-ups + 39 Ready `effort: low` genuine tasks)
against a schema requiring **`rationale` and `confidence` per entry** is not
authorable in one run. Worse, a digest over ~500 inputs goes STALE on *any*
status change anywhere in the corpus, so the freshness signal degenerates to
noise and refresh becomes constant.

Pick a top-N. Record the corpus size and the selection rule in
`narrative.method_note`. Note `exclusions[]` requires a `reason_code` per
excluded task (`unrelated | non_blocking | already_landed | superseded_scope |
deferred_by_user | other`), so a 200-item tail is **not** free — the method note
is the cheap answer, an enumerated tail is not.

### 1b. Artifact owner

`owner` is required and the substrate is task-owned, but this roadmap **outlives
t1569**. Pick a **standing holder task**, not t1569. Verify handle resolution
still works after the owner archives (`ait artifact get art:<id>`), because the
`artifacts:` frontmatter entry lives on the owner's task file.

## Step 2 — The skill (4 files, static)

Profile-agnostic skills keep a single `SKILL.md` and skip the `.j2` template
entirely (`aidocs/framework/skill_authoring_conventions.md:220-222`). Phase 1 is
purely advisory and read-only, so there is little genuine per-profile behaviour.

```
.claude/skills/aitask-backlog-roadmap/SKILL.md      # canonical body — write this
.agents/skills/aitask-backlog-roadmap/SKILL.md      # generated
.opencode/skills/aitask-backlog-roadmap/SKILL.md    # generated
.opencode/commands/aitask-backlog-roadmap.md        # generated
```

Template to copy: `.claude/skills/aitask-stats/`.

```bash
for tree in agents opencode-skill opencode-command; do
  ./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper "$tree" aitask-backlog-roadmap
done
./.aitask-scripts/aitask_skill_verify.sh    # cross-tree parity is the check a static skill hits
```

Do **not** hand-write the three wrappers — they are rendered from this
`SKILL.md`'s `description:` and its first `## Usage` paragraph
(`aitask_audit_wrappers.sh:253-378`).

If the skill invokes any new `.aitask-scripts/aitask_*.sh` helper, add its five
whitelist entries with `apply-helper-whitelist` — and read
`aidocs/framework/aitasks_extension_points.md:286-318` to confirm the touchpoint
list before editing. (`aitask_parallel_admission.sh` is already whitelisted by
t1569_4; only genuinely new helpers need this.)

## Step 3 — The skill body

Steps the skill performs:

1. Resolve scope. **Reuse `aitask-trail`'s ad-hoc mapping verbatim** —
   `--scope task <ids...> --owner <id>` — rather than inventing a scope shape.
2. `./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task <ids...> --with-inflight`
   (t1569_1). All repository state comes from the deterministic gatherer — no
   free-reading the board or scanning task files.
3. The batch derivation and origin resolution (t1569_2).
4. `./.aitask-scripts/aitask_parallel_admission.sh check --from origin
   --lock-freshness allow-cached` per candidate (t1569_3), via t1569_5's policy
   library.
5. Author the trail JSON per t1569_5's encoding contract.
6. `./.aitask-scripts/aitask_trail_depth.sh validate <file> --expect-depth <d>`
   → `VALID:<trail_id>` before writing anything.
7. `ait artifact create <owner> <file> --kind implementation_trail
   --handle art:<trail_id> --name "<title>"`; parse the **`HANDLE:`** line from
   stdout (`aitask_artifact.sh:289-290`). Refresh uses
   `ait artifact update <handle> <file>` (no `HANDLE:` line on update).

Refs are canonical `<project>#<id>` — **copy them into the trail JSON exactly as
emitted, never re-spell**; digest provenance depends on byte-identity.

## Step 4 — Run summary honesty requirements

These are correctness, not tone:

- State plainly that the lanes are an **estimate** — origin/topic evidence,
  in-flight state as of the run, **reserving nothing** — and that `/aitask-pick`
  runs the live preflight (t1569_4) before implementation. A CLEAR estimate must
  never read as an admission decision.
- **Never** say "safe to run in parallel". Say **"no known conflict at check
  time"**.
- Surface t1569_5's resolution-quality histogram (`exact` / `topic` / `unknown`)
  so the `followup_origins:` question stays visible and evidence-backed.
- Show `UNCHECKABLE` counts and their named causes, not just the safe lane.

## Step 5 — Docs

- `website/content/docs/skills/_index.md` — the skills table (~line 92).
- A new `website/content/docs/skills/aitask-backlog-roadmap.md`.
- A workflows note documenting t1569_4's preflight, **including the residual
  race**: the check is a snapshot and reserves nothing, so overlapping work can
  begin immediately after it passes.
- `docs/README.md` if it lists skills.

Follow `aidocs/framework/documentation_conventions.md`: current-state-only prose,
no version history in doc bodies, and genericize any passage naming specific
coding agents.

## Step 6 — Create two follow-ups

**t1343 adoption.** Swap the checker's *evidence backend* to the declared-claims
model (per-task claim store under `.aitask-gates/<id>/`, deterministic set
intersection emitting `PAIR:` / `PHASE:` / `UNCLAIMED:` / `CLEAN:`). t1343's
`depends: [1275]` is satisfied — t1275 landed 2026-08-25. t1569_4's preflight is
the consumer surface t1343 was missing, so this is a **backend swap behind an
unchanged verdict contract**, not a rewrite — **and it is what closes the
point-in-time race**, since a claim registry reserves the surface where this
checker only observes it. `depends: [1343, 1569_4]`.
**Add a bidirectional coordination note to t1343** naming this follow-up.

**`followup_origins:` enhancement.** A persisted direct-origin field populated at
every follow-up creation seam (the t1468_1 / t1468_2 shape: field foundation and
creation seams as separate children). **Gated on t1569_5's measurement** against
the design record's threshold. It is a **ranking-quality** improvement, not a
safety one — the preflight makes the safety decision. `depends: [1569_6]`. Carry
the measured numbers **and their sample bias** verbatim in its Problem section so
the justification is auditable rather than asserted.

## Verification

```bash
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/aitask_*.sh
bash tests/run_all_python_tests.sh --test-dir tests    # last line only
cd website && hugo build --gc --minify                 # docs build
```

End-to-end on the live repo:

1. Run the skill; confirm the artifact is created and `HANDLE:` parsed.
2. `./.aitask-scripts/aitask_trail_depth.sh validate <file> --expect-depth <d>`
   → `VALID:<trail_id>`.
3. `./.aitask-scripts/aitask_trail_gather.sh drift --trail art:<handle>` →
   `CURRENT` immediately after creation.
4. `ait artifact versions art:<handle>` lists v1 as current.
5. Re-run the skill; confirm `update` produces v2 and does not touch the owner's
   task file.
6. Open `ait board` By-Trail view and confirm the trail appears with its
   coordination entries glyphed.
