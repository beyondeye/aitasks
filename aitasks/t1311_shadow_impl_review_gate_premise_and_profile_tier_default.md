---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [shadow, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-07-29 07:49
updated_at: 2026-07-29 10:14
---

Two defects in the shadow skill's implementation-review sub-procedure
(`.claude/skills/aitask-shadow/impl-challenge.md`): a mis-premised "too early to
review" gate that fires in the *normal* case, and a tier prompt with no way to
set a per-profile default.

## Problem 1 — The "too early to review" gate has its premise backwards

`impl-challenge.md:78-90` runs a required, every-tier gate: if the resolved plan
has no `## Final Implementation Notes` section, it warns the user that "it is
probably too early to review the implementation" and makes them choose
**abort** / **proceed anyway** before any review work happens.

That treats the *normal* pre-commit state as an anomaly. In
`.claude/skills/task-workflow/SKILL.md`, the Final Implementation Notes are
written only inside the **"Commit changes"** branch of Step 8 (the
`## Final Implementation Notes` template at ~line 471), which runs **after** the
Step 8 review `AskUserQuestion` (~line 458). So at the single most common moment
a user reaches for a shadow implementation review — the followed agent parked at
"Implementation complete. Please review and test the changes." — the notes are
absent **by construction**.

The procedure already half-knows this: input 2's working-tree fallback says
"this is often the live case" and explains that the changes sit in the working
tree/index because notes are written after the Step 8 prompt. The gate
contradicts that paragraph.

Effect: an extra confirmation round-trip on essentially every real
implementation review, phrased as a warning that the user is doing something
premature when they are doing exactly the intended thing.

**Desired behavior:** absent notes must NOT be treated as a "probably too early"
anomaly requiring confirmation. Reviewing before the notes exist is the expected
flow. The genuinely useful part of the current gate is the *informational* half
— telling the user which diff source is being reviewed (working-tree/index vs
committed) and that no deviations have been narrated yet — which should be kept
as a stated fact, not a blocking prompt.

Design points to settle at planning time:
- Does anything still warrant an abort/proceed prompt (e.g. no plan at all, or
  no diff at all in any of committed/staged/unstaged)? Distinguish "no notes"
  (normal) from "nothing to review" (genuinely blocking).
- The archived-plan fallback in input 1 stays as-is; it is orthogonal and
  correct.
- Keep the "tell the user which source you reviewed" obligation — it becomes
  the surviving carrier of the caveat.

## Problem 2 — No profile default for the implementation-review tier

Tier selection (`impl-challenge.md:92-138`) auto-detects a tier from the user's
wording, and for a generic "review the implementation" it **always** asks a
4-option `AskUserQuestion`. There is no way to say "in my `fast` profile, always
use `advanced`" and skip the prompt.

**Desired behavior:** an execution-profile key that supplies a default review
tier (e.g. `advanced` for the `fast` profile). When set, the prompt is skipped
and the tier is announced; when unset, the current interactive prompt is kept.
An explicit tier named in the user's ask must still win over the profile
default.

### Exploration findings (design constraints — verify before relying on them)

- **Exact precedent: `qa_tier`.** Same "set → skip the prompt, unset → ask"
  shape. Schema entry at `.aitask-scripts/lib/profile_editor.py:84`
  (`"qa_tier": ("enum", ["q", "s", "e"])`), help text at :357, field group at
  :387; consumed in `.claude/skills/aitask-qa/SKILL.md.j2:20-36`. Note a
  pre-existing inconsistency worth deciding against, not copying: profile_editor
  uses single-letter values `q/s/e` while `.claude/skills/task-workflow/profiles.md:44`
  documents `"quick"/"standard"/"exhaustive"`. Pick one form for the new key
  (full tier words `quick|default|advanced|deep` match `impl-challenge.md`'s own
  vocabulary) and state the choice.

- **The shadow skill is NOT profile-aware.** `.claude/skills/aitask-shadow/` has
  no `SKILL.md.j2` and no rendered `-<profile>-` variants; `.agents/skills/aitask-shadow/`
  and `.opencode/skills/aitask-shadow/` contain a wrapper `SKILL.md` only (the
  sub-procedures are Claude-only by design). So the Jinja render route that
  `aitask-qa` uses is not available without first converting the whole shadow
  skill to the stub + `.md.j2` pattern — a large change for a minimonitor-spawned
  wrapper with nine sub-procedure files.

- **Two candidate routes; weigh both at planning time with trade-offs and
  rejected alternatives:**
  - **(a) Runtime profile-key read** inside `impl-challenge.md` at tier-selection
    time. Cheap and local, keeps shadow non-profile-aware. Needs a helper:
    `./.aitask-scripts/aitask_skill_resolve_profile.sh` returns only the profile
    **name**, and nothing in the tree reads an arbitrary key out of a profile
    YAML. Either extend that script or add a small sibling reader
    (`<key>` → value, empty when unset), with a unit test.
  - **(b) Make `aitask-shadow` profile-aware** (stub + `.md.j2` + rendered
    variants + goldens). Consistent with every other profile-aware skill, but
    heavy, and it must not break the minimonitor spawn path, which passes
    `<followed_pane_id> [<source_task_id>]` positionally.

- **Which profile applies to the shadow** is itself a design question: the shadow
  is a companion to a followed agent, not a task-workflow participant. Options:
  resolve `default_profiles.shadow` via the existing per-skill resolver, or
  inherit the followed agent's profile. Decide and document.

- **Blast radius of a new profile key** (derive, don't hand-duplicate — see the
  drift note above):
  - `.aitask-scripts/lib/profile_editor.py` — enum entry, help text, field group
  - `seed/profiles/*.yaml` and `aitasks/metadata/profiles/*.yaml` (`fast.yaml`
    gets `advanced` per the reporter's example; leave `default.yaml` unset so it
    keeps prompting)
  - `.claude/skills/task-workflow/profiles.md` key table **plus its rendered
    variants** (`task-workflow-default-`, `-fast-`, `-remote-`, and the
    `.agents/` / `.opencode/` copies)
  - `website/content/docs/concepts/execution-profiles.md`,
    `website/content/docs/tuis/settings/reference.md`,
    `website/content/docs/workflows/shadow-agent.md` (line ~69 documents the
    current "too early" warning and must be rewritten for Problem 1 as well)

## Acceptance criteria

1. A shadow implementation review started while the followed agent sits at the
   Step 8 review prompt (no Final Implementation Notes, changes in the working
   tree) proceeds **without** an abort/proceed confirmation, and states which
   diff source it reviewed and that deviations have not been narrated yet.
2. A genuinely un-reviewable state (no plan at all, or no diff in committed,
   staged, or unstaged) is still surfaced distinctly rather than silently
   reviewed as if empty.
3. An execution-profile key sets the default implementation-review tier; with it
   set, a generic "review the implementation" runs at that tier with the tier
   announced and **no** tier prompt.
4. With the key unset, the existing 4-option tier prompt is unchanged.
5. An explicit tier in the user's ask overrides the profile default; the
   inferred-tier announcement rules in `impl-challenge.md` still hold.
6. `fast.yaml` (seed + live) ships the key set to the advanced tier;
   `default.yaml` leaves it unset.
7. The new key is registered in the settings TUI schema/help and documented in
   the profiles key table and website docs; `website/content/docs/workflows/shadow-agent.md`
   no longer describes the removed "too early" warning.
8. `./.aitask-scripts/aitask_skill_verify.sh` passes; any new helper script has a
   unit test; goldens regenerated in the same commit if any `.md.j2` or closure
   file is touched.

## Related

- **t1159** (`shadow_review_loop_automation`) — adjacent but separate: it
  automates the whole plan/impl review feedback loop between shadow and followed
  agent. This task fixes the entry conditions of a single review. Whichever
  lands second should re-check the other's assumptions about when a review may
  start and which tier it runs at.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T07:14:35Z status=pass attempt=1 type=human
