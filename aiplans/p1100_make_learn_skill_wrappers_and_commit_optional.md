---
Task: t1100_make_learn_skill_wrappers_and_commit_optional.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# t1100 — Make learn-skill wrappers + commit optional

## Context

`aitask-learn-skill` generates a static Claude Code skill from gathered content.
Its shared generation core, `.claude/skills/aitask-learn-skill/generate.md`, has
two limitations found during review:

1. **No cross-agent wrappers.** It only ever writes `.claude/skills/<name>/SKILL.md`.
   A user who also uses Codex CLI or OpenCode must hand-create the wrapper stubs.
2. **Unconditional commit.** `generate.md` step 7 always runs `git add` +
   `git commit`, giving the user no chance to review or stage the skill first.

The fix makes both optional and prompt-driven.

**Design decision — do NOT reuse the framework stub renderer.** The obvious reuse
target, `aitask_audit_wrappers.sh apply-wrapper`, renders the *framework's* stub:
it speaks in the framework's voice ("wrapper for code agents that use the shared
`.agents/` skills root … Antigravity CLI as support is added") and references
`.agents/skills/codex_tool_mapping.md` / `.opencode/skills/opencode_tool_mapping.md`.
Those mapping docs are **not** in `seed/` — they are aitasks-framework artifacts,
not something a user's own skill owns or that travels if the skill is copied
elsewhere. Baking them into a user-generated skill contradicts `generate.md`'s own
rule (L17-19): a user skill uses the **generic** best-practices guide and "must
not adopt" framework conventions. `aitask_audit_wrappers.sh`'s discover/port
lifecycle is also scoped to `aitask-*` skills — a user skill isn't part of it.

So we emit **generic, self-contained, minimal** wrappers from a **new dedicated
helper**, `.aitask-scripts/aitask_learn_wrappers.sh`.

Confirmed decisions (from the user):
- Generic self-contained stubs via a dedicated helper (not `aitask_audit_wrappers.sh`).
- Minimal content: a pure pointer to the canonical Claude file — **no**
  tool-translation hint, **no** framework references.
- Only emit wrappers for agent trees the project actually has.
- Commit prompt is two options: **Commit** (as today) / **Don't commit**
  (no `git` at all — user stages themselves).

## Changes

### 1. New helper — `.aitask-scripts/aitask_learn_wrappers.sh`

Follows repo shell conventions (`#!/usr/bin/env bash`, `set -euo pipefail`,
sources `lib/terminal_compat.sh` + `lib/task_utils.sh`, `cd` to repo root). It
reuses `read_yaml_field` from `task_utils.sh` to read the generated skill's
`description`. Trees use the same vocabulary as the audit script:
`agents` / `opencode-skill` / `opencode-command`.

Generic minimal stub content (`<name>`, `<description>` interpolated):

- **agents** → `.agents/skills/<name>/SKILL.md`
  ```
  ---
  name: <name>
  description: <description>
  ---

  Read and follow `.claude/skills/<name>/SKILL.md` and execute its workflow.
  ```
- **opencode-skill** → `.opencode/skills/<name>/SKILL.md` — identical body.
- **opencode-command** → `.opencode/commands/<name>.md`
  ```
  ---
  description: <description>
  ---

  Arguments: $ARGUMENTS

  @.claude/skills/<name>/SKILL.md
  ```
  (`@`-include is a standard OpenCode command mechanism, not framework-specific.)

Subcommands (mirrors the audit script's render/apply split for testability):

- `render <tree> <name>` — print the stub to stdout (pure, no writes). Dies if
  the source `.claude/skills/<name>/SKILL.md` is missing or has no description.
- `emit <name> [--force]` — self-gating batch writer. **Validate the source
  first, before writing anything:** if `.claude/skills/<name>/SKILL.md` is
  missing or has no readable `description`, print `ERROR:source-unreadable:<name>`
  (to stderr) and **exit nonzero** — do not write partial output. This
  distinguishes a genuine bad-source failure from the benign per-tree outcomes.
  Only once the source is valid, loop the trees with presence gates:
  `agents` → `[[ -d .agents/skills ]]`; `opencode-skill`/`opencode-command` →
  `[[ -d .opencode ]]`. Per tree: root absent → `SKIP:<tree>:tree-absent`;
  target exists and no `--force` → `EXISTS:<target>` (never clobbers); else
  `mkdir -p` + write → `WROTE:<target>`. When the source is valid, exit 0 (the
  benign `SKIP:`/`EXISTS:`/`WROTE:` lines are the result — those alone never
  fail the batch). `render` likewise dies nonzero on an unreadable source.
- `usage`/help + dispatcher `case`.

### 2. Whitelist the new helper (framework touchpoints)

`generate.md` invokes the helper, so register it via the existing tooling:
```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_learn_wrappers.sh
```
This inserts it (alphabetically) into touchpoints 1/3/4/6/7 (`.claude/settings.local.json`,
`.codex/rules/default.rules`, `seed/claude_settings.local.json`,
`seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`). Verify with
`audit-helper-whitelist aitask_learn_wrappers.sh` → no `MISSING:` lines.

### 3. New test — `tests/test_learn_wrappers.sh`

Source `tests/lib/asserts.sh`. **Run entirely inside throwaway temp git repos**
(`mktemp -d` + `git init`, invoking the helper by absolute path with cwd set to
the temp repo) so the real repo is never polluted and each tree-shape is
controllable. The helper resolves its own root via `git rev-parse
--show-toplevel` and loads its libs by absolute `SCRIPT_DIR`, so it operates on
the temp repo. `trap` removes each temp dir.

- **Case A — both trees present.** Temp repo with `.claude/skills/zz/SKILL.md`
  (name + description + `user-invocable: true`), `.agents/skills/`, `.opencode/`.
  - `render agents zz` → stdout contains the `name`, `description`, and the
    pointer `.claude/skills/zz/SKILL.md`, and does **NOT** contain
    `codex_tool_mapping` / `opencode_tool_mapping` / `Source of Truth` (negative
    assertion — proves the generic stub, not the framework one).
  - `render opencode-command zz` → contains `@.claude/skills/zz/SKILL.md` and
    `$ARGUMENTS`.
  - `emit zz` → `WROTE:` for all three canonical paths; each file exists with the
    pointer body; exit 0.
  - Re-run `emit zz` → `EXISTS:` for the three targets (no overwrite); exit 0.
- **Case B — Claude-only repo (negative control for tree-gating).** Temp repo
  with `.claude/skills/zz/SKILL.md` but **no** `.agents` / `.opencode`.
  - `emit zz` → `SKIP:agents:tree-absent`, `SKIP:opencode-skill:tree-absent`,
    `SKIP:opencode-command:tree-absent`; exit 0; and assert **no** `.agents` or
    `.opencode` directory/file was created (`[[ ! -e .agents ]] && [[ ! -e .opencode ]]`).
    This is the assertion the both-trees-present case cannot make.
- **Case C — unreadable source (fail-fast).** Temp repo with the agent trees but
  **no** `.claude/skills/zz/SKILL.md` (or one lacking a `description`).
  - `emit zz` → prints `ERROR:source-unreadable:zz` and **exits nonzero**;
    assert no wrapper files were written.

### 4. `generate.md` — optional wrappers + optional commit

Restructure the tail of `## Procedure` (current 6→8):

- **Step 6 — Verify** (unchanged).
- **Step 7 (NEW) — Offer cross-agent wrappers.**
  - Coarse detect: `codex_present = [ -d .agents/skills ]`,
    `opencode_present = [ -d .opencode ]`. If **neither**, skip this step
    entirely (no prompt); `wrapper_paths` stays empty.
  - Else `AskUserQuestion` — Header "Wrappers", ~"Also make `/<name>` invokable
    from the other agent(s) in this project?"; description names only the present
    trees. Options: "Yes, create wrappers" / "No — Claude only".
  - On "Yes": run `./.aitask-scripts/aitask_learn_wrappers.sh emit <name>` and
    **check its exit status**. On success, parse `WROTE:<path>` into
    `wrapper_paths` (surface `SKIP:`/`EXISTS:` as-is). On a **nonzero exit**
    (`ERROR:source-unreadable:…`), do NOT silently proceed: tell the user
    wrappers could not be generated (the just-generated source skill is
    unreadable / missing metadata — a red flag worth fixing), leave
    `wrapper_paths` empty, and let the user decide at the Step 8 commit prompt
    whether to still commit the Claude-only skill. Helper self-gates, so absent
    trees are skipped regardless.
- **Step 8 (was 7) — Stage & commit (optional).** Show the generated `SKILL.md`
  path plus any `wrapper_paths`, then `AskUserQuestion` — Header "Commit",
  ~"Commit the generated skill now?". Options:
  - "Yes, commit" → `git add .claude/skills/<name>/` **plus** each
    `wrapper_paths` entry, then
    `git commit -m "feature: Add /<name> skill learned from <source_label>"`
    (plain `git`, never `./ait git`). Append " (+ cross-agent wrappers)" to the
    subject when wrappers were created.
  - "No, leave it for me" → **no** git at all; tell the user the files are
    written but uncommitted and list the paths.
- **Step 9 (was 8) — Report.** As today, plus whether wrappers were created (and
  for which agents) and whether the result was committed or left uncommitted.

Update the three provenance lines claiming an unconditional commit:
- `generate.md` intro **Output:** line (~L14) — reflect "optionally with generic
  cross-agent wrappers, and optionally committed".
- `.claude/skills/aitask-learn-skill/SKILL.md` intro (~L13-14) — "created and
  committed" → "created (and, if the user chooses, generic cross-agent wrappers
  written and the result committed)".
- `.claude/skills/aitask-learn-skill/SKILL.md` **Step 3** (~L113) — "writes and
  commits `.claude/skills/<name>/SKILL.md`" → "writes `.claude/skills/<name>/SKILL.md`,
  optionally emits generic cross-agent wrappers, optionally commits" (so an agent
  reading only the top-level skill isn't misled about the now-optional commit).

### Cross-agent port

**None needed.** `generate.md` and the top-level `aitask-learn-skill/SKILL.md`
live in the Claude tree; the Codex/OpenCode copies of `aitask-learn-skill` are
thin pointer stubs that read the Claude SKILL.md (→ `generate.md`) transitively,
so edits propagate with no separate port task. `aitask_learn_wrappers.sh` is a
shared, agent-agnostic `.aitask-scripts/` helper. No `.j2`/goldens/stub-surface
changes.

## Risk

### Code-health risk: low
- Changes default learn-skill behavior (previously always committed; now asks) ·
  severity: low · → mitigation: TBD — intended; the two-option prompt is
  explicit, and `test_shadow_spawn_learner.sh` is `--dry-run` command-resolution
  only (never executes `generate.md`), so nothing depends on the auto-commit.
- New standalone helper `aitask_learn_wrappers.sh` adds a small script surface ·
  severity: low · → mitigation: TBD — self-contained, shellcheck-clean,
  unit-tested, whitelisted via existing tooling.

### Goal-achievement risk: low
- None identified. Generic self-contained stubs (the user's chosen shape) keep
  the user artifact free of framework internals; both asks are fully covered.

`risk_mitigations_planned = false` — no before/after mitigation tasks warranted.

## Verification

- `bash tests/test_learn_wrappers.sh` → PASS (Case A both-trees render+WROTE+
  idempotent-EXISTS incl. negative no-framework-refs assertion; Case B
  Claude-only SKIP + no-dirs-created negative control; Case C unreadable-source
  fail-fast nonzero; all in temp git repos, no real-repo pollution).
- `shellcheck .aitask-scripts/aitask_learn_wrappers.sh` → clean.
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_learn_wrappers.sh`
  → no `MISSING:` lines.
- `./.aitask-scripts/aitask_skill_verify.sh` → passes (no framework
  `.j2`/stub-surface change).
- `bash tests/test_shadow_spawn_learner.sh` → still PASS (sanity; independent).

## Post-Implementation

Follow task-workflow Step 8 (review) → Step 9 (merge approval, run declared
`risk_evaluated` gate via `./ait gates run 1100`, archive via
`aitask_archive.sh 1100`). Fast profile works on the current branch (no worktree
to clean up).

## Final Implementation Notes

- **Actual work done:** Added `.aitask-scripts/aitask_learn_wrappers.sh` (generic
  cross-agent wrapper emitter: `render <tree> <name>` + `emit <name> [--force]`,
  self-gating on `.agents/skills` / `.opencode` presence, fail-fast
  `ERROR:source-unreadable` on a missing/description-less source skill, and
  `SKIP:`/`EXISTS:`/`WROTE:` per-tree lines). Added `tests/test_learn_wrappers.sh`
  (28 assertions, all passing, run in throwaway temp git repos). Restructured
  `generate.md`'s tail into step 7 (optional wrappers), step 8 (optional
  Commit/leave-uncommitted), step 9 (report) and updated its Output line. Updated
  both provenance lines in `aitask-learn-skill/SKILL.md`. Whitelisted the new
  helper across all 5 touchpoints via `aitask_audit_wrappers.sh apply-helper-whitelist`.
- **Deviations from plan:** None. Implemented exactly as the approved plan,
  including all three reviewer-requested refinements (emit fail-fast semantics,
  negative-control tree-gating test, third stale-wording spot).
- **Issues encountered:** `shellcheck` returns exit 1 on the two SC1091 (info)
  "not following sourced lib" lines — this is the universal repo baseline (the
  existing `aitask_audit_wrappers.sh` produces the identical findings), not a
  real warning.
- **Key decisions:** Deliberately did NOT reuse `aitask_audit_wrappers.sh`'s stub
  renderer: its stubs speak in the framework's voice and reference
  framework-internal `codex_tool_mapping.md` / `opencode_tool_mapping.md` (not in
  `seed/`), which must not leak into a user-generated skill. A dedicated helper
  emitting minimal generic pointer stubs keeps the user artifact self-contained,
  consistent with `generate.md`'s own "generic best-practices, not framework
  conventions" rule.
- **Upstream defects identified:** None.
