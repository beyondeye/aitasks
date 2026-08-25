---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: []
anchor: 1595
followup_kind: risk_mitigation
created_at: 2026-08-26 00:02
updated_at: 2026-08-26 00:02
---

## Origin

Risk-mitigation ("after") follow-up for t1612, created at Step 8d after implementation landed.

## Risk addressed

Addresses: `assemble_aitasks_instructions` has no reachable seed when `aitasks/` is a
dangling symlink and `seed/` was deleted at install, so no instruction surface can be
generated. From t1612's plan `## Risk` → goal-achievement risk:

> **`setup_data_branch` early-return case 4 is not fixed on installed projects.**
> `install.sh:1335` deletes `seed/`, so after a failed `git worktree add` on a fresh
> branch-mode clone the `aitasks` symlink dangles, `assemble_aitasks_instructions`
> returns 1, and `update_claudemd_git_section` writes nothing wherever it is called
> from. The task's goal ("`CLAUDE.md` is regenerated on every `ait setup`") is
> therefore delivered for cases 1-3 only. · severity: low (residual)

## Goal

Give `assemble_aitasks_instructions` (`.aitask-scripts/aitask_setup.sh:1279-1314`) a
third fallback — e.g. a packaged copy of the seeds under `.aitask-scripts/` — so every
instruction surface can still be generated when both existing sources are unreachable.

t1612 moved `update_claudemd_git_section` to `setup_code_agents` so `CLAUDE.md` is
regenerated on every `ait setup`. That fixed three of `setup_data_branch`'s four
early-return cases. The fourth is not a placement problem and is **not** specific to
`CLAUDE.md` — it is a seed-resolution gap that silently skips *every* surface.

## Evidence (verified during t1612)

- `.aitask-scripts/aitask_setup.sh:1279-1314` — `assemble_aitasks_instructions` resolves
  the shared seed from `$project_dir/aitasks/metadata/aitasks_agent_instructions.seed.md`,
  falling back to `$project_dir/seed/aitasks_agent_instructions.seed.md`, then `warn`s to
  stderr and returns 1.
- Every caller swallows that failure by design: `update_claudemd_git_section:1363` and
  `update_agentsmd:1397` both do `content="$(assemble_aitasks_instructions …)" || return 0`;
  `setup_codex_cli:2372` and `setup_opencode:2523` use `|| true`. So the surface is skipped
  **silently** from the user's point of view (the warn goes to stderr mid-setup).
- `install.sh:1335` — `rm -rf "$INSTALL_DIR/seed"` after the seed installers run, so an
  installed project has no `seed/` fallback at all.
- In branch mode `aitasks/` is a symlink into `.aitask-data/`. If `git worktree add` fails
  (`aitask_setup.sh:1493-1497`, `setup_data_branch`'s fourth early return) on a fresh clone
  of a branch-mode repo, that symlink is committed but dangling — so neither source resolves.
- Confirmed empirically in t1612's test work: `tests/test_data_branch_setup.sh` Test 3's
  fixture copies no seed, and `update_claudemd_git_section` has therefore never written
  anything there — today or after t1612.

## Scope notes

- The fix belongs in the **resolver**, not in any one caller — all four surfaces share it.
- Consider whether a total resolution failure should stay best-effort (`|| return 0`) or
  become a visible warning/error; silently shipping a project with no agent instructions is
  arguably worse than failing loudly. Decide deliberately rather than by inheritance.
- `tests/test_setup_git.sh` `setup_fake_project` and `test_data_branch_setup.sh` Test 3 both
  build seedless fixtures — useful starting points for a regression test that pins the new
  fallback.
- Do not undo t1612: `update_claudemd_git_section` must stay in `setup_code_agents`, and
  `setup_data_branch` must keep zero calls to it (pinned by `tests/test_agent_instructions.sh`
  T43 and `tests/test_setup_git.sh` T26).

## Verification

- A regression test driving `assemble_aitasks_instructions` with **neither**
  `aitasks/metadata/` nor `seed/` resolvable, asserting the new fallback resolves.
- A negative control proving the fallback is not masking the normal path (the per-project
  seed still wins when present).
- `bash tests/test_agent_instructions.sh`, `bash tests/test_data_branch_setup.sh`,
  `bash tests/test_setup_git.sh`, `bash tests/test_opencode_setup.sh`.
- `shellcheck .aitask-scripts/aitask_setup.sh`.
