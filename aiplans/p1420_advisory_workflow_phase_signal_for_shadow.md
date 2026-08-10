---
Task: t1420_advisory_workflow_phase_signal_for_shadow.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1420 — Advisory workflow-phase signal for the shadow

## Context

Today, to get useful help from the shadow companion the user must read the
followed agent's pane themselves and decide whether to ask for a plan-level
challenge or an implementation review. That judgement is mechanical, and most of
its inputs already exist on disk — they are simply discarded.

This task ships the phase signal that was **deferred** in
`aidocs/framework/shadow_agent.md:467-491`, in the sanctioned shape only: a hint
that changes a *default*, never a check that changes what is *permitted*. A
wrong or unavailable phase must cost the user at most one extra keystroke. The
scar the rule exists for — `impl-challenge`'s removed "too early to review"
gate — is not to be re-created.

**Reference drift found during exploration** (the task body's line numbers are
stale; these are the real ones):

| Task body says | Actual |
|---|---|
| `shadow_agent.md:360-367` (deferred section) | `shadow_agent.md:467-491` |
| `gate_ledger.py:1547` / `:1570` | `:1607` / `:1630` |
| `TaskGateState` `:148`, populated `:1640` | `:137`, populated `:1700` |
| `monitor_core.py:2855-2910` (GateSummaryCache) | `:2905-2960`, discard at `:2955-2956` |
| `get_task_id_for_pane` `:3013-3028`; `_TASK_ID_RE` `:2783` | `:3063-3078`; `:2833` |
| shadow spawn `minimonitor_app.py:1513/1556` | `:1814` / `:1857` |
| board consumes resume_point `:1422/:1431` | `aitask_board.py:1666`, `:1674` |

## Decisions taken at planning time

1. **Followed-agent card** — minimonitor's docked `#mini-own-agent` panel is
   contractually static (t1133/t1322, pinned at `minimonitor_app.py:780`, `:832`,
   `:886`). We **amend** that contract to admit the phase, using the mark-glyph
   per-tick repaint precedent (`_refresh_own_mark`, `:942-966`). Rationale: the
   shadow shadows *that* agent; the general pane list excludes it by
   construction, so list-only display would never show the phase where it
   matters.
2. **Channel to the shadow** — a pane option `@aitask_shadow_phase`, not argv.
   argv freezes at spawn while the skill re-evaluates on **every** refetch; a
   pane option is re-stamped each tick so the value is current. It also avoids
   positional ambiguity (`source_task_id` is omitted when the window name does
   not match `_TASK_ID_RE`, so a third positional would need a placeholder), and
   `aitask_codeagent.sh:425-436` rejects empty/whitespace args anyway.
3. **Scope boundary with t1467 (`depends: [1420]`).** t1420 owns the
   **agent-neutral** phase contract: ledger derivation, `UNKNOWN`, the shared
   task-workflow checkpoint phrases, the pane-option transport, and
   advisory-only behaviour. t1467 owns inventorying the real Codex/OpenCode
   prompt surfaces. Concretely that splits the live half into two tiers (§1): a
   **Tier A** agent-neutral anchor table that ships complete here, and a
   **Tier B** per-agent native map that ships here with the **Claude row only**
   and explicit empty placeholders for `codex` / `opencode`. The Claude rule is
   deliberately narrow and must not read as cross-agent coverage.

   **Tier A's anchor table is agent-neutral; its *currency detection* is not.**
   Both `awaiting_input` and the current-prompt-block index `k` come from
   `prompt_patterns.PROMPT_PATTERNS_BY_AGENT`, whose `opencode` list is empty
   (`prompt_patterns.py:38`). An OpenCode pane therefore establishes neither, and
   the screen tiers correctly suppress to the ledger — safe by construction, but
   it means **live phase detection is unavailable for OpenCode today** even
   though the anchor strings themselves would match. So t1467's scope is *two*
   things, not one: the **currency markers** each agent needs to establish
   "a prompt is live and it is this one", **and** the native Tier B mappings.
   Nothing in the code or docs may imply live Tier A coverage for an agent before
   its markers land — see the per-agent availability statement in §5.
4. **`prompt_patterns.py`** — additive only. One narrow `claude_plan_approval`
   pattern ahead of `claude_proceed` for Claude's native ExitPlanMode dialog;
   `claude_proceed` itself is untouched, so a stale minimonitor (t1116) degrades
   to today's behaviour rather than misreporting.
5. **A missing native pattern must degrade, never guess.** Tier B is keyed on
   `awaiting_input_kind`, so an agent with no native row contributes **nothing**
   and the phase falls through to the ledger (or `UNKNOWN`). Absence-safety is
   therefore a property of the data structure, not of a code path that must
   remember to check — and it is pinned by a negative control (Verification 7).
6. **The phase value never depends on the profile.** `record_gates` only
   *explains* an `UNKNOWN` ("recording off under profile X" vs "nothing recorded
   yet"). Making the value depend on it would add a failure mode for no gain.

---

### Pre-phase (risk mitigations)

Runs **before** section 1. Both steps are read-only/test-only and gate what the
main body assumes.

1. `[verify_prompt_visibility_live]` Stand up an isolated tmux fixture and drive a
   real followed pane to a task-workflow `AskUserQuestion` checkpoint (or, if a
   live run is impractical, replay the exact question text through the same
   `capture-pane -p -e` + `strip_ansi` path the monitor uses). Confirm for each of
   the four `WORKFLOW_PROMPTS` anchors that (a) the text appears in the capture,
   (b) it survives ANSI stripping, and (c) how many lines above the pane bottom it
   sits. **Record the observed distance and set `_WORKFLOW_PROMPT_TAIL_LINES` from
   it** instead of the provisional 40. In the same session, capture Claude Code's
   ExitPlanMode dialog and read off its actual option wording for the
   `claude_plan_approval` regex. **Also capture the same pane immediately after
   the question is answered**, and then capture again with a **tool-permission
   prompt live** — the adversarial sequence that `awaiting_input`-gating alone
   does not catch. Record whether the answered question text is still in the tail
   and whether an intervening prompt marker separates it from the live prompt;
   that measurement decides which of the two currency rules in §1 ships. If an anchor proves
   invisible, drop that row from the table and say so in the Final Implementation
   Notes — the ledger half is unaffected.
2. `[characterize_gate_summary_cache]` Add characterization assertions to
   `tests/test_monitor_gate_summary.py` pinning `GateSummaryCache.summary_for()`'s
   current output for a gated task, an ungated task, an unreadable path, and a
   malformed ledger — **and run them green against unmodified `monitor_core.py`**
   before touching the cache. They then become the guard that section 2's tuple
   change moves nothing.

## 1. New seam — `.aitask-scripts/lib/workflow_phase.py`

Stdlib-only (matches `gate_ledger.py`'s hard rule), importing `gate_ledger` the
same way `lib/gate_orchestrator.py:50` does. Mirrors gate_ledger's conventions:
frozen dataclass returns, a `_from_text` pure twin for every I/O function,
uppercase bare tokens.

```python
PHASES   = ("PLAN", "IMPLEMENT", "POSTIMPL", "UNKNOWN")
LIVENESS = ("WAITING", "RUNNING", "UNKNOWN")
SOURCES  = ("workflow-prompt", "native-prompt", "ledger", "none")

@dataclass(frozen=True)
class PhaseSignal:
    phase: str              # one of PHASES
    waiting: str            # one of LIVENESS
    source: str             # one of SOURCES — what produced `phase`
    consulted: list[str]    # every signal read: ledger, screen, profile
    recording: str          # on | off | unknown  (explains UNKNOWN only)
    detail: str             # one-line human evidence
```

**One canonical vocabulary, enforced in both directions.** `PHASES`, `LIVENESS`
and `SOURCES` are the single source of truth: the dataclass documents itself by
naming them (never by re-listing values in a comment), `format_signal` asserts
each field is a member before emitting, `parse_signal` rejects a non-member by
degrading that field to its unknown value, and the help text / `shadow_agent.md`
render the vocabulary from the same four names. Verification 10 pins the set, so
serialization cannot drift from runtime semantics. `SOURCES` is deliberately
tier-named (`workflow-prompt` / `native-prompt`) rather than a single `screen`:
which tier won is exactly what a surprised user needs to know, and it is the
value t1467's tests will assert against.

`phase` and `waiting` are **separate tri-/quad-states** — "I cannot tell" is its
own value on both axes, never folded into a negative.

### Derivation

### Ledger API boundary (prerequisite — do this first, inside §1)

The seam must not reach into `gate_ledger`'s private helpers; a later ledger
refactor would silently break the phase signal. `archive_status_from_text`
(`gate_ledger.py:1583`) already establishes the public `*_from_text` convention,
and `has_gate_markers` / `derive_gate_runs` are already public — only two things
are missing. Add them to `gate_ledger.py` as **supported API**, each a thin
delegator so every existing internal caller is untouched:

- `resume_point_from_text(text) -> str` — placed beside `archive_status_from_text`
  at `:1583`, delegating to `_resume_point_from_state(derive_gate_runs(text))`.
  (`resume_point(task_file)` at `:1607` becomes its file-reading wrapper, which is
  the module's own text/path pairing convention.)
- `read_active_gates_profile_from_text(text) -> str` — a *named* reader for the
  claim-time profile stamp, delegating to `_read_frontmatter_scalar_from_text`.
  Named rather than exposing the general scalar reader: the seam needs this one
  field, and a general escape hatch would invite exactly the coupling being
  removed.

Both get a docstring line marking them as the cross-module surface consumed by
`lib/workflow_phase.py`, and both are pinned by a compatibility-contract test
(Verification 8) so removing or changing them fails loudly instead of silently.
`lib/workflow_phase.py` then imports **only** public names.

### Derivation

- `phase_from_ledger_text(text) -> (phase, detail)` — pure.
  `not gate_ledger.has_gate_markers(text)` → **`UNKNOWN`**; otherwise
  `gate_ledger.resume_point_from_text(text)`.
  This is the `UNKNOWN`-vs-`PLAN` split the task requires, and it needs no
  profile: an absent ledger is "I cannot tell", full stop. It also *centralises*
  logic the board already hand-rolls at `aitask_board.py:1547-1553` + `:1660`.
The live half is **two tiers**, and the tier split is the t1467 ownership seam.

- **Tier A — `WORKFLOW_PROMPTS` (agent-neutral, ships complete here).**
  `phase_from_screen(screen_text) -> (phase, waiting, detail) | None` — pure,
  matched against a tail slice. These strings are authored by *task-workflow*,
  not by any code agent, so they read identically under Claude Code, Codex CLI
  and OpenCode. That is what makes them the cross-agent baseline:

  | pattern anchor | phase | waiting |
  |---|---|---|
  | `Plan saved to` | PLAN | WAITING |
  | `Implementation complete\. Please review and test the changes` | IMPLEMENT | WAITING |
  | `Proceed with merge of code changes into` | POSTIMPL | WAITING |
  | `has all gates passing and is ready to archive` | POSTIMPL | WAITING |

  This closes blind spot 2: the ledger records a checkpoint only *after* the
  human answers, so it can name the span but never "waiting inside it". Use a
  wider tail than `monitor_core._PROMPT_DETECTION_TAIL_LINES` (6) — provisionally
  `_WORKFLOW_PROMPT_TAIL_LINES = 40`, **sized from the pre-phase measurement**,
  because an `AskUserQuestion` widget pushes its question text well above the
  last six lines.

  **Freshness gate (load-bearing).** `TmuxMonitor._capture_args` is
  `capture-pane -p -e -S -<n>` — it reads *back into scrollback*, so an
  **already-answered** "Plan saved to …" survives in the tail long after the
  agent moved on. Matching it unconditionally would override a correct
  `IMPLEMENT` ledger with a stale `PLAN` + `WAITING` — worse than having no live
  half at all. Therefore:

  1. **Necessary but not sufficient: `awaiting_input is True`.** A pane that is
     not blocked cannot be "waiting inside a phase". `awaiting_input is None`
     ("cannot tell") counts as **not** current — unverifiable is not a licence to
     override. This is the CLI path's default.
  2. **The anchor must belong to the CURRENT prompt block.** `awaiting_input`
     only proves *a* prompt is live, not that the *matched* one is: an answered
     "Plan saved to …" can sit in the tail while a tool-permission dialog is what
     is actually blocking. So compute, over the tail:
     - `k` — index of the last line matching any `prompt_patterns.all_patterns()`
       entry, i.e. the **active** prompt's marker;
     - `a` — index of the last Tier A anchor.

     Tier A fires only when `a < k` **and no other prompt-pattern match lies
     between `a` and `k`**. An intervening prompt marker means the anchor is the
     question text of an earlier, already-answered prompt, and the block that is
     actually current belongs to something else. Same rule for Tier B, whose
     anchor is `k` itself by construction.
  3. **Ambiguity suppresses, never guesses.** If `k` cannot be located, or the
     rule cannot be evaluated, the screen tiers contribute nothing and the ledger
     wins. When suppressed, `detail` says which condition failed
     (`"screen tiers suppressed: anchor precedes an intervening prompt"`) — an
     override that silently did not happen is worse than one that explains itself.

     **Name the no-markers case distinctly.** When the pane's agent has *no*
     prompt patterns at all, `k` is unlocatable for a structural reason, not an
     ambiguous one. Report it as such: omit `screen` from `consulted` and set
     `detail` to `"live tiers unavailable: no prompt markers for agent
     'opencode' (t1467)"`. A user who sees a permanently ledger-only phase then
     learns why and where the fix lives, instead of assuming the feature is
     broken. Expose the predicate as
     `live_tiers_available(agent) -> bool` so the monitor can render the same
     distinction and t1467 has one place to flip.
  4. **The pre-phase validates this rule, and may tighten it.**
     `verify_prompt_visibility_live` must capture the exact adversarial sequence
     — answer a workflow checkpoint, then trigger a tool-permission prompt, then
     capture — and confirm the intervening-marker rule actually suppresses. If
     real captures do not support it, fall back to the construction-safe rule:
     **Tier A matches only inside the same tail slice that produced
     `awaiting_input`**, so the anchor and the evidence of currency are the same
     text and a stale occurrence higher up can never fire. Record which rule
     shipped in the Final Implementation Notes.

- **Tier B — `NATIVE_KIND_PHASE` (per-agent native dialogs).** A map from the
  monitor's existing `awaiting_input_kind` values to `(phase, waiting)`, keyed by
  the same per-agent grouping `prompt_patterns.PROMPT_PATTERNS_BY_AGENT` already
  uses. t1420 ships exactly one row:

  ```python
  NATIVE_KIND_PHASE = {
      "claude": {"claude_plan_approval": ("PLAN", "WAITING")},
      "codex": {},      # owned by t1467 — inventory real surfaces first
      "opencode": {},   # owned by t1467
  }
  ```

  Keying on `awaiting_input_kind` rather than re-matching raw text has three
  consequences worth stating: one regex pass serves both the monitor's
  awaiting-input boolean and the phase; the ordered per-agent structure t1467
  extends already exists; and **a generic confirmation carries no phase by
  construction** — `claude_proceed`, `claude_help_bar` and `codex_yes_proceed`
  are deliberately *absent* keys, so they contribute nothing and the phase falls
  through to the ledger. An agent with an empty map degrades to the ledger-derived
  phase (or `UNKNOWN`); it can never yield a guessed one.

  Tier B needs the classifier's output, so it is available on the **monitor path
  only**. The CLI path can reach Tier A, but only when the caller asserts
  currency via `--awaiting-input yes` (see below); with the default `unknown` it
  reports the ledger phase. Say so in the verb's help text rather than letting
  callers infer it — a CLI caller that cannot observe the pane's input state has
  no business overriding the ledger.
- `recording_from_text(task_text, profiles_dir) -> (state, detail)` — reads
  `active_gates_profile` from the task's own frontmatter (stamped at claim;
  t1420 itself carries `active_gates_profile: fast`) via the **public**
  `gate_ledger.read_active_gates_profile_from_text` added above — not the private
  scalar reader — then `record_gates` from
  `<profiles_dir>/local/<name>.yaml` falling back to `<profiles_dir>/<name>.yaml`
  — the local-over-shared precedence `aitask_run_gates.sh:34-48` establishes.
  Any miss → `unknown`.
- `phase_signal(task_file=None, *, task_text=None, screen_text=None,
  awaiting_input=None, awaiting_input_kind="", agent="", profiles_dir=None)
  -> PhaseSignal` — the composer. **Precedence: `awaiting_input is True` ?
  (Tier A > Tier B) : (nothing) > ledger > none.** Tier A wins over Tier B
  because a workflow checkpoint phrase names the phase directly, whereas a native
  dialog only implies it; both are gated by the freshness condition above.
  `source` records which tier won (`workflow-prompt` | `native-prompt` | `ledger`
  | `none`) so a surprising answer is always explainable. `waiting` comes from the
  winning tier; otherwise from `awaiting_input` (`True`→WAITING, `False`→RUNNING,
  `None`→UNKNOWN) — note a pane can be `WAITING` with an `UNKNOWN` phase, which
  is a legitimate state and must render as such.
- `default_profiles_dir(task_file)` — walks up from the task file to the
  `aitasks/` parent. Derived from the supplied path, never from cwd or env.

### Wire format (one writer, one validated reader)

```
PHASE:IMPLEMENT|WAITING:WAITING|SOURCE:workflow-prompt|CONSULTED:ledger,screen|RECORDING:on|DETAIL:step-8 review prompt is the current prompt block
```

`format_signal(sig) -> str` and `parse_signal(line) -> PhaseSignal`. Because the
format is `|`-delimited, `format_signal` **strips `|` and newlines from `detail`
at the write site** — a delimiter in the payload is undecidable on read.
`parse_signal` is total: any unparseable input yields an all-`UNKNOWN` signal, it
never raises.

### CLI

`python3 .aitask-scripts/lib/workflow_phase.py signal <task_file> [--screen <file>|-] [--awaiting-input yes|no|unknown] [--profiles-dir <dir>]`,
surfaced for shell callers as:

```
./.aitask-scripts/aitask_gate.sh workflow-phase <task-id> [--screen <file>] [--awaiting-input yes|no|unknown] [--profiles-dir <dir>]
```

`--awaiting-input` defaults to `unknown`, which suppresses the screen tiers — so
the plain `workflow-phase <task-id>` form is purely ledger-derived and can never
be poisoned by stale scrollback.

Implemented exactly like `cmd_resume_point` (`aitask_gate.sh:615`): validate arg →
`resolve_task_file` → delegate → `|| echo "<all-UNKNOWN line>"` degrade. It needs
a second delegator (`delegate_python_phase`) because `delegate_python` is
hardwired to `$GATE_LEDGER_PY`. Register in **all four** places a verb lives:
the header comment block (`:16-44`, incl. the python-only exceptions list),
`show_help()` (`:1158`), the `main()` case (`:1321`), and `workflow_phase.py`'s
module docstring. This is a **stdout-token verb** like `resume-point`, not one of
`gate-cli.md`'s exit-code decision verbs — say so in the help text.

## 2. Monitor / minimonitor wiring

`monitor_core.GateSummaryCache` (`:2905-2960`) currently computes
`read_task_gate_state()` and throws everything but the summary string away
(`:2955-2956`). Extend its stored value rather than adding a second parse of the
same file (the t1323 coordination note):

- cache value becomes `(identity, summary, ledger_phase, recording)`;
- `summary_for()` keeps its exact signature and behaviour (existing call sites at
  `monitor_app.py:1577` and `minimonitor_app.py:835` are untouched);
- new `ledger_phase_for(info) -> (phase, detail)`.

Only the **file-derived** half is cached — its key is file identity, whereas the
live half changes every tick. The live half is composed at call time via
`workflow_phase.compose(ledger_half, screen_text=snap.content,
awaiting_input=snap.awaiting_input, recording=…)`.

Display (keep it narrow — minimonitor rows are tight):
`phase: IMPLEMENT ⏸` / `phase: PLAN` / `phase: unknown (recording off)`.

- **Full monitor** — `monitor_app._format_agent_card_text:1569-1581`, appended to
  the status row beside `gates:`.
- **Minimonitor general rows** — `minimonitor_app._agent_card_text:823-838`, its
  own line beside `gates:`.
- **Minimonitor docked followed panel** — `_own_card_text` (`:909-940`) grows a
  phase line; `_refresh_own_mark` (`:942-966`) becomes
  `_refresh_own_live_state`, repainting mark **and** phase per tick via
  `Static.update`. Amend the three static-contract comments (`:780-782`,
  `:832-834`, `:886-889`) to read "static except the mark glyph and the phase
  line" and cite t1420.

`prompt_patterns.py`: add `PromptPattern("claude_plan_approval", …)` **first** in
the `claude` list (first-match-wins in `classify_content:198-202`), matching the
ExitPlanMode dialog's distinctive option wording. **Verify the exact wording
against a live pane before hardcoding it** — use the isolated tmux fixture recipe
rather than guessing. This is the *only* native pattern t1420 adds; the `codex`
and `opencode` lists are left exactly as they are. Record that boundary in the
file's docstring as a forward pointer — "workflow-*phase* mapping lives in
`lib/workflow_phase.NATIVE_KIND_PHASE`; Codex/OpenCode native surfaces are
inventoried and added by t1467" — so the next reader does not mistake the single
Claude row for cross-agent coverage. (The pointer goes in the module docstring,
never into t1467's task file.) `awaiting_input_kind` reaches the applink wire
(`applink/pusher.py:420-421`); a new value there is additive and needs no schema
change.

Wire `snap.awaiting_input_kind` and the pane's agent through to the composer —
today it is computed every tick (`monitor_core.py:1920-1921`) and consumed by
nothing but applink.

## 3. Shadow spawn channel

- `monitor_core.py:283-290` — add `SHADOW_PHASE_OPTION = "@aitask_shadow_phase"`.
- `monitor_core.spawn_shadow:2798-2813` — after the `@aitask_shadow_target` stamp,
  stamp the phase. **Best-effort and explicitly non-fatal**, in deliberate
  contrast to the target stamp (which kills the pane on failure): an unstamped
  phase must never cost the user a shadow. Document the asymmetry inline.
- **Re-stamping must be shared, not minimonitor-only.** The full monitor spawns
  shadows too (`monitor_app.py:499-500` bindings, `action_launch_shadow:2737`,
  `_spawn_shadow:2833` → the same `monitor_core.spawn_shadow`), so a
  minimonitor-only refresh would leave every full-monitor shadow frozen at its
  launch-time value — which is precisely the argv failure mode the pane option
  was chosen to avoid. Add a shared
  `monitor_core.refresh_shadow_phase_stamp(monitor, shadow_pane, signal)`
  alongside `compute_shadow_staleness` (`monitor_core.py:498`) — same
  "comparison/mutation shared in `monitor_core`, display owned by the caller"
  split that module already uses — and call it from **every** site that already
  resolves a bound shadow pane per tick: `minimonitor_app:2096`
  (`_update_shadow_freshness`) and `monitor_app:1134` and `:2942`. Best-effort
  like the spawn stamp: a failed re-stamp leaves the previous value and never
  raises into the refresh loop.
- `aitask_shadow_capture.sh` — new `--phase [<task_id>]` mode printing **one line
  to stdout and nothing else**, always exit 0, never refusing (deliberately
  unlike the capture path's `die_code 2`). Resolution ladder, terminating:
  1. `@aitask_shadow_phase` on our own pane (same single `display-message`
     round-trip idiom as `shadow_self_target:202-227`) → emit, `VIA:pane-option`;
  2. else, with a `<task_id>`, delegate to `aitask_gate.sh workflow-phase`
     (ledger half only) → `VIA:ledger-cli`;
  3. else all-`UNKNOWN`, `VIA:none`.

## 4. Shadow skill — `.claude/skills/aitask-shadow/SKILL.md.j2`

All additions are Jinja-free (the phase is runtime data, not profile config), so
`SKILL.md.j2` keeps its single `{{ profile.name }}` and Test 1b agent-invariance
is unaffected.

- **Step 1**, extending the proactive-offer block (`:138-149`): run
  `aitask_shadow_capture.sh --phase` alongside each capture and let the offer
  cite the phase. Keep every existing non-gating word; add explicitly that an
  `UNKNOWN` or a *wrong* phase changes nothing about what may be asked.
- **Step 3**, a short "Phase-driven default" note above the dispatch list —
  the ladder **explicit user wording > detected phase > ask**, mirroring
  `impl-challenge.md:181-184`, with the same announce-what-you-resolved
  obligation as `:204-212` (name the phase, its evidence, and how to override).
  Mapping: `PLAN` → `plan-challenge.md`; `IMPLEMENT`/`POSTIMPL` →
  `impl-challenge.md`; `UNKNOWN` → ask, which is today's behaviour.
- A hard clause, phrased so the guard test can assert it: *the phase never
  removes a capability; every capability below is available at every phase,
  including one you believe is wrong.*

Regenerate the three entry-point goldens
(`tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md`) via
the loop in `skill_authoring_conventions.md:484-497`; `impl-challenge`'s
procedure goldens are unchanged. Run `./.aitask-scripts/aitask_skill_verify.sh`.
The `.agents/` and `.opencode/` renders come from the same closure — rerender
per profile (one call per profile).

## 5. Docs

- `aidocs/framework/shadow_agent.md` — retitle `## Phase detection (deferred)`
  (`:467`) to **`## Phase detection (advisory)`**, describe the shipped signal
  (seam, CLI verb, pane option, ladder, `UNKNOWN` semantics), and restate the
  anti-gating rule as a **live, testable** constraint naming the guard test. Keep
  the t1311 paragraph verbatim as the scar. Fix the forward reference at `:29-30`.
  Add `@aitask_shadow_phase` to the spawn-path and Configuration sections. State
  the two-tier split and its ownership explicitly, with a **per-agent
  availability table** so no reader infers coverage that does not exist:

  | agent | ledger half | Tier A (live) | Tier B (native) |
  |---|---|---|---|
  | Claude Code | yes | yes | yes (`claude_plan_approval`) |
  | Codex CLI | yes | markers exist; anchors unverified — t1467 | no — t1467 |
  | OpenCode | yes | **no prompt markers at all** — t1467 | no — t1467 |

  and the rule that binds it: Tier A's anchor strings are agent-neutral, but
  establishing that a prompt is *current* needs per-agent markers, so an agent
  without them degrades to the ledger-derived phase or `UNKNOWN` — never to a
  guess. Keep this table adjacent to the anti-gating rule so both are read
  together.
- `aidocs/gates/ledger-driven-reentry.md` — a short note that the phase signal
  reuses the new public `resume_point_from_text` but adds `UNKNOWN` plus a live half, and does
  **not** redefine the three-state re-entry contract (`:50-53`).
- `monitor/prompt_patterns.py` — the bidirectional pointer described in §2.
- `aitasks/t1420_…md` — add a `t1467` bullet to its own **Coordination** section
  (the reverse of t1467's `depends: [1420]`), naming the tier boundary. Edit only
  t1420's file; t1467's task file is not ours to touch.

### Post-phase (risk mitigations)

Runs **after** section 5, before the verification sweep.

1. `[prove_followed_panel_repaint]` Prove the docked followed-agent panel's phase
   line is **live, not frozen at build**: in a real tmux session, observe the
   panel, change the underlying phase (append a `plan_approved pass` run to the
   task's ledger, or put a matching workflow prompt on the followed pane), and
   confirm the panel text changes **within one refresh cycle** — captured from the
   pane, not read off the text-builder's return value. A unit test of
   `_own_card_text` cannot distinguish a correct builder wired to a
   never-re-invoked repaint path from a correct one; only the live capture can.
   If the panel does not repaint, the defect is the wiring in
   `_refresh_own_live_state`, not the builder.

## Verification

Run `bash tests/run_all_python_tests.sh` (read the last line only) plus each new
bash test individually, and `shellcheck .aitask-scripts/aitask_*.sh`.

1. **`tests/test_workflow_phase.py`** (new, unit) — the `UNKNOWN`-vs-`PLAN` split
   at its weakest surface: a task with **no `## Gate Runs` section under a
   non-`record_gates` profile must not report `PLAN`** (and the same under
   `fast`, proving the value is profile-independent while `recording` differs);
   every ledger state; a Tier A match overriding the ledger with
   `source=workflow-prompt`; `awaiting_input` tri-state; `format_signal` /
   `parse_signal` round-trip; a `detail` containing `|` and a newline is sanitised
   at the write site; a garbage line parses to all-`UNKNOWN` without raising.

   **Plus the stale-checkpoint cases** (the freshness gate):
   (a) screen text containing an **answered** `Plan saved to …` with
   `awaiting_input=False`, over a ledger recording `plan_approved pass` → must
   report `IMPLEMENT` / `source=ledger`, **not** `PLAN`/`WAITING`;
   (b) the same text with `awaiting_input=None` → same result (unverifiable is
   not a licence to override);
   (c) the same text with `awaiting_input=True` → `PLAN` / `WAITING` /
   `source=workflow-prompt` (the positive control — without it, (a) and (b) would
   also pass against a build that simply never consults the screen);
   (d) a tail containing **both** `Plan saved to …` and, later,
   `Implementation complete. …` with `awaiting_input=True` → `IMPLEMENT`
   (last-anchor-wins, not first);
   (e) **the current-prompt-block negative control**: a stale `Plan saved to …`
   anchor, followed by an intervening prompt marker (the answered widget's
   `claude_help_bar`), followed by a live tool-permission `claude_proceed` at the
   bottom, with `awaiting_input=True` and
   `awaiting_input_kind="claude_proceed"` — over a ledger recording
   `plan_approved pass`. Must report `IMPLEMENT` / `source=ledger`, **not**
   `PLAN`/`WAITING`. This is the case `awaiting_input`-gating alone does not
   catch, so it must fail against a build with only rule (1) — assert that
   explicitly by running it against a rule-(1)-only variant first.
2. **`tests/test_gate_workflow_phase.sh`** (new) — the CLI verb, following
   `test_gate_reentry.sh`'s conventions: bash↔python parity on the same fixtures,
   child-id (`<parent>_<child>`) resolution, a malformed ledger still exits 0, and
   the degrade line pinned by static source grep.
3. **`tests/test_shadow_phase_advisory.sh`** (new) — **the discriminating
   negative control.** For each phase value, including a deliberately *wrong* one
   stamped on the pane: `--phase` exits 0 and emits one parseable line; capture
   still succeeds with a garbage stamp; and a structural sweep over every
   rendered shadow closure asserts all Step-3 capability bullets are present and
   no phase-conditioned refusal exists. **Positive control first**: the sweep must
   FAIL against a fixture with an injected phase-gate, otherwise a green sweep
   proves nothing.
4. **`tests/test_workflow_phase_prompt_drift.sh`** (new) — two drift guards, both
   asserting a **hit count**, never a silent zero-match:
   (a) each Tier A literal anchor still exists in the canonical source
   `.claude/skills/task-workflow/{SKILL.md,planning.md}` (canonical site + drift
   guard, since `WORKFLOW_PROMPTS` necessarily duplicates it);
   (b) every key of `NATIVE_KIND_PHASE` exists as a `PromptPattern.name` in
   `prompt_patterns.PROMPT_PATTERNS_BY_AGENT` under the same agent — so a rename
   there fails loudly instead of silently emptying a native row. This guard is
   the one t1467 inherits when it fills in the Codex/OpenCode rows.
5. **`tests/test_monitor_gate_summary.py` / `test_monitor_gate_cache.py`** —
   extend for the new cache tuple; assert `summary_for()` is byte-identical to
   today for gated, ungated, and unreadable task files.
6. **Missing-native-pattern degradation** (in `test_workflow_phase.py`) — the
   negative control the t1467 split requires. Three cases, each asserting the
   composed `phase` equals the **pure ledger phase** and `source` is `ledger` (or
   `none`), never a guess:
   (a) `agent="codex"` with `awaiting_input_kind="codex_yes_proceed"` — a generic
   confirmation, and a native map that is empty by design;
   (b) `agent="claude"` with `awaiting_input_kind="claude_proceed"` — the
   deliberately-absent generic key, proving `claude_plan_approval` did not widen
   into its ambiguous neighbour;
   (c) `agent="opencode"` with an arbitrary unknown kind **and screen text
   containing a live Tier A anchor** — the structural case: no prompt markers
   exist for that agent, so neither `awaiting_input` nor `k` can be established
   and the anchor must not fire. Additionally assert `live_tiers_available
   ("opencode") is False`, that `consulted` omits `screen`, and that `detail`
   names t1467 — the availability statement must be machine-checked, not just
   documented.
   Each case is run once with an empty ledger (expect `UNKNOWN`, **not** `PLAN`)
   and once with `plan_approved pass` (expect `IMPLEMENT`) — so a stub that
   always answered `UNKNOWN` would fail too. Positive control: the same harness
   with `awaiting_input_kind="claude_plan_approval"` and `agent="claude"` **must**
   yield `source=native-prompt`, otherwise the three negatives prove nothing.
7. **Shared re-stamp coverage** (new, in `tests/test_monitor_shadow_status.py` or
   a sibling) — assert `refresh_shadow_phase_stamp` is invoked from **both**
   apps, not just minimonitor: drive each app's shadow-freshness path against a
   fake `monitor` (duck-typed on `tmux_run`, as `monitor_core.py:2706-2708`
   already allows) and assert a `set-option -p … @aitask_shadow_phase` call is
   recorded. A source-level grep for the call sites is the cheap backstop, but the
   behavioural assertion is what catches a site that imports the helper and never
   reaches it. Also assert a failing `tmux_run` does not raise into the refresh
   loop.
8. **`tests/test_gate_ledger_public_api.py`** (new) — the compatibility contract
   between `gate_ledger` and `workflow_phase`. Assert `resume_point_from_text`,
   `read_active_gates_profile_from_text`, `has_gate_markers` and
   `derive_gate_runs` exist as public module attributes and behave as documented
   on fixtures, and that `workflow_phase` imports **no** underscore-prefixed name
   from `gate_ledger` (an AST/source check over its import statements and
   attribute accesses). A later ledger refactor then fails here rather than
   silently degrading the phase signal.
9. **Vocabulary contract** (in `test_workflow_phase.py`) — `PHASES`, `LIVENESS`
   and `SOURCES` are pinned by value; every `PhaseSignal` the composer can
   produce across the fixture matrix has all three fields inside their sets;
   `format_signal` refuses a non-member; `parse_signal` degrades a non-member to
   the unknown value rather than propagating it; and a round-trip over every
   member of `SOURCES` is exact. Grep the help text and `shadow_agent.md` for
   any source token not in `SOURCES` (hit count asserted) so docs cannot drift
   from the constant.
10. **Live acceptance** (manual-verification candidate): in a real tmux session,
   confirm the minimonitor followed-agent panel shows the phase and **repaints**
   when the followed agent moves from the plan checkpoint to the Step-8 review
   prompt; that a shadow spawned with `e` from **both** the full monitor and
   minimonitor reads a value that updates after the followed agent advances; and
   that after answering a checkpoint the phase follows the ledger rather than the
   answered prompt still visible in scrollback.

## Risk

Levels below are the **post-inline reassessment** — they describe the plan as
augmented with the pre-/post-phase blocks, which is the plan being approved.

### Code-health risk: medium
- `GateSummaryCache` (`monitor_core.py:2905`) is shared by both monitor TUIs; changing its cached tuple risks moving `summary_for()`'s existing output. · severity: low (residual — pinned by inline pre-phase `characterize_gate_summary_cache`, which must be green against unmodified source first) · → mitigation: inline pre-phase characterize_gate_summary_cache
- Amending minimonitor's deliberately-static followed-agent panel adds a per-tick repaint path — the classic place a "live" value silently freezes at build time. · severity: low (residual — the failure mode is caught only by the live capture in inline post-phase `prove_followed_panel_repaint`) · → mitigation: inline post-phase prove_followed_panel_repaint
- Inserting `claude_plan_approval` ahead of `claude_proceed` changes `awaiting_input_kind` for panes that previously reported the generic value; that field is already on the applink wire (`pusher.py:420-421`). · severity: low · → mitigation: none (additive value; no schema change — noted in §2)
- `WORKFLOW_PROMPTS` duplicates prompt strings authored in `.claude/skills/task-workflow/{SKILL.md,planning.md}` — a rewording there silently kills the live half. · severity: medium · → mitigation: none (the drift-guard test, Verification item 4, is the standing guard)
- The stamp added to `spawn_shadow` sits beside a stamp whose failure kills the pane; getting the fatal/non-fatal asymmetry wrong would make an advisory hint able to destroy a shadow. · severity: low · → mitigation: none (asymmetry documented inline at the call site, §3)
- Tier B couples `lib/workflow_phase.py` to the monitor's `awaiting_input_kind` vocabulary; renaming a pattern in `prompt_patterns.py` would silently empty a native row. · severity: low · → mitigation: none (the same drift-guard test asserts every `NATIVE_KIND_PHASE` key exists as a `PromptPattern.name`, so a rename fails loudly)
- `capture-pane -S -<n>` reads scrollback, so an **answered** checkpoint prompt persists in the tail and would let a stale Tier A match override a correct ledger phase — including while an unrelated prompt makes `awaiting_input` true. · severity: low (residual — current-prompt-block rule + `awaiting_input` gate + suppress-on-ambiguity, pinned by Verification 1(a)-(e) with (e) required to fail against a gate-only build; the pre-phase validates the rule against real captures and may tighten it) · → mitigation: inline pre-phase verify_prompt_visibility_live
- Three names for the same field (`screen` in the dataclass comment, `SOURCE:screen` on the wire, tier names in the composer) would let serialization drift from runtime semantics. · severity: low (residual — one `SOURCES` constant validated by both formatter and parser, pinned by Verification 9) · → mitigation: none (design change, §1 "One canonical vocabulary")
- The phase pane option would freeze at launch for shadows spawned from the **full** monitor if re-stamping lived only in minimonitor — the exact staleness the pane-option channel was chosen over argv to avoid. · severity: low (residual — shared `refresh_shadow_phase_stamp` called from all three per-tick sites; pinned behaviourally by Verification 7) · → mitigation: none (design change, §3)
- Depending on `gate_ledger`'s private helpers would let an internal ledger refactor silently break the public phase signal. · severity: low (residual — two promoted public functions plus the no-private-imports contract test, Verification 8) · → mitigation: none (design change, §1 "Ledger API boundary")
- The Claude-only Tier B row could be misread as cross-agent coverage, causing t1467 to be scoped away or a Codex pane to be trusted for phase. · severity: low · → mitigation: none (explicit empty placeholders + the forward pointer in the module docstring + the degradation negative control, Verification 6)
- Tier A's anchors are agent-neutral but its currency detection is not, so "Tier A ships complete" could be read as live cross-agent coverage when OpenCode has no prompt markers at all and is permanently ledger-only until t1467. · severity: low (residual — `live_tiers_available()` predicate, the per-agent availability table in `shadow_agent.md`, the t1467-naming `detail`, and the machine-checked assertion in Verification 6(c)) · → mitigation: none (design change, §Decisions 3 and §5)

Residual driver: the blast radius is unchanged — ~8 files across four subsystems
plus a contract amendment — so this stays `medium` even with both riskiest edits
guarded.

### Goal-achievement risk: low
- The whole live half assumes task-workflow's `AskUserQuestion` text is actually present in a `capture-pane` of the followed agent and survives `strip_ansi` within the tail window. If it is not, the feature degrades to the ledger half only — which is permanently `UNKNOWN` under non-`record_gates` profiles. · severity: low (residual — inline pre-phase `verify_prompt_visibility_live` settles the assumption before any dependent code is written, and a negative result costs one precedence rung, not the feature) · → mitigation: inline pre-phase verify_prompt_visibility_live
- Claude Code's ExitPlanMode dialog wording for `claude_plan_approval` is assumed, not observed. · severity: low (residual — observed in the same pre-phase session; and a wrong regex just leaves the Tier B row inert, which is the same state Codex/OpenCode ship in) · → mitigation: inline pre-phase verify_prompt_visibility_live
- Re-stamping `@aitask_shadow_phase` from `_update_shadow_freshness` (every *other* tick) is assumed to reach the shadow pane reliably; if it does not, the hint freezes at spawn and the pane-option channel loses its advantage over argv. · severity: low · → mitigation: none (worst case equals the argv alternative that was rejected — no capability is lost)

### Planned mitigations
- timing: pre-phase | name: verify_prompt_visibility_live | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — capture visibility of workflow prompt text and ExitPlanMode dialog wording; code-health — which of the two current-prompt-block rules is sound | desc: Observe a live pane through the monitor's own capture+strip path across three states (prompt live, prompt answered, unrelated prompt live), size the tail window from the measurement, decide the currency rule, and read off the real ExitPlanMode option wording before hardcoding any of it.
- timing: pre-phase | name: characterize_gate_summary_cache | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — GateSummaryCache tuple change moving existing summary output | desc: Pin summary_for() for gated/ungated/unreadable/malformed inputs and run it green against unmodified monitor_core.py before extending the cache.
- timing: post-phase | name: prove_followed_panel_repaint | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a live phase line frozen at panel build time | desc: Change the underlying phase in a real tmux session and confirm the docked followed-agent panel repaints within one refresh cycle, captured from the pane rather than from the builder's return value.
