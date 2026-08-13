---
Task: t1467_cross_agent_phase_prompt_detection.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1467 — Cross-agent phase prompt detection

## Context

t1420 shipped the advisory workflow-phase signal with a deliberate seam: the
**agent-neutral** half is complete (Tier A's checkpoint anchors, the ledger
derivation, `UNKNOWN`, the pane-option transport, advisory-only behaviour), but
the **per-agent** half ships with the Claude row only. `QUESTION_WIDGET_KINDS`
and `NATIVE_KIND_PHASE` (`lib/workflow_phase.py:122-132`) carry literal
`# t1467` placeholders for `codex` and `opencode`, so
`live_tiers_available("codex") is False` and both agents are **permanently
ledger-only** — which under a non-`record_gates` profile means permanently
`UNKNOWN`.

The gap is *not* the anchor text. Confirmed during exploration: the three Tier A
question strings are **byte-identical across all 11 rendered task-workflow
trees** (`.claude/`, `.agents/…-codex-`, `.opencode/…`), because the framework —
not the agent — authors them. What is missing is the **currency evidence**: the
per-agent markers that establish "a prompt is live, and it is *this* one".
t1420's Final Implementation Notes state the boundary explicitly: t1467 owns
*two* things, the currency markers **and** the native Tier B mappings.

Intended outcome: Codex and OpenCode get phase-aware detection comparable to
Claude where the measurement supports it, degrade honestly to the ledger where
it does not, and the phase remains advisory-only throughout.

## Decisions taken at planning time

1. **Inventory is hybrid — static enumeration, then live measurement.** Both
   CLIs are installed and readable: `codex` 0.146.0 ships a native Rust binary
   (`@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex`) whose
   string table is greppable, and `opencode` 1.18.18 ships a 176 MB binary
   embedding a **full i18n JSON bundle** (verified: `settings.permissions.action.allow`
   exists in ~15 languages). Static extraction enumerates *candidates*; only a
   live capture through the monitor's own path (`capture-pane -p -e -S -<n>` +
   `ansi_utils.strip_ansi`) establishes **geometry** — where the marker sits
   relative to the pane bottom, whether it survives stripping, and whether a
   structural block boundary exists. t1420's pre-phase is the precedent, and its
   result (the planned distance heuristic was *wrong*; only a structural chip
   worked) is the reason measurement precedes code here too.

2. **OpenCode's prompt text is localized — anchors must be locale-invariant
   where possible.** This is a class of fragility Claude and Codex do not have.
   Prefer glyphs, key-binding hints (`(y)`, `esc`), and structural geometry over
   translated words; where an English word is unavoidable, say so and accept
   that a non-English locale degrades to ledger-only. Degradation is the
   designed-in outcome, not a defect — but it must be **measured and asserted**,
   not assumed.

3. **Prompt matching becomes per-agent.** Today `classify_content`
   (`monitor_core.py:190-219`) applies the flat `all_patterns()` list to every
   AGENT pane; the module docstring admits it (`prompt_patterns.py:3-5`) and
   `tests/test_prompt_detection.py:85` even asserts a *codex* kind on a pane
   whose `current_command` is `claude`. Adding several codex/opencode patterns
   would widen that cross-fire, and `awaiting_input_kind` is not inert: it drives
   the awaiting/idle badges, `_rebuild_pane_list` ordering
   (`monitor_app.py:1368-1380`), the applink wire (`pusher.py:420-421`), and the
   review-loop work latch (`review_loop.classify_followed_change:483-484`).
   Scoping is therefore a **prerequisite** of this task, not an optional
   cleanup. The task body permits it: *"do not alter existing
   `awaiting_input_kind` semantics unless compatibility impact is documented and
   tested"* — so it ships with a characterization test taken **before** the
   change plus an explicit compatibility note.

4. **Fail-open, never fail-closed, on an unrecognized command.** A pane whose
   `current_command` is a wrapper (`node`, `bash`, a shim) resolves to `""` and
   keeps today's flat-list behaviour. Scoping removes only patterns that
   *provably belong to another agent*; unknown names (a caller's custom pattern,
   a test's) survive. `prompt_patterns=[]` must still disable detection
   entirely — the filter operates on the **supplied list**, never on the module
   dict.

5. **One canonical command→agent mapper.** `workflow_phase.agent_key_from_command`
   (`:135-145`) keys off `QUESTION_WIDGET_KINDS`; classification needs the same
   mapping keyed off `PROMPT_PATTERNS_BY_AGENT`. Two mappers would drift the
   moment an agent is added to one table only. The mapper moves to
   `prompt_patterns.py` (the lower layer — `workflow_phase` already imports
   nothing from `monitor/`, so the dependency direction is checked in step 3)
   and `workflow_phase.agent_key_from_command` becomes a delegating alias,
   keeping its public name and behaviour.

6. **The review loop does NOT unlock as a side effect.** `live_tiers_available`
   currently doubles as minimonitor's arming gate for the auto-recheck loop
   (`minimonitor_app.py:2438-2444`). That loop **injects text into the shadow
   pane** — it is not advisory, so it must not inherit a newly-measured marker
   automatically. A separate predicate `review_loop_agent_supported(agent)` (one
   named constant, `REVIEW_LOOP_AGENTS = ("claude",)`) becomes the arming gate;
   `live_tiers_available` keeps its own meaning. The minimonitor refusal message
   must also stop citing t1467, which will no longer be the reason.

7. **A missing measurement drops a rung, never the feature.** If neither CLI
   renders a stable block boundary, Tier A stays unavailable for it and only
   Tier B ships; if neither renders a phase-bearing native dialog, Tier B stays
   empty and the ledger half is all there is. Both outcomes are recorded in the
   availability table and asserted by a negative control — the same absence-safety
   property t1420 built into the data structure.

---

### Pre-phase (risk mitigations)

Runs **before** section 1. Both are measurement/test-only and gate what the main
body may assume.

1. `[inventory_prompt_surfaces_live]` Inventory Codex CLI 0.146.0 and OpenCode
   1.18.18 in two passes, and **write the findings into this plan before any
   pattern is authored**.

   *Static pass (no API cost).* Extract candidate strings:
   `strings -n 6 <codex-binary>` filtered for confirmation/selection wording, and
   for OpenCode the embedded i18n bundle — pull the **English** values for the
   permission/dialog key families (`settings.permissions.action.*`,
   `dialog.*`, `permission.*`) and, critically, **the same keys in ≥2 other
   locales**, so the localization blast radius is measured rather than guessed.

   *Live pass.* In an **isolated tmux fixture** (`lib/tmux_exec.sh` gateway,
   never raw `tmux`; own socket, `TMUX` scrubbed — see
   `aidocs/framework/tmux_gateway.md` and the live-fixture gotchas), run each CLI
   in a throwaway scratch repo and drive it to each state below, capturing the
   pane through the monitor's exact path (`capture-pane -p -e -S -<n>` piped
   through `ansi_utils.strip_ansi`):

   | state | what to record |
   |---|---|
   | tool/command approval dialog | matching line, distance above bottom, whether it lands inside `_PROMPT_DETECTION_TAIL_LINES` (6) |
   | a task-workflow checkpoint question (the agent asked; it is waiting) | does *any* stable marker exist? distance of the Tier A anchor above the bottom |
   | the same question **after** it is answered | does the anchor survive in scrollback, and does the marker survive with it? |
   | idle at the input box, nothing pending | must NOT match anything — the negative control |
   | a plan-approval / review-shaped native dialog, if one exists | wording, distance, distinctness from the generic confirmation |

   For each candidate marker record: (a) the exact line, (b) its distance above
   the pane bottom, (c) whether it survives `strip_ansi`, (d) whether it is
   **disjoint** from every existing pattern in `PROMPT_PATTERNS_BY_AGENT` (cross-check
   against all of them, as t1420 did), and (e) whether a **structural block
   boundary** exists — a line that appears exactly once, only while the prompt
   is live, and always *above* the anchor. (e) is the decision point: it is what
   `current_question_block` needs, and without it Tier A cannot ship for that
   agent.

   If a CLI cannot be driven (no auth, quota, sandbox refusal), record that
   verbatim, ship only what the static pass supports, and mark that agent's Tier
   A row `no` in the availability table. **Do not infer geometry from the
   binary.**

2. `[characterize_classify_content]` Add characterization assertions to
   `tests/test_prompt_detection.py` pinning **today's** `classify_content`
   behaviour at the seam section 1 changes — for each existing pattern name, the
   `(awaiting_input, awaiting_input_kind)` produced on a pane with
   `current_command` set to each of `claude` / `codex` / `opencode` / `node` /
   `""`, plus the `prompt_patterns=[]` disable path and the OTHER/TUI category
   gate. **Run them green against unmodified `monitor_core.py` first** — a
   characterization test written after the change pins the change, not the
   contract. They then become the guard that the per-agent scoping moves exactly
   what it intends and nothing else. (Two of these will legitimately flip in
   section 1; the flip table is authored **here**, before the change, and each
   flip is justified in the same commit.)

## 1. Per-agent prompt scoping — `monitor/prompt_patterns.py` + `monitor/monitor_core.py`

**`prompt_patterns.py`** gains two pure helpers and keeps `all_patterns()`
untouched (five call sites depend on it):

```python
def agent_key_from_command(current_command: str) -> str:
    """Canonical pane-command → per-agent table key, or "" when unrecognised.

    THE one mapper: `workflow_phase.agent_key_from_command` delegates here, so a
    new agent cannot land in one table's key set and not the other. Exact
    basename match — a pane running `claude-something-else` is not Claude Code.
    `"all"` is a pattern group, never an agent, and is excluded.
    """


def scope_patterns(patterns: list[PromptPattern],
                   agent: str) -> list[PromptPattern]:
    """`patterns` minus every pattern that provably belongs to a DIFFERENT agent.

    Subtractive, not selective, and that is load-bearing three times over:
      * an unrecognised `agent` ("" — a wrapper process) removes nothing, so
        today's flat-list behaviour is the fail-open default;
      * a caller-supplied pattern whose name is in no registry group survives;
      * `patterns=[]` stays empty, so the explicit disable path is unaffected.
    Order is preserved — first-match-wins semantics are unchanged.
    """
```

**`monitor_core.py`**: `classify_content` (`:190`) and `_classify_one` (`:222`)
take a new keyword-only `agent: str = ""`; the default preserves today's
behaviour for any caller that does not pass it. Inside `classify_content`, the
scan iterates `scope_patterns(prompt_patterns, agent)` instead of
`prompt_patterns`. The five call sites all have `pane` in scope and pass
`agent=prompt_patterns_mod.agent_key_from_command(pane.current_command)`:

- `:2167` `_finalize_capture` (sync)
- `:2259` shadow capture (`_classify_one` via lambda)
- `:2341` async single
- `:2391` off-loop single
- `:2525` `_classify_batch` — the helper resolves the key per pane inside the
  comprehension (`:249`), since it already receives the whole `pane`

Document the compatibility change **in the function docstring**, not only in the
plan: *"Scoped to the pane's own agent since t1467; an unrecognised
`current_command` falls back to the full list."*

## 2. Native prompt patterns for Codex and OpenCode — `monitor/prompt_patterns.py`

Additive rows authored **from the pre-phase measurement**, never from the binary
strings alone. Shape rules, inherited from `claude_trust_folder`'s hard-won
geometry lessons (t1474) and applied here:

- anchor on the **bottom-most** stable line of the widget, because matching sees
  only `_PROMPT_DETECTION_TAIL_LINES` (6) lines;
- prefer structural geometry (a marker glyph, an option line holding nothing but
  its label, adjacency) over a quotable phrase — a phrase eventually fires on a
  pane displaying prose *about* the dialog;
- for OpenCode, prefer locale-invariant fragments; where impossible, name the
  locale assumption in the comment and pin the degradation with a test;
- each new pattern carries a comment recording **what it was measured against**
  (CLI version, pane geometry, date) — the convention the existing Claude rows
  already follow.

Ordering within a row is first-match-wins: the **specific** widget before the
generic confirmation, exactly as `claude_askuserquestion` precedes
`claude_help_bar`. `codex_yes_proceed` stays untouched and stays last in its row.

Update the module docstring: `all_patterns()` is no longer "applied to every
AGENT pane" — replace that sentence with the scoping rule and a pointer to
`scope_patterns`. Keep the `workflow_phase` forward pointer, rewritten from
"added by t1467" to a statement of what is now wired.

## 3. Per-agent question-block boundary — `lib/workflow_phase.py`

`current_question_block` (`:304-324`) is Claude-specific: `_QUESTION_HEADER_RE`
matches the `☐ <Header>` chip an `AskUserQuestion` renders. Codex and OpenCode
have no such widget. Generalize with **one table, keyed by agent**, mirroring the
`NATIVE_DIALOG_BOUNDARIES` precedent that already exists one layer up
(`review_loop.py:420-424`):

```python
QUESTION_BLOCK_BOUNDARIES: dict[str, "re.Pattern[str]"] = {
    "claude": _QUESTION_HEADER_RE,   # ☐ <Header> chip (t1420, measured)
    # codex / opencode: filled from the pre-phase measurement, or ABSENT when no
    # structural boundary was found — absence keeps Tier A suppressed for that
    # agent, which is the honest outcome, not a gap to paper over.
}


def current_question_block(lines: list[str], agent: str = "claude") -> int | None:
```

The `agent="claude"` default preserves the existing call from
`review_loop.classify_followed_change` (`:490-495`) **byte-for-byte** while that
call is threaded (below). `phase_from_screen` gains the same parameter and
`compose` passes the agent through. An agent with **no** boundary entry returns
`None` → Tier A suppresses → the ledger wins, with `detail` naming the reason.

`review_loop.classify_followed_change` passes `agent_key` into both
`current_question_block` calls. It is gated Claude-only by decision 6, so this is
correctness insurance rather than a behaviour change — but leaving it would mean
a codex pane newly present in `QUESTION_WIDGET_KINDS` being measured against
Claude's chip, which is exactly the kind of latent wrong-table bug the per-agent
split exists to prevent.

## 4. Fill the tables and split the arming predicate — `lib/workflow_phase.py`, `monitor/review_loop.py`, `monitor/minimonitor_app.py`

- `QUESTION_WIDGET_KINDS["codex"] / ["opencode"]` ← the measured question/selection
  widget kinds (empty tuple if none was found).
- `NATIVE_KIND_PHASE["codex"] / ["opencode"]` ← measured native dialogs that
  imply a phase. A **generic confirmation gets no row** — `codex_yes_proceed` is
  and stays a deliberately absent key, and the drift guard's `LEAKED:-` check
  already fails if it is added.
- `agent_key_from_command` (`:135-145`) becomes a one-line delegation to
  `prompt_patterns.agent_key_from_command`, keeping its name, signature and
  docstring intent (decision 5).
- **New, in `review_loop.py`** (it owns the loop, and the predicate is about the
  loop, not about the phase):

  ```python
  # Agents whose followed-pane change classification has a PROVEN boundary
  # strategy. Deliberately NOT `workflow_phase.live_tiers_available`: that
  # answers "can a phase hint be derived", this answers "may an INJECTING loop
  # be armed". A newly-measured marker must earn the second separately (t1467).
  REVIEW_LOOP_AGENTS: tuple[str, ...] = ("claude",)

  def review_loop_agent_supported(agent: str) -> bool: ...
  ```

- `minimonitor_app.py:2438-2444` calls the new predicate instead of
  `live_tiers_available`, and its message stops citing t1467 (which will no
  longer be the reason): *"Auto-recheck unavailable for '<cmd>' — the recheck
  loop is Claude-only for now"*. The **shadow**-side gate
  (`SHADOW_READY_DETECTORS`, `:2459`) is untouched.

## 5. Tests

Run `bash tests/run_all_python_tests.sh` (**last line only**), each new/edited
bash test individually, and `shellcheck .aitask-scripts/aitask_*.sh`.

1. **`tests/test_prompt_detection.py`** — the pre-phase characterizations, plus:
   the **cross-agent negative control** (a `codex_yes_proceed` body on a pane
   with `current_command="claude"` must NOT report a codex kind — this fails
   against today's build, which is what makes it discriminating), the fail-open
   control (`current_command="node"` still matches the flat list), the
   `prompt_patterns=[]` disable path under scoping, and the custom-pattern
   survival case. `_check_all_patterns_flattens_per_agent_groups` (`:172`)
   derives its count from `PROMPT_PATTERNS_BY_AGENT`, so it absorbs new patterns
   — but its three explicit name assertions (`:180-182`) get siblings for the
   new names.
   **Positive control first:** the scoping tests must fail against the
   unmodified module, asserted by running them once before the change.
2. **`tests/test_workflow_phase.py`** — `test_opencode_live_tiers_unavailable`
   (`:194-205`) **flips by design**: `assertFalse(live_tiers_available("codex"))`
   / `("opencode")` become `assertTrue` for whichever agent actually got markers.
   This is a fixture retarget, not a weakened invariant — the invariant
   ("an agent without markers is ledger-only, and says so") is **preserved** by
   retargeting it onto a synthetic agent key with no markers, so the degradation
   path keeps a live guard after the real agents are wired. Add per-agent Tier A
   and Tier B positive controls built from **captured** fixture text, and keep
   `AbsenceSafetyTest._cases()` (`:177-182`) meaningful by pointing its
   generic-confirmation cases at the still-unmapped kinds.
3. **`tests/test_workflow_phase_prompt_drift.sh`** — guard B already iterates
   both tables per agent (`:116-122`), so the new rows inherit it for free. Add
   `CODEX_WIRED` / `OPENCODE_WIRED` rows beside `CLAUDE_WIRED:1` (`:143`)
   asserting the **measured** truth, so a silently-emptied row fails loudly.
   Add a guard that every key of `QUESTION_BLOCK_BOUNDARIES` is a known agent key.
4. **`tests/test_review_loop.py`** — assert `review_loop_agent_supported` is True
   for `claude` and False for `codex`/`opencode` **even though**
   `live_tiers_available` is now True for them. That divergence is the whole
   point of decision 6 and is otherwise untestable by inspection.
5. **`tests/test_minimonitor_concern_action.py:1481`** —
   `test_refuses_followed_agent_without_live_tiers` currently uses an `opencode`
   pane and asserts the "no prompt detection yet (t1467)" wording. Retarget it to
   the new predicate and the new wording, and add a case proving an OpenCode pane
   is refused **for the loop** while its phase still renders.
6. **Locale degradation** (new, in `test_workflow_phase.py` or a sibling) — feed
   an OpenCode capture whose dialog is rendered in a non-English locale (taken
   from the static i18n pass) and assert the phase degrades to the ledger with a
   suppression `detail`, never to a wrong phase. Paired with the English positive
   control on the same fixture shape, so a build that simply never matches
   anything fails.
7. **`tests/test_gate_workflow_phase.sh`** — add `--agent codex` / `--agent
   opencode` CLI cases (the file has none today), asserting the default
   ledger-only behaviour is unchanged and that `--agent` alone (without
   `--awaiting-input yes`) still cannot override the ledger.

## 6. Docs

- `aidocs/framework/shadow_agent.md:695-708` — rewrite the per-agent availability
  table rows for Codex CLI and OpenCode with the **measured** truth, and replace
  the `t1467` pointers. Add one sentence naming the localization limit for
  OpenCode and one naming the review-loop split (phase available ≠ loop armable),
  since a reader of that table will otherwise infer the loop followed.
- `aidocs/framework/monitor_idle_and_prompt_detection.md` — this is the canonical
  doc for "how idle vs awaiting-input is detected" and for adding a new agent's
  prompt wording. Document the **per-agent scoping rule**, the fail-open
  fallback, and the fact that `prompt_patterns.py` is still the single edit site.
  (Bidirectional: `prompt_patterns.py`'s docstring points back here.)
- `.aitask-scripts/monitor/prompt_patterns.py` docstring — per section 2.
- `aitasks/t1467_…md` — a **Coordination** section recording the review-loop
  split and the follow-up it implies. Edit only this task's own file.

### Post-phase (risk mitigations)

Runs **after** section 6, before the verification sweep.

1. `[prove_scoping_live]` Prove the per-agent scoping is live in the real
   monitor, not just in `classify_content`'s unit tests: in a real tmux session
   with a Claude pane and a Codex pane side by side, put each agent's prompt text
   on the **other** agent's pane and confirm from a **captured monitor render**
   that neither reports the foreign kind, while each still reports its own. A
   unit test of `classify_content` cannot distinguish a correct function from a
   correct function whose `agent=` argument is never threaded at one of the five
   call sites; only the live render can.

## Verification

1. Every test in section 5, with the discriminating ones (5.1 cross-agent
   negative control, 5.6 locale degradation) **run against the pre-change build
   first** and shown to fail.
2. `bash tests/run_all_python_tests.sh` — read the **last line only**
   (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); piping discards the status.
3. `bash tests/test_workflow_phase_prompt_drift.sh`,
   `bash tests/test_gate_workflow_phase.sh`,
   `bash tests/test_prompt_detection.py`, `bash tests/test_shadow_phase_advisory.sh`
   individually.
4. `shellcheck .aitask-scripts/aitask_*.sh`.
5. `bash tests/test_no_raw_tmux.sh` — the pre-phase fixture must go through the
   tmux gateway.
6. **Live acceptance** (manual-verification candidate): with a Codex or OpenCode
   agent parked at a task-workflow checkpoint, `ait minimonitor` renders a phase
   other than a permanent `unknown (ledger)`; the same pane refuses auto-recheck
   arming with the new wording; and a shadow spawned with `e` reads a
   `@aitask_shadow_phase` value that updates as the agent advances.

## Risk

Levels below are the **post-inline reassessment** — they describe the plan as
augmented with the pre-/post-phase blocks, which is the plan being approved.

### Code-health risk: medium

- Per-agent scoping changes `awaiting_input_kind` for real panes, and that field
  is consumed by the idle/awaiting badges, pane-list ordering
  (`monitor_app.py:1368-1380`), the applink wire (`pusher.py:420-421`) and the
  review-loop work latch — a wrong scoping rule degrades four surfaces at once.
  · severity: low (residual — pinned by inline pre-phase
  `characterize_classify_content`, which must be green against unmodified source
  first, with the intended flips tabled before the change)
  · → mitigation: inline pre-phase characterize_classify_content
- Regexes authored from a binary string table rather than a live render would be
  geometrically wrong (t1420 shipped a distance heuristic that had to be
  replaced by a structural rule after measurement). · severity: low (residual —
  the inline pre-phase measures geometry through the monitor's own capture path
  before any pattern is authored) · → mitigation: inline pre-phase
  inventory_prompt_surfaces_live
- OpenCode's prompt strings are localized; an English-only anchor silently stops
  matching under another locale, and silence is indistinguishable from "agent is
  idle". · severity: medium (residual — the inline pre-phase measures the same
  keys in ≥2 other locales so the blast radius is known, and Verification 5.6
  pins the degradation; but no anchor choice can *remove* the limit)
  · → mitigation: inline pre-phase inventory_prompt_surfaces_live
- Generalizing `current_question_block` adds a per-agent table read by two
  modules (`workflow_phase`, `review_loop`); an agent present in
  `QUESTION_WIDGET_KINDS` but absent from `QUESTION_BLOCK_BOUNDARIES` would be
  measured against the wrong boundary. · severity: low · → mitigation: none
  (absence returns `None` → suppress; pinned by the section 5.3 key guard)
- Splitting the arming predicate creates two similar per-agent predicates that
  can drift into each other. · severity: low · → mitigation: none (one named
  constant `REVIEW_LOOP_AGENTS`, and section 5.4 asserts the divergence
  explicitly rather than trusting inspection)
- Threading `agent=` through five `classify_content` call sites is exactly the
  shape where one site is missed and the unit tests stay green.
  · severity: low (residual — the failure mode is caught only by the live
  render in inline post-phase `prove_scoping_live`, which is why it is a live
  capture and not another unit test) · → mitigation: inline post-phase
  prove_scoping_live

### Goal-achievement risk: medium

- The whole Tier A half for these agents depends on a **structural block
  boundary** existing in their TUIs, comparable to Claude's `☐` chip. Neither
  CLI has an `AskUserQuestion` widget; if neither renders a stable boundary,
  Tier A cannot ship for them and the task delivers Tier B only.
  · severity: medium (residual — the inline pre-phase settles it **before** any
  dependent code is written and decision 7 pre-decides the fallback, so a
  negative result costs one rung rather than a rewrite; but measuring earlier
  cannot make a boundary exist, so the delivery probability is unchanged)
  · → mitigation: inline pre-phase inventory_prompt_surfaces_live
- Codex and OpenCode have no `ExitPlanMode` equivalent, so there may be **no
  phase-bearing native dialog** to map — leaving Tier B empty too, and the task
  delivering only the scoping and the honest availability statement.
  · severity: medium (residual — same shape as above: known early, honestly
  documented, but not made less likely) · → mitigation: inline pre-phase
  inventory_prompt_surfaces_live
- The live pass needs working auth and quota on both CLIs; a sandbox refusal or
  rate limit would leave the static pass as the only evidence.
  · severity: low · → mitigation: none (recorded verbatim and that agent's row
  ships `no`; decision 7 makes a dropped rung a planned outcome)

### Planned mitigations
- timing: pre-phase | name: inventory_prompt_surfaces_live | type: test | priority: high | effort: medium | inline_risk: medium | added_complexity: low | addresses: goal-achievement — whether a structural question-block boundary and a phase-bearing native dialog exist at all for Codex/OpenCode; code-health — geometrically wrong regexes and the OpenCode localization blast radius | desc: Enumerate candidate markers statically from the shipped codex binary and the opencode i18n bundle (including ≥2 non-English locales), then drive each CLI in an isolated tmux fixture through its approval / live-question / answered-question / idle states, capturing via the monitor's own capture-pane + strip_ansi path and recording line, distance above bottom, strip survival, disjointness from existing patterns, and boundary existence — before any pattern is authored.
- timing: pre-phase | name: characterize_classify_content | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — per-agent scoping moving awaiting_input_kind across the badges, pane ordering, the applink wire and the review-loop latch | desc: Pin today's (awaiting_input, awaiting_input_kind) for every existing pattern across current_command in {claude, codex, opencode, node, ""} plus the prompt_patterns=[] disable path and the category gate, run green against unmodified monitor_core.py, and table the intended flips before making the change.
- timing: post-phase | name: prove_scoping_live | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — one of the five classify_content call sites missing the agent= thread while unit tests stay green | desc: In a real tmux session with a Claude pane and a Codex pane, put each agent's prompt text on the other's pane and confirm from a captured monitor render that neither reports the foreign kind while each still reports its own.
