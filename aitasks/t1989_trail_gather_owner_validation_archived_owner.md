---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, python, skills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-14 19:01
updated_at: 2026-10-14 19:15
---

## Context

The two owner paths of `aitask_trail_gather.sh snapshot` disagree. Found
while refreshing `art:trail-testmap-feature`, the trail of topic 1852, whose
owner is the **archived** task t1852. The previous refresh hit the same
problem (it is recorded in that version's `narrative.method_note`), so it
recurs on every refresh of a trail whose owner has since been archived.

The skill tells every refresh to pass the owner explicitly. In
`.claude/skills/aitask-trail/SKILL.md.j2`, Step 3.3 says "**Always pass
`--owner <id>`** with the loaded trail's `owner` … so the gatherer
re-validates it". The gatherer does this (`.aitask-scripts/lib/trail_gather.py`):

- **Explicit `--owner`** (`cmd_snapshot`, "Validate --owner against the fresh
  universe", around line 1100): the owner is looked up in
  `fresh[proj].by_own_id`, which holds the **active** tree only. An archived
  owner fails with `ERROR:unknown_task:aitasks#1852`, and the refresh cannot
  proceed as the skill prescribes.
- **Implicit owner** (around line 1118: "Owner: --owner override, else the
  single scope id, else none"): with one scope id, `OWNER:` is that id
  echoed **without any validation**. So `snapshot --scope topic 1852`
  succeeds and prints `OWNER:aitasks#1852`, the same archived task the
  explicit path refused.

The result is that refreshing an archived-owner trail requires breaking the
skill's rule and falling back to the implicit path. That path validates
nothing, so a mistyped or deleted owner would also pass silently.

A trail outlives its owner by design: a topic root such as t1852 is archived
long before its topic finishes. `aitask_artifact.sh update` keeps working
for such a trail, since it rewrites only the manifest; it worked on
2026-10-14.

## Goal

One owner rule, applied on both paths:

- An owner is valid when it exists in the project's **active or archived**
  tasks. Archived means `aitasks/archived/`, including `old.tar.zst`
  bundles: reuse the archive lookup the gatherer already imports,
  `archive_iter.find_archived_markdown_by_id`.
- A task that exists nowhere stays `ERROR:unknown_task`.
- The implicit single-scope-id owner goes through the **same** validation
  instead of being echoed blindly.
- Decide whether `create` (a new trail) may name an archived owner. The
  artifact substrate writes the owner's task file on create, so an archived
  owner may need to stay refused there. If so, say it in the error (for
  example `ERROR:archived_owner:<ref>`) rather than `unknown_task`, and keep
  refresh (which passes `--owner` only to re-validate) accepting it.

Then update `.claude/skills/aitask-trail/SKILL.md.j2` Step 3.3 so the
"always pass `--owner`" rule matches. Regenerate the rendered variants and
goldens per `aidocs/framework/skill_authoring_conventions.md`, and run
`./.aitask-scripts/aitask_skill_verify.sh`. Suggest port tasks for the other
agent trees, as `CLAUDE.md` requires for skill changes.

## Verification

Add to `tests/test_trail_gather.py`:

- explicit `--owner` naming an archived task → `OWNER:<ref>`, no error;
- explicit `--owner` naming a nonexistent task → `ERROR:unknown_task`;
- implicit single-id owner naming a nonexistent task → an error, not a
  silent `OWNER:` echo;
- an owner found only in an `old.tar.zst` bundle is accepted;
- a negative control showing the archived-owner case fails before the fix.

Also: `bash tests/test_skill_render_aitask_trail.sh` and
`./.aitask-scripts/aitask_skill_verify.sh` after the `.j2` edit.
