---
Task: t1509_shadow_readiness_detectors_for_non_claude_shadows.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1509 — Shadow readiness detection for a Codex shadow

## Context

`ait minimonitor`'s auto-recheck loop (t1159_2) drives the **shadow** pane: when
the shadow's analysis of the followed agent goes stale, the loop injects a
"run the next review round" prompt plus Enter. Because Enter into a pane parked
at a dialog would *answer* that dialog, the loop refuses to arm unless the
shadow's agent has a readiness detector. Today `SHADOW_READY_DETECTORS`
(`review_loop.py:382`) holds only `{"claude": _claude_ready}`.

The pairing the framework actually uses — and the one its live positive control
verified (archived t1498, t1493's coordination note) — is a **Codex shadow of a
Claude followed pane**. So the automatic loop cannot arm in exactly the
configuration in which the manual recheck path is live-proven. This task closes
the shadow half for Codex.

**Scope decision (user-confirmed):** Codex ships here; OpenCode becomes a
sibling follow-up. Both agents' surfaces were measured live during planning
(evidence below), and OpenCode's composer is structurally different enough
(a `┃`-gutter box anchored on its bottom border, no SGR-dim placeholder, and a
placeholder hint that disappears after the first turn) to deserve its own live
evidence and its own review.

---

## Live measurement (done at planning time — resolves the task's safety question)

Captured 2026-08-14 through the monitor's own capture path (`capture-pane -p -e`
on a private tmux socket, 120x30) against **codex-cli 0.146.0 / gpt-5.6-terra**
and **opencode 1.18.18**. Raw captures are in the session scratchpad
(`measure/caps/`).

**The task asked: can a Codex pane parked at a dialog satisfy the POSITIVE
empty-composer half? Answer: no — measured, in isolation.** Running the positive
half with the negative pattern list *disabled* over every Codex dialog state:

| Codex state | positive half alone | why |
|---|---|---|
| permission dialog | **False** | composer is gone; lowest `›` line is an option row with visible non-dim text |
| question widget | **False** | composer is gone; lowest `›` line is the echoed user message |
| startup update prompt | **False** | same shape; option row carries visible non-dim text |
| at rest | True | `›` + entirely-dim placeholder hint |
| streaming | **True** | ← the real gap, see below |

So the thin-pattern-list worry was about dialogs, and dialogs are excluded
**structurally**: a Codex dialog replaces the composer's screen real estate.
The negative half is therefore defense-in-depth for dialogs, not load-bearing —
and it is stronger than the task assumed: **t1467 already landed three
live-measured Codex patterns** (`codex_question`, `codex_permission`,
`codex_yes_proceed`) and two OpenCode ones, so the task's "codex has 1
placeholder, opencode has 0" premise is stale. **No `depends: [1467]` edge is
needed.**

**What IS load-bearing for Codex:** the pane renders the *identical* empty
dim-hint composer while streaming. Conjunct (b)'s working-indicator regex and
conjunct (c)'s hash instability are the only things that block a streaming
Codex shadow from reading as ready. Measured working line:
`• Working (Ns • esc to interrupt)` (per-character animated shimmer + a
per-second timer, so the raw tail is hash-unstable) and `• Running <cmd>`.

**Residual, accepted and documented:** for ~1 tick after a dialog is answered,
Codex renders an empty composer with no working indicator yet. Same class of
transient the Claude detector has; covered by conjunct (c) plus the
controller's work-observed latch, not by the detector.

## The actual blocker (found during measurement)

Adding a `codex` entry to `SHADOW_READY_DETECTORS` is **not sufficient**. The
arm gate resolves the shadow's agent with
`workflow_phase.agent_key_from_command(shadow_command)` (`minimonitor_app.py:2468`,
re-checked at `:2554`) — rung 1 only. Codex installs as a **node wrapper**, so
`pane_current_command` reports `node` (confirmed live: `list-panes` reported
`node` for the Codex pane; `agent_keys.py:19-26` documents exactly this). Rung 1
returns `""`, so a Codex shadow would still be refused.

Fixing it needs the two-rung `agent_key_from_pane(command, pid, pane_id)`, which
needs the shadow pane's **pid** — a field `shadow_query_args()` does not
currently request.

---

## Implementation

### Pre-phase (risk mitigations)

1. `[pin_shadow_seam_consumers]` **Before** touching
   `shadow_query_args` / `match_shadow_pane_info` /
   `find_shadow_pane_info_async`, enumerate every consumer of the latter two
   (`grep -rn` across `.aitask-scripts/` and `tests/`: `monitor_core.py`'s own
   `match_shadow_pane` + `find_shadow_pane_async`, `tmux_monitor.py`'s
   re-export, `minimonitor_app.py:2456` and `:2899`, and the assertions in
   `tests/test_minimonitor_concern_action.py` / `tests/test_shadow_seam.py` /
   `tests/test_minimonitor_concern_smoke.py`). Add a test that **exercises each
   unpack path** — not just the pure helper, but every call site that destructures
   its result — and confirm the new test passes against the *unmodified* helpers
   first, so it is a real characterization baseline and not a shape the widening
   authored. A missed unpack site must then fail this test rather than raise a
   `TypeError` inside a live minimonitor tick.

### Phase 1 — carry the shadow pane's pid to the arm gate

`.aitask-scripts/monitor/monitor_core.py`

1. `shadow_query_args()` (:443) — append a fourth field `#{pane_pid}`. Keep the
   docstring's forward-compat promise: shorter lines still parse.
2. `match_shadow_pane_info()` (:377) — return `(pane_id, command, pid)`. Parse
   field 3 as `int` when present and numeric, else `0`. **Preserve the existing
   `len(parts) < 2: continue` tolerance verbatim** — the docstring's two-field
   contract (older format / test stubs) must keep resolving, now with `pid = 0`.
   `match_shadow_pane()` (:413) is unchanged (it indexes `[0]`).
3. `find_shadow_pane_info_async()` (:507) — return `(ok, pane, command, pid)`;
   the three failure/absence returns become `(False, None, "", 0)` /
   `(True, None, "", 0)`. `find_shadow_pane_async()` (:499) already discards the
   extras — widen its unpack.
4. `.aitask-scripts/monitor/tmux_monitor.py:48-52` — re-export list unchanged in
   names; no signature is declared there.

`.aitask-scripts/monitor/minimonitor_app.py`

5. Both `find_shadow_pane_info_async` call sites (:2456 arm, :2899 mid-loop)
   unpack the fourth value.
6. Replace `agent_key_from_command(shadow_command)` with
   `agent_key_from_pane(shadow_command, shadow_pid, shadow_pane)` at **both**
   the arm gate (:2468) and the mid-loop re-check (:2554).
   Call it **inline (synchronously)** — do not add an `await`. Precedent:
   `monitor_core.py:2216` calls the same function inline inside
   `_finalize_capture`, which is documented as atomic on the loop, and
   `:2311/:2396/:2449` do the same. Rung 2 is a `pgrep`+`ps` pair bounded at 2 s
   with a positive cache keyed on `(pane_id, pid, command)`, so steady state is
   free. Adding an `await` here would insert a suspension point *before* the
   mid-loop's `lifecycle_gen` snapshot and needs a second generation guard —
   avoided entirely by staying synchronous. Do **not** route it through
   `TmuxMonitor._run_offloaded`: that seam's contract is "pure compute over
   plain data" and this shells out.

### Phase 2 — distinguish "unresolved" from "unsupported"

`agent_keys`' own contract: `""` means **could not resolve**, never "not an
agent", and negative results are provisional (the wrapper spawns its child
asynchronously; misses are retried on a 1 s/5 s/15 s→300 s backoff). A shadow
launched moments before the user presses the arm key therefore resolves `""`
transiently. Today `"" not in SHADOW_READY_DETECTORS` collapses both cases into
one message, and mid-loop it would **auto-disarm** — destroying the user's armed
state over a timing artifact.

7. Arm gate (:2468): split the branch.
   - `shadow_key == ""` → refuse with a *transient* message in the shape of the
     existing query-failure branch: "Auto-recheck unavailable: could not resolve
     the shadow's agent yet — try again".
   - resolved key not in `SHADOW_READY_DETECTORS` → keep the existing refusal
     verbatim, still naming the agent: `Auto-recheck unavailable: shadow agent
     '<cmd or unknown>' has no readiness detection yet`. This is the refusal
     t1159_2 test-pinned; it must stay reachable — after this task OpenCode is
     what reaches it.
8. Mid-loop re-check (:2554): `shadow_key == ""` → **hold** (return without
   disarming, as the transient tmux-failure path does); a resolved-but-
   unsupported key keeps auto-disarming with the existing message.

### Phase 3 — generalize the detector, add Codex

`.aitask-scripts/monitor/review_loop.py`

9. Extract the body of `_claude_ready` (:338) into
   `_composer_ready(raw_text, *, agent, composer_re, working_re, pad)`:
   negative-patterns-first over `PROMPT_PATTERNS_BY_AGENT[agent]`, then
   `working_re`, then the bottom-up composer scan with the `_DIM_SPAN_RE`
   dim-strip discriminator. `pad` is the run of characters stripped after the
   glyph (`"  "` Claude, `" "` Codex). `_claude_ready` becomes a thin
   wrapper so its name, signature and behaviour are unchanged.
10. Add the Codex constants, pinned from the live captures with a provenance
    comment naming version + date (t1420/t1474 maintain-in-place practice):
    - `_CODEX_COMPOSER_RE = re.compile("^›( .*)?$")` — `›` + optional
      plain-space-prefixed text. Note in the comment why there is **no NBSP
      discriminator** as Claude has: Codex uses a plain space, and option rows /
      echoed user messages share the glyph. They are excluded by the dim-strip
      test instead (an option row's label and an echoed message are not dim),
      which is what the isolated-positive-half measurement above verified.
    - `_CODEX_WORKING_RE = re.compile(r"(?m)^\s*•\s+(?:Working|Running)\b|esc to interrupt")`
      — covers both `• Working (Ns • esc to interrupt)` and `• Running <cmd>`.
      Kept separate from `_CLAUDE_SPINNER_RE`, whose `\(esc to interrupt\)`
      requires the parenthesised form Codex does not render.
    - `_codex_ready(raw_text)` delegating to `_composer_ready`.
11. `SHADOW_READY_DETECTORS["codex"] = _codex_ready`. Rewrite the dict comment
    (:379-381) and the module contract block (:301-319) to be agent-generic and
    to record the measured facts: dialogs replace the composer for Codex, so the
    positive half excludes them structurally; the working indicator plus hash
    stability are what exclude streaming; the ~1-tick post-dialog gap is a
    documented residual. `REVIEW_LOOP_AGENTS` (:396, the **followed** side)
    stays `("claude",)` — out of scope, and a Claude followed pane with a Codex
    shadow is precisely the pairing being unblocked.

### Phase 4 — fixtures and tests

`tests/review_loop_fixtures.py` (the established home for these captures — the
task text says "inline in `test_review_loop.py`", but the shipped practice from
t1159_2 is this separate module; following the shipped practice)

12. Add one single-line raw literal per measured state, ANSI preserved:
    `CODEX_AT_REST_RAW`, `CODEX_TYPED_RAW`, `CODEX_WORKING_RAW`,
    `CODEX_PERMISSION_RAW`, `CODEX_QUESTION_RAW`, `CODEX_UPDATE_PROMPT_RAW`.
    Extend the module provenance docstring with the Codex capture session
    (codex-cli 0.146.0, gpt-5.6-terra, 2026-08-14, 120x30, `capture-pane -p -e`).
    `CODEX_UPDATE_PROMPT_RAW` is the startup update-available dialog — the state
    **no** prompt pattern matches, so it is the fixture that proves the positive
    half is doing the work.

`tests/test_review_loop.py` (`ShadowPromptReadyTests`, stdlib `unittest`)

13. Per-state cases mirroring the Claude ones: at-rest + `hash_stable` → `True`;
    typed / working / permission / question / update-prompt → **not** `True`;
    at-rest with `hash_stable=False` → `False`; `raw_text=None` → `None`.
14. **Isolated positive half** — the task's explicit safety question, as an
    executable assertion. With `PROMPT_PATTERNS_BY_AGENT` patched so `"codex"`
    is empty, `_codex_ready` must still return `False` for all three dialog
    fixtures. Without this, the dialog cases only prove the pattern list fires.
15. **Negative controls** (one mutation each, each with a named failing
    assertion): swap `_CODEX_COMPOSER_RE` for Claude's NBSP form → at-rest stops
    being ready; drop `_CODEX_WORKING_RE` → the working fixture becomes ready,
    pinning that regex as the thing excluding streaming.
16. Fix the now-wrong existing assertion at :473
    (`shadow_prompt_ready(CLAUDE_AT_REST_RAW, "codex", True) is None`) — Codex is
    supported now. Re-point the unknown-agent case at `"opencode"` and add a
    genuinely-unknown key (`"gemini"`), so "unknown agent ⇒ indeterminate" stays
    pinned.

`tests/test_minimonitor_concern_action.py` (:1454-1470) and
`tests/test_shadow_seam.py` (:182)

17. Update the four `match_shadow_pane_info` / `find_shadow_pane_info_async`
    tuple assertions for the new arity, and add cases for the pid field: a
    4-field line yields the pid; 3-field and 2-field lines still resolve with
    `pid = 0`.
18. New cases for Phase 1+2 at the app level: a shadow pane whose command is
    `node` with a pid whose child is `codex` resolves to `codex` and **arms**
    (the regression this task exists to fix); an `opencode` shadow still hits
    the unchanged refusal; an unresolvable shadow refuses at arm time **without**
    the unsupported-agent wording and **holds** rather than disarms mid-loop.

### Phase 5 — docs

19. `aidocs/framework/shadow_agent.md` (review-loop section) — record that
    shadow **composer/working** patterns are per-agent and live in
    `review_loop.py` (not `prompt_patterns.py`, which owns followed-pane dialog
    patterns), that Codex is now supported, and that the arm gate resolves the
    shadow's agent via the two-rung ladder because Codex reports `node`.
20. `aidocs/framework/monitor_idle_and_prompt_detection.md` — one cross-reference
    to the above, so the "when to edit `prompt_patterns.py`" page does not read
    as the only place per-agent pane text is matched.
    **Obey that page's own third rule:** describe dialog structure in prose;
    never paste an option block verbatim into a doc, task, or plan.

---

## Verification

- `python3 tests/test_review_loop.py` — the new per-state, isolated-positive-half
  and negative-control cases.
- `python3 tests/test_minimonitor_concern_action.py`,
  `python3 tests/test_shadow_seam.py` — the widened tuples and pid parsing.
- `bash tests/run_all_python_tests.sh` — **read only the last stderr line**
  (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); do not pipe to `tail`
  without `pipefail`.
- `shellcheck` — not applicable (no shell scripts touched).
- **Live** (queued as a manual-verification follow-up at Step 8c, per the
  user's decision): arm the loop in a real `ait minimonitor` with a Codex
  shadow of a Claude followed pane, observe one automatic recheck fire, and
  confirm nothing is injected while that shadow is mid-output or parked at a
  dialog. Also confirm an OpenCode shadow still produces the refusal naming the
  agent.

## Coordination

- **OpenCode sibling follow-up** (to be created): the border-anchored detector.
  Measured evidence to hand over — the composer is a `┃`-gutter box whose
  positive anchor must be its `╹▀▀▀…` bottom border plus the composer status
  row (`Build · <model> · <effort>`); the permission dialog **replaces** that box
  (so the positive half excludes it, same as Codex) but the dialog is *also* a
  `┃`-gutter box containing blank rows, so a naive "blank `┃` row" rule
  false-positives; the gray placeholder hint is **not** a durable readiness
  signal — it disappears after the first turn; the working state is a blank
  composer plus an `⬝⬝⬝⬝ esc interrupt` footer.
- **t1467** (followed-side per-agent prompt patterns) — no blocking edge, per the
  measurement above. One gap to hand over: the **Codex startup
  update-available prompt** is a real awaiting-user-input dialog that no Codex
  pattern matches, so `ait monitor` will not flag a followed Codex pane parked
  there. Recorded for the Step 8b upstream-defect offer.
- **t1159_5** (aggregate manual verification of the review loop) — its checklist
  assumes a loop that can arm; with this task landed, verify it with the Codex
  shadow pairing rather than substituting a Claude shadow.
- **Step 9 (Post-Implementation)** — merge to `main`, archive t1509 and its plan.

## Risk

### Code-health risk: medium
- Widening the `match_shadow_pane_info` / `find_shadow_pane_info_async` return
  tuples changes a shared shadow seam consumed by the concern picker, key
  forwarding and the launch guards; a missed unpack site surfaces as a runtime
  `TypeError` inside a live minimonitor tick rather than as a test failure ·
  severity: medium · → mitigation: inline pre-phase pin_shadow_seam_consumers
- Phase 2 changes an existing arm/disarm gate's semantics (an unresolved shadow
  key holds instead of disarming), so a regression in `agent_key_from_pane`
  would present as a loop that silently never settles instead of a visible
  refusal · severity: low · → mitigation: none (accepted; Phase 4 step 18 pins
  both the hold and the refusal branches)

### Goal-achievement risk: low
- The Codex composer/working regexes are pinned to codex-cli 0.146.0 and the
  pane itself already advertises 0.147.0; a UI change makes readiness
  permanently `False`. The failure direction is fail-safe (the loop holds and
  never injects), but it is **silent** — indistinguishable from a shadow that is
  simply busy · severity: low · → mitigation: surface_never_settled_shadow
- For roughly one tick after a Codex dialog is answered the pane shows an empty
  composer with no working indicator yet, so conjunct (c) is the only thing
  standing between that window and a fire. Outside the task's stated
  requirement (neither mid-output nor at-dialog) but worth confirming live ·
  severity: low · → mitigation: covered by the queued manual-verification
  follow-up (a dedicated `measure_post_dialog_gap` mitigation was proposed and
  dropped as duplicative)

### Planned mitigations
- timing: pre-phase | name: pin_shadow_seam_consumers | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (shadow-seam tuple widening / missed unpack site) | desc: Characterize every consumer's unpack path against the unmodified helpers before widening them, so a missed call site fails a test instead of a live minimonitor tick.
- timing: after | name: surface_never_settled_shadow | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement risk 1 (silent composer-pattern drift across a Codex release) | desc: When the loop is armed and the shadow never reads ready for N consecutive ticks, surface a banner hint that its composer pattern may need re-pinning, turning a silent fail-safe hold into a legible signal.

**Reassessment after inlining** (`risk-evaluation.md` Step 3 note): with
`pin_shadow_seam_consumers` inlined as a pre-phase, code-health risk stays
**medium** — the characterization test closes the missed-unpack path, but the
seam's blast radius and the Phase 2 semantic change are unchanged.
Goal-achievement risk stays **low**.
