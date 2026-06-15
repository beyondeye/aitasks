---
Task: t1001_fix_risk_mitigation_landed_whitelist_drift.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# Plan: Fix `aitask_risk_mitigation_landed.sh` whitelist drift (t1001)

## Context

`aitask_risk_mitigation_landed.sh` is a planning-time helper invoked by
task-workflow `planning.md` §6.0a (force-reverify when a risk mitigation
landed). It is shipped as a whitelisted Bash permission to downstream projects
via the `seed/` templates, and is present in this repo's own live Codex rules —
but the entry was never added to this repo's **own** live
`.claude/settings.local.json`.

Confirmed during `/aitask-explore`:

| Repo | Live Claude `.claude/settings.local.json` | Live Codex `.codex/rules/default.rules` |
|------|:--:|:--:|
| aitasks (this repo) | **MISSING** | present (line 49) |
| aitasks_mobile | present (line 94) | present (line 61) |
| aitasks_go | present (line 79) | present (line 45) |

Seed source already has it: `seed/claude_settings.local.json:84`. So both
consumer repos picked it up via `ait setup`/`upgrade`, but the framework repo
itself drifted. Net effect: a Claude session in *this* repo gets a permission
prompt when planning fires the helper, while seeded downstream repos do not.

## Approach

Add the single missing allowlist entry to this repo's live
`.claude/settings.local.json`, matching the seed and the existing Codex rule.

The live file groups `aitask_*` helper entries functionally (not
alphabetically). The closest planning-sibling already present is
`aitask_plan_verified.sh` (line 69) — itself used by `planning.md` §6.0a/6.1
right alongside the risk-mitigation-landed check. Insert the new entry
immediately after it.

## File to modify

`.claude/settings.local.json` — add one line after line 69
(`"Bash(./.aitask-scripts/aitask_plan_verified.sh:*)",`):

```json
      "Bash(./.aitask-scripts/aitask_risk_mitigation_landed.sh:*)",
```

6-space indentation, trailing comma, matching surrounding entries.

## Scope notes

- This is the narrow, already-whitelistable drift fix. It is intentionally
  **not** folded with t454 (broad investigation of skill bash calls that
  *cannot* be whitelisted) — distinct scope.
- `.claude/settings.local.json` is the *live, gitignored* per-user permissions
  file — it is not committed. The fix takes effect immediately in this session
  with no commit needed for the file itself (the task/plan files are committed
  per the normal workflow). Optional spot-check: scan for other
  `seed/`-whitelisted helpers likewise absent from the live file (out of scope
  for the core AC; report only).

## Risk

### Code-health risk: low
- None identified. Single additive permission entry in a gitignored per-user
  config; no source-code path touched; no behavior change beyond suppressing a
  permission prompt for an already-trusted, test-covered helper.

### Goal-achievement risk: low
- None identified. The one-line addition plainly satisfies the acceptance
  criteria (entry present; no more permission prompt).

## Verification

1. Confirm the entry is present:
   `grep -n risk_mitigation_landed .claude/settings.local.json` → one match.
2. Confirm JSON is still valid:
   `python3 -m json.tool .claude/settings.local.json >/dev/null && echo OK`.
3. Behavioral: a subsequent `./.aitask-scripts/aitask_risk_mitigation_landed.sh`
   invocation (e.g. during a future planning §6.0a) no longer triggers a
   permission prompt.

## Step 9 (Post-Implementation)

Per task-workflow Step 9: review (Step 8), then archival via
`./.aitask-scripts/aitask_archive.sh 1001`. No code-branch merge (fast profile,
current branch).

## Final Implementation Notes

- **Actual work done:** Added the single line
  `"Bash(./.aitask-scripts/aitask_risk_mitigation_landed.sh:*)",` to
  `.claude/settings.local.json` immediately after the `aitask_plan_verified.sh`
  entry, matching `seed/claude_settings.local.json` and the existing
  `.codex/rules/default.rules` entry. JSON validated; `grep` confirms one match.
- **Deviations from plan:** The plan assumed `.claude/settings.local.json` was a
  gitignored per-user file requiring no source commit. **It is in fact
  git-tracked in this repo** (`git check-ignore` returns nothing;
  `git status` shows it modified). Consequence: the change is a normal tracked
  code commit (using plain `git`, `style:` prefix per issue_type bug → actually
  committed with the task's `bug:` type), and the fix is now shared via git
  rather than purely local. This is a strictly stronger outcome that still
  satisfies the AC.
- **Issues encountered:** None.
- **Key decisions:** Inserted next to `aitask_plan_verified.sh` (functional
  grouping the live file uses) rather than alphabetically, since both helpers
  are invoked together in `planning.md` §6.0a/6.1.
- **Upstream defects identified:** None.
