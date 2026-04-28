---
Task: t653_brainstorm_import_proposal_hangs.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# Plan: t653 — Brainstorm import proposal hangs (parent)

## Context

User ran `ait brainstorm` on session 635 and imported a proposal (`aitask-gate-framework.md`). The `initializer_bootstrap` agent ran and produced its expected output file (`.aitask-crews/crew-brainstorm-635/initializer_bootstrap_output.md`, 794 lines, valid delimited blocks). Yet the dashboard still shows the n000_init node as "Imported proposal (awaiting reformat): aitask-gate-framework.md" and opening the detail (Enter) shows the placeholder proposal "Awaiting initializer agent output for `aitask-gate-framework.md`."

Investigation isolated **four independent layers** in the failure chain. Layer A (the runner falsely marking the agent Error after 5 min because the agent never refreshes `_alive.yaml`) is **already in flight as parent t650** (`t650_1` whitelists `ait crew` for code agents; `t650_2` rewrites the brainstorm templates so every Checkpoint emits a real `ait crew status heartbeat` call; `t650_3` is the more aggressive fallback if `t650_2` doesn't stick). t653 explicitly **defers Layer A to t650** and addresses the three surviving links B, C, D.

### B. Brainstorm TUI poll is one-shot and not self-healing on reopen

`_poll_initializer()` (`brainstorm_app.py:3172`) sets `_initializer_done = True` and stops the 2-second timer the first time it sees `Completed` *or* `Error`/`Aborted`. On Error it surfaces a transient toast ("Initializer agent error. Placeholder retained; retry via TUI.") then never polls again — even though the agent eventually wrote `_output.md` and flipped its own status to `Completed` (the on-disk file shows `status: Completed` with `error_message` lingering from the runner's earlier Error write). When the user reopens the TUI, `_load_existing_session()` re-reads `br_nodes/n000_init.yaml` (still the placeholder) and never re-attempts apply — there is no detection of "output file present + node still placeholder".

### C. Initializer agent emits invalid YAML; apply silently fails

`apply_initializer_output()` (`brainstorm_session.py:264`) extracts the `NODE_YAML_START..END` block and calls `yaml.safe_load()`. The session-635 output contains lines like:

```yaml
component_gate_registry: aitasks/metadata/gates.yaml — per-gate config: verifier skill name, type (machine|human), …
```

The em-dash plus second `:` makes this an invalid mapping value (`mapping values are not allowed here, line 28, column 71` — confirmed by re-running `yaml.safe_load` on the actual output file). The exception is swallowed by `_poll_initializer`'s `try/except` (lines 3194–3198). The user sees only a brief toast that disappears when the TUI is closed. The 794-line output sits on disk forever, untouched. The initializer template (`brainstorm/templates/initializer.md`) does not require quoting of em-dash-bearing scalars.

### D. Runner pushes Error and exits before agent finishes; Completed never propagates

`agentcrew_runner.py:979` (`git_commit_push_if_changes`) pushes after each iteration. At iter 15 (09:57:16 in `_runner_launch.log`) it pushed `Error`. The very next log line is "All agents in terminal state — stopping runner" — runner exited at 09:57:16. Agent finished at 10:04:59 and the local `_status.yaml` ended at `Completed`, but no runner was alive to push it. `cmd_set` in `agentcrew_status.py:87` does not push; `AGENT_TRANSITIONS["Error"] = ["Waiting"]` (line 30 of `agentcrew_utils.py`) means a falsely-Error'd agent cannot self-correct to `Completed` via the validator — the agent's recovery path is brittle. Net effect: remote and other PCs see `Error` permanently.

Once Layer A (t650) lands, false-Error becomes rare, but D is still defense-in-depth: any runner crash (SIGKILL, machine restart, network blip mid-iteration) leaves the same divergence between the agent's local Completed write and remote.

### Goal

Make the chain robust **after t650 lands**: even if the agent's output is malformed, the user has a recovery path; even if the user closes and reopens the TUI, the dashboard self-heals; even if the runner dies for any reason after the agent set Completed locally, the final state propagates.

User explicitly asked **fix-forward only** — session-635's on-disk state is left untouched. After this plan's child 2 lands, the user can rerun apply via the new `ait brainstorm apply-initializer 635` CLI to recover that session.

## Approach

Three child tasks, each independently mergeable. Parent t653 declares `depends: [650]` so it is naturally picked after the heartbeat work lands (and the verification flow in t653 can assume the agent reliably heartbeats):

| Child | Layer | One-line scope |
|-------|-------|----------------|
| t653_1 | B — TUI | TUI re-runs apply on session open if output exists + node still placeholder; persistent error banner; non-terminal poll on Error |
| t653_2 | C — apply | Tolerant YAML parser with em-dash auto-quote fallback; tighter prompt template; new `ait brainstorm apply-initializer <session>` retry CLI |
| t653_3 | D — push & recover | `cmd_set` pushes worktree on terminal transition; relax `Error → Completed` transition so a recovering agent can self-correct |

Children are independent (no hard ordering between them). Recommended implementation order: 2 → 1 → 3 (apply tolerance is the highest-leverage fix and unblocks session 635; TUI self-heal then makes the recovery automatic; push/transition is defense-in-depth).

## Child task summaries

### t653_1 — TUI self-heal + persistent retry (Layer B)

**Why:** Even if the apply path fails for any reason, the TUI should recover the node when the user re-opens it. Today the user has no path forward except re-importing.

**Key files:**
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `_load_existing_session`, `_poll_initializer`, new `_try_apply_initializer_if_needed()` method
- `.aitask-scripts/brainstorm/brainstorm_session.py` — small helper `n000_needs_apply(session_path) -> bool`

**Approach sketch:**
1. New helper `n000_needs_apply(session_path)`: returns True iff `br_nodes/n000_init.yaml`'s description starts with `"Imported proposal (awaiting reformat):"` AND `initializer_bootstrap_output.md` exists in the session.
2. On `_load_existing_session()` and on `_start_initializer_wait`, if `n000_needs_apply()` is True → call `apply_initializer_output()` inside a try/except. On success, refresh dashboard. On failure, set `self._initializer_apply_error = str(e)` and render a **persistent banner widget** (not a fading toast) that says "Initializer apply failed: <err>. Run `ait brainstorm apply-initializer <session>` to retry."
3. In `_poll_initializer`, on `Error`/`Aborted`: keep polling at a longer interval (30 s) for `_output.md` to appear; do not set `_initializer_done = True` permanently. When the file appears, attempt apply. (Layer A — t650 — should make Error rare; this branch only matters in pathological cases.)
4. Add a key-binding (e.g. `ctrl+r` while focus is on the dashboard) → "retry initializer apply".
5. Test: manual TUI reopen on a synthetic session that mimics 635's state → dashboard shows real proposal.

### t653_2 — Tolerant apply + prompt hardening + retry CLI (Layer C)

**Why:** The agent will make YAML mistakes occasionally (LLMs do); silent failure is the worst outcome. We can both shrink the failure rate (prompt) and make the failure recoverable (tolerant load + retry CLI + clear error log on disk).

**Key files:**
- `.aitask-scripts/brainstorm/templates/initializer.md` — output rules
- `.aitask-scripts/brainstorm/brainstorm_session.py` — `apply_initializer_output` + new `_tolerant_yaml_load`
- `.aitask-scripts/aitask_brainstorm_apply_initializer.sh` — new helper script
- `ait` dispatcher — wire `ait brainstorm apply-initializer <session>`
- 5-touchpoint whitelist for the new helper (per CLAUDE.md "Adding a New Helper Script")
- `tests/test_apply_initializer_tolerant.sh`

**Approach sketch:**
1. Strengthen `initializer.md` Phase 4: add a "YAML rules" subsection requiring double-quoting any scalar value containing em-dash (`—`), en-dash (`–`), hyphen-space (` - `), a second `:`, or `#`. Add a small bad/good example. (This may interact with t650_2's pseudo-verb rewrite — coordinate by appending the new subsection so the rewrite diff is clean.)
2. `_tolerant_yaml_load(text)`: try `yaml.safe_load`. On `yaml.YAMLError`, run a regex pass that quotes the value of any line `^(\s*)([A-Za-z_][\w]*):\s+(.+)$` whose value contains `—`, `–`, ` - `, `: `, or `#` and is not already quoted. Retry. If still fails: write `<session>/initializer_bootstrap_apply_error.log` with the original parse error, the offending line+column, and the auto-fix attempt diff. Raise.
3. New helper `aitask_brainstorm_apply_initializer.sh <session>` — resolves session path, calls `python -c "from brainstorm.brainstorm_session import apply_initializer_output; apply_initializer_output('<num>')"`. On success, prints `APPLIED:n000_init`. On failure prints `APPLY_FAILED:<err>` and points at the error log.
4. **5-touchpoint whitelist** (this is an explicit deliverable per CLAUDE.md):
   - `.claude/settings.local.json` — `"Bash(./.aitask-scripts/aitask_brainstorm_apply_initializer.sh:*)"`
   - `seed/claude_settings.local.json` — mirror
   - `.gemini/policies/aitasks-whitelist.toml` — `[[rule]]` block
   - `seed/geminicli_policies/aitasks-whitelist.toml` — mirror
   - `seed/opencode_config.seed.json` — `"./.aitask-scripts/aitask_brainstorm_apply_initializer.sh *": "allow"`
5. Wire `ait brainstorm apply-initializer <session>` in the dispatcher.
6. Tests: a fixture file with em-dash YAML that originally fails → tolerant load succeeds. A truly malformed file → fails with the error log written.

### t653_3 — Push terminal status + relax Error→Completed (Layer D)

**Why:** Even with t650 in place, any runner exit between an agent's Completed write and its next iteration leaves remote stale. And the `Error → Completed` validator block prevents an agent that was falsely Error'd from ever recovering.

**Key files:**
- `.aitask-scripts/agentcrew/agentcrew_status.py` — `cmd_set` (push on terminal transition); add `--no-push` flag for callers that want to batch
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — extend `AGENT_TRANSITIONS["Error"]`; possibly move/share `git_commit_push_if_changes`

**Approach sketch:**
1. Extend `AGENT_TRANSITIONS["Error"]` to include `Completed` (and `Running` so the agent can resume mid-flight). Document above the table: "Error is recoverable — a watchdog timeout does not prove the agent failed."
2. In `cmd_set`, after `write_yaml(status_path, data)` and `_recompute_crew_status(wt)`, if the new status is in `("Completed","Aborted","Error")` and `--no-push` was not passed, call `git_commit_push_if_changes(wt, f"agent {agent}: {current} -> {new_status}", batch=True)`. Move `git_commit_push_if_changes` from `agentcrew_runner.py:149` into `agentcrew_utils.py` so both runner and status command import it.
3. Idempotent: skip push if there are no changes (already the helper's behavior).
4. Document clearly: this push happens **synchronously** on the agent's `cmd_set` call. If the user has spotty network, this may add latency to the agent's completion. Acceptable trade-off for state propagation; the `--no-push` flag is the escape hatch.
5. Test: trigger an `Error → Completed` transition via cmd_set; verify status file flips and a commit was created. Trigger a `Running → Completed` with `--no-push`; verify no commit was made.

## Sibling-task discipline

- Each child task description must be self-sufficient (Context, Key Files, Reference Patterns, Implementation Plan, Verification — per `Child Task Documentation Requirements`).
- t653_2 introduces a new helper script → MUST surface the 5-touchpoint whitelist as a deliverable (per CLAUDE.md).
- No frontmatter field is added by any child, so the "Adding a New Frontmatter Field" 3-layer check is not in scope.
- Parent t653 declares `depends: [650]`. After t650 archives, t653's children become pickable.

## Verification (parent-level, after children land)

End-to-end smoke test (ideally on a fresh proposal that triggers em-dashes in the agent's YAML output, since LLMs vary run-to-run):

1. With **t650** in place: agent runs ≥ 6 min without being falsely Error'd (heartbeats fire on every Checkpoint).
2. With **t653_2**: even if the agent's YAML has em-dashes, `apply_initializer_output` succeeds via the tolerant load. Truly malformed output writes `initializer_bootstrap_apply_error.log`.
3. With **t653_1**: closing and reopening `ait brainstorm` after the agent finishes auto-applies the output on next session load.
4. With **t653_3**: an agent that was Error'd by any pathway can call `ait crew status set --status Completed` and have it both succeed locally and push to remote.
5. Manual sanity for session 635: after merging t653_2, run `ait brainstorm apply-initializer 635` → dashboard reflects the real proposal.

## Step 9 reference

After all three children are archived, parent t653 archives automatically (`aitask_archive.sh` handles all-children-done). No worktree merge needed — children commit directly to `main`.
