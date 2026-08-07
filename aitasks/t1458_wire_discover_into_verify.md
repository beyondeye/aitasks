---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [gates, claudeskills]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-07 15:50
updated_at: 2026-08-07 15:50
---

## Origin

Risk-mitigation ("after") follow-up for t635_23, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement "recurrence — a skill absent from ALL wrapper trees is invisible to parity":

> `cmd_discover` (the only check that walks the Claude tree for missing wrappers)
> is *not* wired into `aitask_skill_verify.sh`; `cmd_parity` only compares wrapper
> trees to each other, so a skill absent from *all* trees is invisible. That is
> precisely why these three sat unported. After this lands the same hole remains
> open for the next Claude-only skill · severity: medium

## Goal

Close the structural hole that let three gate skills ship Claude-only for months
without any check complaining.

**Current state.** `.aitask-scripts/aitask_skill_verify.sh` (the mandated
pre-commit check, also Test 0 of `tests/test_opencode_setup.sh`) runs
`aitask_audit_wrappers.sh parity` and nothing else on the plain-skill side.
`cmd_parity` (`aitask_audit_wrappers.sh`, ~L174-223) builds its comparison union
from the **wrapper trees only** — deliberately, so that "which skills need a
wrapper?" is never derived from a wrapper tree itself. The documented residual
limit is exactly the failure that occurred: a skill present in *no* wrapper tree
is invisible. `cmd_discover` (~L226-236) *does* walk `.claude/skills/aitask-*`
and emits `GAP:<tree>:<skill>`, but nothing calls it automatically.

**Work.** Wire `discover` into `aitask_skill_verify.sh` alongside `parity`,
reporting gaps as a `WRAPPER_FAIL`-style finding in the same shape as the
existing parity findings (fail-closed on a non-zero exit, same as the parity
block).

**This requires an exemption mechanism** — the reason it was not simply done in
t635_23. `aitask-explorechat` is deliberately Claude-only (a machine-spawned
chatlink gateway, not a user command) and would fail the check immediately.
Design an explicit, discoverable exemption list — a sidecar file or a frontmatter
key on the skill itself — and prefer whichever makes the Claude-only decision
visible *at the skill*, since an out-of-band list rots. Note `list_source_skills()`
already structurally exempts non-`aitask-*` names (`task-workflow`,
`user-file-select`, `ait-git`), so the exemption is only needed for `aitask-*`
skills that are intentionally unported.

Coordinate with **t1456**, which asks the complementary question — whether
`aitask-explorechat` should be ported or exempted. That decision is this task's
motivating exemption entry; land them consistently.

**Verification.** After wiring: `aitask_skill_verify.sh` still passes on a clean
tree; a negative control (temporarily create a `.claude/skills/aitask-<scratch>/`
with no wrappers) makes it fail with a named finding, and adding the scratch skill
to the exemption list makes it pass again; `tests/test_opencode_setup.sh` and
`tests/test_skill_dispatch_contract.sh` stay green. A consumer project with no
`.agents/` or `.opencode/` roots (Claude-only install) must **not** start failing —
mirror the existing tree-presence rule that drops absent trees from the comparison.
