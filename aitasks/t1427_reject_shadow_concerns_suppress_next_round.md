---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini, aitask_monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1427_1]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
created_at: 2026-08-05 12:04
updated_at: 2026-08-05 17:17
---

In the concern picker (`c` in `ait monitor` / `ait minimonitor`) the user can
select concerns to copy and forward to the code agent, but there is **no way to
reject one**. Rejecting means: do not show me this concern again in the next
review round — after the code agent addresses the forwarded concerns and the
shadow refetches the updated plan/implementation to re-check, a rejected concern
must not come back.

Today every re-review re-raises everything, so the user re-triages the same
dismissed items on every round. That is the friction this task removes.

## Why this is not just a UI toggle

Exploration established that nothing in the pipeline can express "already
rejected" today:

- **The picker is pure-UI with zero persistence.** `ConcernPickerModal`
  (`.aitask-scripts/monitor/monitor_shared.py`) dismisses with the selected
  `list[Concern]` or `None`; the only per-concern state is `_selected` (☑/☐) plus
  a *derived* `informational` dimming. Nothing survives the modal closing.
- **Dedup is per-block, not per-concern, and in-memory only.**
  `_last_concern_block_payload` (minimonitor) and
  `_concern_sig_offered` / `_concern_sig_examined` (monitor) are instance
  dicts keyed on the whole block's payload/signature; they die with the TUI and
  offer no hook to drop individual items.
- **Concerns have no stable identity across rounds.** `Concern` is a NamedTuple
  with no id; the picker itself falls back to positional index because "two equal
  concerns are indistinguishable by value". `concern-format.md` explicitly states
  `region` is "a display label … never a key", and
  `concern_block_signature` is documented "trigger only" with a known reflow
  residual. So no consumer-side hash can serve as a cross-round identity.
- **The shadow has no round memory whatsoever.** No sub-procedure in
  `.claude/skills/aitask-shadow/` mentions dismiss / reject / suppress / round;
  every producer is written as a stateless one-shot that re-derives from a fresh
  capture. `aidocs/framework/shadow_agent.md` has no such concept either.

Consequence: **matching a fresh concern against a rejected one must be semantic
and performed by the shadow agent**, not by `concern_parser.py`. The shadow
re-words bodies between rounds, so exact- or hash-matching would be brittle.

## Required behavior

1. **Reject action in the picker.** A per-row tri-state — none / forward /
   rejected — mutually exclusive, on the existing `_ConcernRow` (it already has a
   `_selected` bool, a ☑/☐ glyph, and per-disposition CSS classes, so this needs
   no new layout or partition). `Space` keeps meaning "forward"; a free key
   (`r`, `x`, and `d` are unbound in the modal) means "reject".
2. **Rejections persist** beyond the modal, beyond the TUI process, and across
   TUI restarts, scoped to the task under review.
3. **The next review round suppresses them.** The shadow consults the rejected
   list before emitting its concern block and drops items that are substantively
   the same as a rejected one *even when reworded*.
4. **Suppression is visible, never silent.** The shadow reports how many
   previously-rejected concerns it suppressed. When it is unsure whether a fresh
   concern matches a rejected one, it keeps the concern and says why — the safe
   direction, consistent with `needs_addressing()` treating an unspecified
   disposition as needing attention.
5. **Rejection is reversible.** Without an un-reject path a single mis-press
   permanently blinds the shadow for that task. Decide and build the surface
   (a picker-side view of rejected items, and/or a helper subcommand).
6. Works for **all four** concern producers, not just plan review.

## Design constraints found during exploration

**Delivery seam — do not rely on the optional context fetch.** Extending
`aitask_shadow_context.sh` with a `REJECTED:` line fits its existing
`TASK_FILE:` / `PLAN_FILE:` / `SIBLING:` line protocol, but shadow **Step 2 is
explicitly optional**, and both `plan-challenge.md` and `plan-assumptions.md`
say their input is "the captured screen *and/or* the fetched plan file". A
shadow can therefore run a whole review round without ever calling it, so a
context-fetch-only design is a fallback with an unreachable trigger. The rule
belongs in `concern-format.md` **and inlined in each producer**
(`plan-challenge.md`, `plan-assumptions.md`, `plan-diagnose-errors.md`,
`impl-challenge.md`). Precedent and enforcement already exist:
`tests/test_concern_parser.py::TestProducerShortRegionRule` discovers producers
by the marker phrase "load-bearing for minimonitor's parser", pins
`KNOWN_PRODUCERS`, and has a sibling `test_producer_set_is_the_known_set` drift
guard — and its docstring states the reason rules are inlined rather than linked:
"these are prompt files read at runtime, and an extra file read is a rule the
agent may skip". A new producer-side rule should plug into that same guard.

**Store shape.** `.aitask-shadow/<task_id>/` mirroring `.aitask-gates/<task_id>/`:
lazy `mkdir -p` by the writer, bare task id (no `t` prefix), git-ignored, never
committed. The gitignore rule installs via the `setup_gate_logs_gitignore`
template in `.aitask-scripts/aitask_setup.sh` (greps `-qxF` for the exact line,
appends with a rationale comment, auto-commits) — see
`aidocs/framework/aitasks_extension_points.md` before touching the install flow.
Note `.gitignore` is **not** regenerated wholesale
(`aitask_regen_gitignore_prerender.sh` does not exist yet; it is a TODO with a
narrow future scope), so the line is added deliberately.

**Content format.** Store the canonical `- [priority | region] body` marker line
so the shadow has the full text to match against, plus when it was rejected and
which producer/mode raised it. The closest existing precedent for "a per-unit
file a coding agent reads back as prompt context" is the AgentCrew per-agent set
(`<name>_work2do.md` / `<name>_status.yaml` in `.aitask-crews/crew-<id>/`):
flat files in a per-unit directory, markdown for prompt content, YAML for
machine state, path handed to the agent. Reuse `Concern` / `needs_addressing`
rather than re-parsing the grammar.

**Concurrency.** There is no `flock` anywhere in this repo (deliberately —
BSD/macOS). `lib/atomic_write.py` / `lib/atomic_write.sh` give readers a
whole-old-or-whole-new view but **explicitly do not serialize read-modify-write**:
two concurrent mutations render from the same snapshot and the second rename
silently discards the first. Appending a rejection *is* a read-modify-write, and
`ait monitor` and `ait minimonitor` can both be open against the same followed
agent — so take `lib/registry_lock.sh` (mkdir-based mutex, owner-token release,
steals only a provably dead PID) around the mutation and land the result through
the atomic-write helper. Do not open-code a `mktemp`-in-`$TMPDIR`-then-`mv`
writer; that is the known-bad pattern `atomic_write.sh` warns about.

**Task-id resolution.** `monitor_core.task_id_from_window_name()` maps
`agent-pick-635_3` → `635_3` and `TaskInfoCache.get_task_id_for_pane()` is the
per-pane accessor — but both are **Python-only; there is no shell counterpart**.
The TUI writer side therefore has the key already (minimonitor's launcher builds
`/aitask-shadow <pane> <task_id>`). For the reader side, prefer either passing
`<task_id>` explicitly (the shadow has it from its launch args / Step 2) or
shimming into the existing Python seam — do **not** add a second regex in bash.
Decide explicitly what happens when the task id is unresolvable (pane-scoped
fallback vs. a clear refusal); a silent no-op is not acceptable.

**Helper script.** No `ait shadow` subcommand exists; shadow helpers are invoked
by path (`./.aitask-scripts/aitask_shadow_capture.sh`). A new
`aitask_shadow_rejected.sh` follows that convention and must be added to the
skill helper-script whitelist (`aitask_skill_verify.sh` / the audit-wrappers
surface).

**Modal dismiss contract.** `ConcernPickerModal` currently dismisses with
`list[Concern] | None` — a contract t1037_4 consumers and
`tests/test_concern_picker_modal.py` depend on. Rejection needs a second output
channel, so return a named result carrying both the forwarded and the rejected
sets rather than overloading the list. `_on_concerns_picked` in **both**
`monitor_app.py` and `minimonitor_app.py` must be updated together, along with
`tests/test_monitor_concern_action.py` and
`tests/test_minimonitor_concern_action.py`.

**Lifetime is an explicit decision, not an inherited one.** Nothing prunes
`.aitask-gates/` — not `aitask_archive*.sh`, not any `ait` subcommand; it grows
monotonically. Decide whether the rejection store is pruned on archive, GC'd
like `.aitask-explain/` (see `aitask_explain_cleanup.sh`, which is the template
including its "only delete under my own root" safety check), or deliberately
left to grow, and state the reasoning in the plan.

## Documentation surface

- `website/content/docs/workflows/shadow-agent.md` (concern block + selective
  forwarding sections)
- `website/content/docs/tuis/minimonitor/how-to.md` ("How to Pick Shadow
  Concerns" + the keybinding table)
- `website/content/docs/tuis/monitor/how-to.md` / `reference.md` (equivalents)
- `aidocs/framework/shadow_agent.md`
- `.claude/skills/aitask-shadow/concern-format.md` (the format's single source of
  truth)

Per CLAUDE.md, make the skill changes in the Claude Code tree first and propose
separate follow-up tasks for the Codex CLI (`.agents/skills/`) and OpenCode
(`.opencode/skills/`) shadow trees.

## Sequencing

**Land after t1293** (`t1293_concern_block_parse_diagnostics`), which is
*currently uncommitted in the working tree* and is actively editing
`ConcernPickerModal` — during this exploration a constant was renamed mid-session
(`_PICKER_XNARROW_COLS` → `_PICKER_NARROW_MIN_WIDTH`). At planning time, re-read
`monitor_shared.py` from HEAD rather than trusting any line numbers recorded
here.

## Coordination — t1159 (shadow review-loop automation)

t1159 already carries this requirement, inherited from folded t1017: per-round
concern triage should route each concern to "address in plan now" vs "spin off
as a separate task" vs **"dismiss"**, so plans do not bloat by absorbing every
secondary concern across rounds. t1159 also already requires the concern block to
carry a **round number**, which is the natural key-space for round-scoped
suppression.

This task builds the **substrate** — the durable rejection store, the
producer-side suppression rule, and the picker action. t1159 consumes it as the
"dismiss" arm of its triage loop and layers automated re-review on top; it must
not re-implement rejection. Whichever lands second re-checks the other's
assumptions about where per-round concern state lives. A reverse pointer is
recorded in t1159.

Relevant sources: `.aitask-scripts/monitor/monitor_shared.py` (`ConcernPickerModal`,
`_ConcernRow`), `.aitask-scripts/monitor/monitor_app.py`,
`.aitask-scripts/monitor/minimonitor_app.py`,
`.aitask-scripts/monitor/concern_parser.py`, `.aitask-scripts/monitor/monitor_core.py`,
`.aitask-scripts/aitask_shadow_capture.sh`, `.aitask-scripts/aitask_shadow_context.sh`,
`.aitask-scripts/lib/registry_lock.sh`, `.aitask-scripts/lib/atomic_write.sh`,
`.aitask-scripts/lib/atomic_write.py`, `.aitask-scripts/aitask_setup.sh`,
`.claude/skills/aitask-shadow/`, `aidocs/framework/shadow_agent.md`,
`aidocs/framework/aitasks_extension_points.md`, `tests/test_concern_parser.py`,
`tests/test_concern_picker_modal.py`.
