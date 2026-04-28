---
Task: t698_make_upstream_defect_reporting_robust.md
Base branch: main
plan_verified: []
---

# Plan — t698: Make upstream-defect reporting robust

## Context

In t687 the agent writing the plan file's `## Final Implementation Notes`
section recorded a related defect (`trailing-slash .gitignore entries don't
match aitasks/ / aiplans/ symlinks`) under a side bullet
`- **Trailing-slash follow-up:**` and wrote `None` to the canonical
`- **Upstream defects identified:**` bullet. Step 8b's
`upstream-followup.md` parses only the canonical bullet, so the defect was
invisible to the parser and the user was never offered a follow-up task.

Two failure modes are intertwined:

1. **Mis-classification** — the canonical bullet's "*seeded* the symptom this
   task fixed" framing is too narrow. The agent reads it as "must have caused
   the current bug" and writes `None` for related-but-not-causal defects (the
   t687 trailing-slash issue did not seed the gitignore-commit symptom; it
   was discovered alongside it during the same investigation).
2. **Mis-location** — once the agent has decided "this defect doesn't fit the
   canonical bullet", it writes a side bullet outside any bullet the parser
   reads.

Both modes are silent. The user gets no signal that a defect was identified
but skipped.

## Decision

**Option C (Hybrid)** with tightened contract language. Two coordinated
changes:

1. **Tighten the contract** in `SKILL.md` Step 8 plan-consolidation language:
   broaden "seeded the symptom" to "any pre-existing defect identified during
   diagnosis, regardless of causal relationship to the current symptom"; add
   an explicit "all related defects go under this single bullet — no
   separate side bullets" instruction; add a worked counter-example
   referencing the t687 failure mode. This addresses **mis-classification**
   directly and gives the agent a clear template to follow.
2. **Add a sanity-check re-read** in `upstream-followup.md`: when the
   canonical bullet is missing/empty/None, re-read the plan body end-to-end
   and ask the agent whether a related defect was documented elsewhere (a
   side bullet, free prose, "Out of scope" section, etc.). If found,
   surface the defect to the user via the existing offer flow. This catches
   **mis-location** even when the contract is followed imperfectly.

**No write-back.** The re-read is a runtime sanity check that surfaces an
offer; it does not modify the plan file mid-Step-8b. The defect remains in
its original location in the plan body, and the consolidation instructions
are the lever that gets future plans into canonical shape.

**No `aitask_archive.sh` changes.** Step 8b runs before archive; an
archive-time validator would be redundant with the hybrid re-read.

**No mirror-agent porting.** `.opencode/`, `.gemini/`, and `.agents/`
skill trees do not currently contain a `task-workflow` skill (verified —
none of those trees have `upstream-followup.md` or any "Upstream defects
identified" string). When task-workflow lands in those trees, the porter
will pick up the canonical Claude Code version, which by then includes
this fix. No new follow-up task needed today.

## Files to change

1. `.claude/skills/task-workflow/SKILL.md` — Step 8 "Final Implementation
   Notes" template, the `Upstream defects identified` bullet description
   (currently line 334).
2. `.claude/skills/task-workflow/upstream-followup.md` — Procedure step 1
   ("Resolve the plan file and read the subsection") gains a hybrid
   re-read fallback when the canonical bullet is missing/empty/None.

## Implementation

### Change 1 — `.claude/skills/task-workflow/SKILL.md` (line 334)

Replace the single-line `Upstream defects identified` bullet with a
broadened, more prescriptive version. The new wording:

- Drops the narrow "*seeded* the symptom this task fixed" framing in favor
  of "any pre-existing defect surfaced during diagnosis, whether or not it
  caused the current symptom".
- Adds an explicit instruction: "List every related defect under this
  single bullet. Do not create a separate side bullet (`- **Trailing-slash
  follow-up:**`, `- **Out of scope:**`, etc.) for related defects — Step 8b
  reads only this canonical bullet by name."
- Adds a worked counter-example showing the t687 failure mode (canonical
  says `None`, side bullet carries the actual defect → don't do this).
- Keeps the `path/to/file.ext:LINE — short summary` format example and
  the `None` (verbatim) escape hatch.
- Keeps the existing exclusions for style/lint/test gaps/unrelated TODOs.

Concrete replacement:

````markdown
- **Upstream defects identified:** Did diagnosis surface a separate,
  pre-existing bug in a different script/helper/module — whether or not it
  *caused* the current symptom? Anything you noticed about another piece of
  code that is broken or wrong belongs here. List each defect as a bullet
  of the form `path/to/file.ext:LINE — short summary` (e.g.
  `aitask_brainstorm_delete.sh:109-111 — worktree-prune ordering bug leaves
  stale crew-brainstorm-<N> branch`). Write `None` (verbatim) only if no
  related defect was identified — this subsection is read by Step 8b. Do
  not list style/lint cleanups, refactor opportunities, test gaps (those
  go through `/aitask-qa`), or unrelated TODOs.

  **All related defects go here, in the canonical bullet.** Do not record
  related defects under a separate side bullet (e.g.
  `- **Trailing-slash follow-up:**`, `- **Possibly worth a separate
  issue:**`, an "Out of scope" section, or free prose). Step 8b parses
  this single bullet by name; anything written elsewhere is invisible to
  the follow-up offer. If a defect feels out of scope for the current
  task, that is exactly what this bullet is for.

  *Anti-example (do not do this):* canonical bullet writes `None` and a
  side bullet `- **Trailing-slash follow-up:**` carries the actual
  defect. The parser sees `None`, the user never gets the follow-up
  offer, and the defect is silently buried in the archived plan.
````

### Change 2 — `.claude/skills/task-workflow/upstream-followup.md`

Replace step 1 ("Resolve the plan file and read the … subsection") to add
the hybrid sanity-check fallback. Step 2 (offer) and step 3 (seed
follow-up) stay unchanged — only the input to step 2 changes.

Concrete replacement (whole section 1, after the existing `### 1. …`
header):

````markdown
### 1. Resolve the plan file and read the "Upstream defects identified" subsection

Resolve the plan file:

```bash
./.aitask-scripts/aitask_query_files.sh plan-file <task_id>
```

Parse the output: `PLAN_FILE:<path>` means found, `NOT_FOUND` means the
plan file does not exist. If `NOT_FOUND`, return to the caller (proceed to
Step 8c) — there is nothing to read.

Read `<path>` and locate the bullet `- **Upstream defects identified:**`
inside the `## Final Implementation Notes` section. The subsection is the
plan-file source of truth: Step 8 plan consolidation writes either `None`
(verbatim) or a list of defect bullets of the form
`path/to/file.ext:LINE — short summary`.

**Fast path — canonical bullet has defect entries:** parse the bullets
into a list. Each bullet's location prefix and summary become the input
for the offer in step 2. Skip the sanity check below.

**Sanity-check path — canonical bullet is missing, empty, or contains
exactly `None`** (case insensitive, whitespace tolerant): the bullet may
be misclassified (a related defect was dismissed because it didn't seed
the symptom) or mis-located (a related defect was documented in a side
bullet, free prose, or an "Out of scope" section instead of the canonical
bullet — see the t687 failure mode in `SKILL.md` Step 8). Re-read the
plan file end-to-end and answer this question explicitly:

  > "Did diagnosis surface any pre-existing defect in another script,
  > helper, or module — whether or not it caused the current symptom —
  > that should become its own follow-up task? Look in every section of
  > the plan body, including 'Out of scope', 'Issues encountered',
  > 'Deviations from plan', side bullets, and free prose. Ignore
  > style/lint cleanups, refactor opportunities, test gaps, and unrelated
  > TODOs (the same exclusions the canonical bullet uses)."

If the answer is **no**: return to the caller (proceed to Step 8c).

If the answer is **yes**: synthesize one bullet per defect in the
canonical format `path/to/file.ext:LINE — short summary`, falling back
to `path/to/file.ext — short summary` (no line number) if the plan body
doesn't pin one down. Use these synthesized bullets as the input for the
offer in step 2. **Do not modify the plan file** — the re-read is a
runtime sanity check, not a write-back. The next time Step 8 plan
consolidation runs (in a future task), the tightened contract language
in `SKILL.md` will steer the agent to write the bullet canonically from
the start.
````

The remaining `### 2. User offer` and `### 3. Seed the follow-up task`
sections stay as-is. The "Canonical illustration (t660)" footer also
stays. Optionally append a second canonical illustration for t687 right
after the t660 one — keep it brief, since the SKILL.md anti-example
already documents the failure mode in detail.

Suggested addition after t660:

````markdown
## Canonical illustration (t687)

Setup wrote `None` to the canonical bullet and recorded a related
trailing-slash defect under a side bullet
`- **Trailing-slash follow-up:**`. The fast path saw `None` and would
have short-circuited. The sanity-check re-read inspects the plan body,
finds the side bullet's defect, and surfaces it as a normal follow-up
offer. The plan file is left untouched — only the runtime offer is
affected.
````

## Out of scope

- **Archive-time validator** (one of the optional sub-fixes in Option A's
  description). Step 8b already runs before archive; the hybrid re-read
  catches the same case earlier and more meaningfully (offers a
  follow-up rather than just warning).
- **Mirror to `.opencode/`, `.gemini/`, `.agents/`.** Confirmed those
  trees do not currently contain `task-workflow` or
  `upstream-followup.md`. When that skill is ported, the porter will
  pick up this fix automatically.
- **Plan-file write-back of the synthesized bullets.** User explicitly
  declined this when planning. The contract tightening covers the
  go-forward case.

## Verification

1. **Reproduce the t687 failure mode against the new procedure (read-only
   simulation):**

   - Construct a synthetic plan file fragment in memory with the exact
     t687 shape: `## Final Implementation Notes` containing
     `- **Upstream defects identified:** None.` plus a side bullet
     `- **Trailing-slash follow-up:** aitasks/ and aiplans/ trailing-slash
     entries don't match the symlinks…`.
   - Walk through `upstream-followup.md` step 1 by hand: confirm the
     fast path matches `None` → falls into sanity-check path → re-read
     instruction surfaces the side-bullet defect → step 2 offer fires.
   - This is a manual desk-check — no executable test asset needs to be
     committed because the procedure is markdown instructions, not code.

2. **Inspect the rendered SKILL.md change** to confirm:
   - The bullet text reads cleanly (no orphan list markers, no broken
     emphasis).
   - The anti-example sub-bullet is visually distinct enough that an
     agent reading the template will not glide past it.

3. **Inspect the rendered upstream-followup.md change** to confirm:
   - "Fast path" and "Sanity-check path" are clearly delimited so an
     agent reading the procedure does not collapse them into one
     unconditional re-read.
   - The "Do not modify the plan file" instruction is visible in the
     sanity-check path (write-back was explicitly declined).

4. **Cross-reference grep** to confirm no other file in the repo still
   carries the narrow "*seeded* the symptom" language that this change
   broadens:
   ```bash
   grep -rn "seeded the symptom" .claude/ .opencode/ .gemini/ .agents/ aireviewguides/ website/ 2>&1 | grep -v Binary
   ```
   Expect: only the updated SKILL.md line (or zero hits if the broader
   wording fully replaces it) and possibly historical hits in archived
   plans (those are immutable references — leave them).

5. **Sanity-check the canonical bullet is still parseable in the fast
   path.** Pick one recently archived plan that filled the canonical
   bullet with real defect entries (not `None`) and walk the procedure
   by hand: confirm the fast path still triggers, the sanity-check is
   skipped, and the offer wording matches the bullets verbatim.

## Step 9 (Post-Implementation)

- Code commit (regular `git`): `refactor: Make upstream-defect reporting robust (t698)`
  - Includes both `.claude/skills/task-workflow/SKILL.md` and
    `.claude/skills/task-workflow/upstream-followup.md`.
- Plan commit (`./ait git`): `ait: Update plan for t698`
- Archive via `./.aitask-scripts/aitask_archive.sh 698`
- No linked issue (`issue:` not set in t698 frontmatter) — the archive
  flow's issue-update step is a no-op here.
- Step 8b on this very task: the plan documents no upstream defect (the
  t687 mis-categorization is *the topic of this task*, not an upstream
  defect of it). Canonical bullet will read `None`. The new sanity-check
  path will re-read the plan body and confirm no other related defect
  is mentioned, returning the no-op cleanly.

## Final Implementation Notes

- **Actual work done:**
  - `.claude/skills/task-workflow/SKILL.md` (line 334): broadened the
    `Upstream defects identified` bullet — dropped the narrow "*seeded*
    the symptom" framing in favor of "whether or not it caused the
    current symptom"; added an explicit "all related defects go in this
    canonical bullet, not in side bullets / 'Out of scope' sections /
    free prose" instruction; added a worked anti-example referencing the
    t687 trailing-slash side-bullet failure mode.
  - `.claude/skills/task-workflow/upstream-followup.md`: split step 1
    into a "Fast path" (canonical bullet has entries — unchanged
    behavior) and a "Sanity-check path" (canonical bullet is missing /
    empty / `None` → re-read the plan body end-to-end, surface any
    related defect found anywhere in the body to step 2's offer).
    Re-read explicitly does not modify the plan file (write-back was
    declined during planning). Also broadened the file's intro line 3
    away from the same "*seeded* by" framing for consistency. Appended
    a "Canonical illustration (t687) — sanity-check path" footer
    documenting the t687 failure mode.
- **Deviations from plan:** None of substance. Added one extra small
  edit to upstream-followup.md line 3 (broadening the intro language)
  for consistency with the SKILL.md broadening — caught during the
  rendered-file inspection verification step. The plan's verification
  step 4 (cross-reference grep for "seeded the symptom") would
  otherwise have flagged it.
- **Issues encountered:** None. Both edits were single Edit-tool
  replacements against the existing text. The cross-reference grep
  verification (`grep -rn "seeded the symptom" .claude/ .opencode/
  .gemini/ .agents/ aireviewguides/ website/`) returned zero hits,
  confirming the broader wording fully replaces the narrow framing.
- **Key decisions:**
  - Kept the agent's re-read in the sanity-check path **non-mutating**
    (no write-back into the canonical bullet). User explicitly chose
    "No write-back" during planning. Rationale: the contract tightening
    is the lever that gets future plans into canonical shape; the
    sanity-check is a safety net for already-written plans.
  - Did not touch `aitask_archive.sh` — Option A's "validate
    canonical bullet at archive time" sub-fix is redundant with the
    hybrid re-read at Step 8b (which runs before archive and offers
    a follow-up rather than just warning).
  - Did not mirror to `.opencode/`, `.gemini/`, or `.agents/` skill
    trees. Confirmed those trees do not currently contain
    `task-workflow` or `upstream-followup.md` (their `skills/`
    directories list aitask-* skills and a couple of prereq/tool-
    mapping markdown files, but no `task-workflow/`). When that skill
    is ported, the porter will pick up this fix automatically — no
    cross-port follow-up task needed today.
- **Upstream defects identified:** None. The t687 mis-categorization is
  the topic of this task, not an upstream defect of it. No other
  unrelated defect surfaced during diagnosis or implementation.
