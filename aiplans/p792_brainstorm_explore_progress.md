---
Task: t792_brainstorm_explore_progress.md
Base branch: main
plan_verified: []
---

# Plan — t792: Explore-op group progress + canonical `created_by_group`

## Context

In `ait brainstorm` session `brainstorm-635` the user ran an `explore`
operation with two parallel explorer subagents (`explorer_001a`,
`explorer_001b`). Two related issues surfaced:

1. **No visible progress for the parallel explore op.** During the prior
   `patch` operation the status tab showed a 0→100% progress bar; during
   the `explore` op no comparable indicator was seen. Verified the root
   cause: progress *is* written by each agent to
   `<agent>_status.yaml::progress`, and the per-agent rows show a bar
   when expanded — but the **group row** (`GroupRow.render()` in
   `.aitask-scripts/brainstorm/brainstorm_app.py:1692-1702`) shows only
   `agents: N` and no progress at all. Patcher groups have a single
   agent, so the user could "drill down" and see one bar. With two
   parallel explorers the user is unlikely to expand both — and even
   when expanded, two separate bars don't tell them "where the *op* is".
   They want an aggregate group-level progress indicator.

2. **One of the two explore-generated nodes lost its operation linkage.**
   Inspecting `.aitask-crews/crew-brainstorm-635/br_nodes/`:
   - `n002_template_resolved_gates.yaml::created_by_group: explore_001` ✅
   - `n002_profile_templated_gates.yaml::created_by_group: op_explore_001` ❌
     (no such group exists in `br_groups.yaml`; the real group is
     `explore_001`).

   In the graph tab the "good" node renders its operation block (the
   group exists, so the agent roster shows up); the "bad" node has a
   `created_by_group` that doesn't resolve, so nothing is shown.

   Root cause: `_assemble_input_explorer()` in `brainstorm_crew.py:191`
   never writes the operation group name into the agent's `_input.md`,
   yet `templates/explorer.md:40` instructs the agent to set
   `created_by_group: The operation group ID provided in the input`.
   The agent has to invent the value, and parallel agents drift —
   one writes `explore_001`, another writes `op_explore_001`. The same
   gap exists for `node_id` ("Use the ID assigned by the orchestrator
   (provided in input)" — the input never provides one), but
   t792's user-visible damage is `created_by_group`, so this plan
   addresses it surgically.

   The apply path (`brainstorm_session.py:860-861`) already has a
   fallback to `_agent_to_group_name(agent_name)` — but it fires only
   when the field is **missing**, not when the agent supplies a wrong
   value. Same fallback exists for the patcher at
   `brainstorm_session.py:643-644`.

3. **Design intent clarification (no code change).** The user asked
   whether multiple explorer agents are supposed to merge into one
   node. The design doc
   (`aidocs/brainstorming/brainstorm_engine_architecture.md:953-1025`)
   is explicit: **one explorer → one node**; merging happens later via
   `compare` / `hybridize` / `synthesize` ops. The "second node has
   information about all the sub-agents that run" perception is a
   side-effect of the graph tab rendering the *group's* agent roster
   (`agents: [explorer_001a, explorer_001b]`) on whichever node still
   resolves its `created_by_group` — both nodes belong to the same
   group, so when the bug above is fixed, the agent roster will show
   on **both** nodes (correctly, because both are products of the same
   `explore_001` op). No design change needed; the architecture doc
   already says so. The README/website don't need updating either —
   the confusion was caused entirely by issue #2.

This task is `issue_type: bug` and scoped to brainstorm engine code
under `.aitask-scripts/brainstorm/`.

## Changes

### 1. Force-canonical `created_by_group` in the apply paths

**Files:**
- `.aitask-scripts/brainstorm/brainstorm_session.py:643-644` (patcher path)
- `.aitask-scripts/brainstorm/brainstorm_session.py:860-861` (explorer / synthesizer path via `_apply_node_output`)

Replace the "only-if-missing" assignment with an unconditional
overwrite. The group name is fully derivable from the agent name via
`_agent_to_group_name()` (already exists at
`brainstorm_session.py:516`); there is no reason to trust the agent's
value. This eliminates the entire class of bug where parallel agents
emit divergent group names.

Before (both sites, same pattern):
```python
if not node_data.get("created_by_group"):
    node_data["created_by_group"] = _agent_to_group_name(agent_name)
```

After:
```python
# created_by_group is authoritative from the agent name — never
# trust the agent's value (parallel agents drift; see t792).
node_data["created_by_group"] = _agent_to_group_name(agent_name)
```

Rationale: minimal, defensive, retroactive — works without any
template/work2do edits. Pre-existing nodes with wrong values are not
rewritten (out of scope; future explores get correct values).

### 2. Drop `created_by_group` from the agent's output schema

**Files:**
- `.aitask-scripts/brainstorm/templates/explorer.md:40,156` (and the work2do header at line 35 if mirrored)
- `.aitask-scripts/brainstorm/templates/patcher.md` (matching line that says "created_by_group: …")
- `.aitask-scripts/brainstorm/templates/synthesizer.md` (matching line)
- `.aitask-scripts/brainstorm/templates/initializer.md` (matching line)
- `.aitask-scripts/brainstorm/templates/detailer.md` (if present in the metadata schema description)

In each template, remove the line that tells the agent to emit
`created_by_group` (or replace with: "the orchestrator assigns this —
do not emit"). This is purely cosmetic: change #1 already makes the
agent's value irrelevant. But silently ignoring agent output that the
template still requests would confuse future template editors.

The exact line in `explorer.md` is line 40:
`- created_by_group: The operation group ID provided in the input`
and line 156 (output checklist):
`- created_by_group (operation group ID from input)`.
Inspect the other templates with grep to find their analogues.

(Same applies to `node_id` — the input doesn't provide one either —
but fixing that is out of scope for this task; it's a separate
operational bug that has not bitten the user yet because the apply
code calls `next_node_id(wt)` and parallel slugs happen to differ.
Note it in Final Implementation Notes as an upstream defect.)

### 3. Group-level aggregate progress bar in the Status tab

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

Add aggregate progress to the group row. Two places to touch:

a. **`GroupRow.render()` at line 1692-1702.** Today it returns:
   ```
   ▶ explore_001  explore  Running  agents: 2  2026-05-18 19:00:40
   ```
   Change it to include a small block-progress bar when at least one
   agent has progress > 0 and the group is not Completed:
   ```
   ▶ explore_001  explore  Running  agents: 2  ███░░░░░░░ 30%  2026-05-18 19:00:40
   ```

b. **Where it reads per-agent status.** `GroupRow` currently stores
   only the `group_info` dict from `br_groups.yaml`. It does not know
   each agent's `progress`. Two implementation options; pick (i):

   (i) *Compute aggregate at refresh time and pass it to GroupRow.*
       In `_refresh_status_tab` at `brainstorm_app.py:3695-3703`,
       before constructing `GroupRow(...)`, walk `ginfo.get("agents", [])`
       and read each agent's `<wt_path>/<agent>_status.yaml`, taking the
       `progress` field. Aggregate = `int(round(mean(progresses)))`
       across agents that exist; clip to 0-100. Pass this as a new
       kwarg `aggregate_progress=`. The render method then formats the
       10-block bar the same way the per-agent row does
       (`brainstorm_app.py:3849-3858`) — extract that as a tiny helper
       `_format_progress_bar(progress: int) -> str` and reuse it in
       both `GroupRow.render` and `_mount_agent_row`.

   (ii) *Compute aggregate inside GroupRow.render.* Rejected — render
        should be cheap and side-effect-free; reading 2-N YAMLs per
        refresh per group is fine in `_refresh_status_tab` but
        unwanted in render (Textual may re-render on focus/blur).

   Aggregate semantics:
   - **Mean across agents** (rounded). Simpler than min/max and matches
     the user's mental model ("the explore op is halfway done").
   - When the group `status` is `Completed`, omit the bar (the bar
     would always read 100% and add visual clutter next to the
     "Completed" status).
   - When no agent has progress > 0, omit the bar (same convention as
     the per-agent row).

c. **Auto-refresh hits this for free.** `_status_refresh_timer` at
   `brainstorm_app.py:3187` already calls `_refresh_status_tab` every
   30s; the user-driven flash refresh stays unchanged. No new timer.

This is a TUI change. Per CLAUDE.md the TUI conventions are in
`aidocs/tui_conventions.md`; read before implementing if the diff
touches keybindings or layout — this one is purely a render-string
change and a new aggregation helper, no key/layout impact.

### 4. Tests

Add focused tests; no full TUI run needed.

- **`tests/test_brainstorm_apply_created_by_group.sh` (new).**
  Build a tiny fake crew worktree, simulate an explorer output where
  `NODE_YAML` block contains `created_by_group: op_explore_001`, run
  `apply_explorer_output` via `python3 -c "from brainstorm.brainstorm_session
  import apply_explorer_output; ..."`, and assert the resulting node
  YAML file has `created_by_group: explore_001`. A matching case for
  the patcher path.

  Reuse the helper conventions from existing brainstorm tests; grep
  `tests/` for `apply_explorer_output` / `apply_patcher_output` to
  find an existing scaffold to copy. The scaffold should write the
  output `.md`, the `br_groups.yaml`, and the parent node files needed
  by `_apply_node_output`'s `create_node` call.

- **`tests/test_brainstorm_group_progress_aggregate.sh` (new), OR an
  inline Python case in an existing brainstorm test file.** Test the
  new `_format_progress_bar()` helper plus the aggregation arithmetic
  in isolation — given a list of `_status.yaml` snippets, compute the
  aggregate. No Textual harness required.

- **Verify the existing `tests/test_brainstorm_*.sh` files still pass**
  (`bash tests/test_brainstorm*.sh`) — none of them should care about
  the changes here, but run them defensively.

## Verification

1. **Unit tests:**
   ```bash
   bash tests/test_brainstorm_apply_created_by_group.sh
   bash tests/test_brainstorm_group_progress_aggregate.sh
   for f in tests/test_brainstorm_*.sh; do bash "$f"; done
   ```

2. **Lint:**
   ```bash
   shellcheck tests/test_brainstorm_apply_created_by_group.sh \
              tests/test_brainstorm_group_progress_aggregate.sh
   python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_session.py
   python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py
   ```

3. **Manual TUI smoke (in the existing `brainstorm-635` session, no
   new run needed for the progress bar test — the existing
   `explorer_001a/b_status.yaml` files have progress 100 and group
   `Completed`, so the bar is suppressed; flip one back to 50 in a
   throwaway copy to see the bar render). After the apply-path fix,
   replay the existing `explorer_001b_output.md` against a fresh fake
   worktree (or, simpler, point the unit test at it) and confirm the
   stored `created_by_group` value is `explore_001` regardless of what
   the agent emitted.

4. **Regression:** verify the graph tab's per-node operation-block
   lookup still works on both old nodes (existing
   `created_by_group: explore_001` value) and on any new nodes
   created with the fixed apply path. No migration of historical
   `op_explore_001` values — out of scope; the user can manually fix
   that one node or simply leave it.

## Out of scope (for Final Implementation Notes)

- `node_id` is also referenced in templates as "assigned by the
  orchestrator (provided in input)" but the input never assigns one.
  Parallel explorers can in principle pick colliding `node_id` slugs
  (in `brainstorm-635` they happened not to). Worth a follow-up bug
  task; not addressed here.
- Historical wrong `created_by_group` values in already-stored nodes
  (e.g. `n002_profile_templated_gates.yaml::created_by_group:
  op_explore_001` in `brainstorm-635`) are not rewritten. Manual
  cleanup is one-line; no migration script proposed.
- `aidocs/brainstorming/brainstorm_engine_architecture.md` already
  documents the "one explorer → one node" design accurately. The
  user's confusion was a symptom of the bug above, not a doc gap.

## Cross-version porting (per CLAUDE.md)

All changes live under `.aitask-scripts/brainstorm/` (Python + agent
templates) — framework code shared across all four code-agent
surfaces. No skill/command porting follow-ups needed.

## Commit plan

Single code commit:

```
bug: Force canonical created_by_group and add group-level progress aggregate (t792)
```

Plan file commit (separate, via `./ait git`):

```
ait: Update plan for t792
```
