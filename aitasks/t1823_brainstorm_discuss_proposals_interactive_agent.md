---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [ait_brainstorm, tui, skills, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1823_2, t1823_3, t1823_4, t1823_5, t1823_6]
created_at: 2026-09-17 08:21
updated_at: 2026-09-17 12:53
---

## Goal

Add a node operation to the `ait brainstorm` TUI that launches an **interactive,
advisory-only coding agent** over the proposal file(s) of the selected node(s),
so the user can reason about them conversationally: compare them (in simple
words or in depth), ask questions, get a plain-language-but-complete
explanation, and have them checked for structural design flaws and risks.
Similar in spirit to the shadow agent (`aitask-shadow`), but anchored on
brainstorm proposals instead of a followed agent pane.

## Decisions settled during exploration

- **Authority:** strictly advisory / read-only. The agent never edits proposal
  files, node YAML, or session state. (Write-back / "suggest an op" is
  follow-up material, not this task.)
- **Cardinality:** works on 1 or more nodes — the cursor node, or the
  space-marked set (`NodeSelection.effective()`).
- **Context beyond proposal paths (all lazy — read on demand, NOT at startup):**
  node metadata YAML (`br_nodes/<id>.yaml`: dimensions, parents), the
  brainstormed task's id/description, and parent lineage (ancestor proposals,
  to explain how a node evolved).
- **Launch UX:** agent dialog first, then tmux — the codebrowser-explain
  pattern (`AgentCommandScreen` to pick agent/model and window-vs-split
  placement), with `spawn_in_terminal` fallback when tmux is unavailable.

## Skill behaviour (new skill, e.g. `aitask-brainstorm-discuss`)

- **Fast start:** on launch, immediately list the passed proposals with a short
  differentiating title each and a short handle (e.g. `A`, `B`, … plus node id)
  so they are easy to refer to. Do **not** process/analyse them up front — a
  quick skim for a title only. With one proposal, skip the list ceremony.
- Then offer a capability menu (derive it from the capability section — single
  source of truth, as shadow's Step 0 does; `>`-prefixed shortcodes):
  compare proposals (simple words / detailed), explain a proposal in simple
  words but fully, free-form Q&A, structural design-flaw & risk check.
  Consider reusing/adapting shadow sub-procedures (`plan-explain.md`,
  `plan-challenge.md`, `plan-assumptions.md`, `concern-format.md`) rather than
  forking their wording.
- Model on the shadow's stub + `.md.j2` profile-aware shape
  (`.claude/skills/aitask-shadow/`, `aidocs/framework/stub-skill-pattern.md`,
  `aidocs/framework/skill_authoring_conventions.md`). Bulk context is
  self-fetched by the skill, never passed on argv.

## Code touchpoints found

**Brainstorm TUI** (`.aitask-scripts/brainstorm/`)
- Proposal path: `<session_path>/br_proposals/<node_id>.md`; resolve via
  `brainstorm_op_refs.file_for_ref(session_path, OpDataRef("node_proposal", nid))`
  (`brainstorm_op_refs.py:44-56`). Session dir is the crew worktree
  (`brainstorm_session.py:54`).
- Op catalogue / help: `constants.py` `_DESIGN_OPS`/`_SESSION_OPS`/`_OP_LABELS`
  (:70-91), `_OPERATION_HELP` (:94+); cardinality classes (:404-410) consumed by
  `utils.op_states_for_selection` (`utils.py:406-462`) — the new op needs a
  class accepting >=1 node.
- Picker rows: `NodeActionSelectModal._OPS` / `_LOCAL_LABELS` (`modals.py:1274-1288`).
- Dispatch: `_on_node_action_result` (`brainstorm_app.py:2941-2972`) — branch
  **before** the wizard, as `delete` does; this op must NOT register a crew
  agent. Consider a direct key binding too (`BINDINGS` :2041-2073,
  `ShortcutsMixin` scope `brainstorm`, `_TAB_SCOPED_ACTIONS` :2078).
- No on-demand interactive agent path exists in brainstorm today (it imports
  only `is_tmux_available` from `agent_launch_utils`).

**Launch pattern to copy:** `codebrowser_app.py:1468-1531` `action_launch_agent`
— `resolve_dry_run_command(root, "<op>", *args)` → `resolve_agent_string` →
`AgentCommandScreen(...)` → `launch_in_tmux(screen.full_command, cfg)` +
`maybe_spawn_minimonitor`; terminal fallback. Follow
`aidocs/framework/tmux_gateway.md` and `aidocs/framework/tui_conventions.md`.

**Codeagent wrapper:** new entry in `SUPPORTED_OPERATIONS`
(`aitask_codeagent.sh:26`) with per-agent dispatch (claudecode :481-484,
codex :575, opencode :599-601), plus a default key in
`aitasks/metadata/codeagent_config.json` (and seed). **Constraint
(`aitask_codeagent.sh:443-454`): skill args may not be empty or contain
whitespace** — proposal paths are safe, but decide the argv shape deliberately
(e.g. `<session/task id> <node_id>...` and let the skill resolve paths, vs.
raw paths). See `aidocs/framework/aitasks_extension_points.md`.

**Skill plumbing:** `aitask_skill_render.sh` closure, goldens regeneration,
`aitask_skill_verify.sh`, render inventory test, opencode permission allowlist
(`aitasks/metadata/opencode_config.seed.json`), profile resolution key +
`userconfig.yaml` default profile, `aitask-audit-wrappers`.

## Out of scope / suggested follow-ups

- Codex CLI and OpenCode ports of the new skill (separate aitasks, per CLAUDE.md).
- Website docs for the new op (brainstorm TUI pages).
- Any write-back from the discussion into the session (notes, suggested ops).

## Adjacent pending tasks (not overlapping, for awareness)

t745 (improve node comparator), t417 (diff viewer for brainstorming), t571
(structured proposal sections — relevant if discussion should scope to
sections), t1296 (AgentCommandScreen key collisions).
