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

**Post-dialog settle window — NOT an accepted residual (revised after review).**
For a period after a dialog is answered, Codex renders an empty composer with no
working indicator yet. The first draft of this plan waved that away as "~1 tick,
covered by conjunct (c)". Re-checking the source shows that reasoning was wrong:

- committed evidence ticks are throttled to
  `max(1.0, 0.5 * _refresh_seconds)` = **1.5 s** at the default 3 s refresh
  (`minimonitor_app.py:2518-2523`), **not** one 3 s refresh;
- `hash_stable` needs only `_loop_shadow_hash_streak >= 1` (:2584), i.e. **two**
  identical consecutive captures — so a **1.5 s** unchanged window is enough.

The measured gap was **≥ 2 s** (a capture 2 s after the dialog was answered still
showed no working indicator; the next at 4 s showed `• Working (3s …)`). A gap
that spans two 1.5 s evidence ticks makes `shadow_ready` True with nothing
running, and the loop would send its prompt + Enter before Codex resumed — the
exact failure this feature exists to prevent. It is therefore **measured
explicitly (Pre-phase step 2) and closed structurally (Phase 3b)**, and the
measurement is a **required pre-ship condition**, not an optional check.

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

2. `[measure_post_dialog_settle]` **Measure the post-interaction settle window in
   WALL-CLOCK SECONDS, before writing the guard it sizes.** Drive a live Codex
   pane in a private tmux socket and, for each interaction kind, record the
   elapsed monotonic time from *the interaction leaving the screen* to *the
   working indicator appearing*:
   - the permission dialog (answered `y`),
   - the question widget (an option submitted),
   - the startup update prompt (dismissed) — included because Phase 3b treats it
     as latch-arming and no prompt pattern matches it,
   - and, as the pathological case, an interaction answered so that **no work
     follows** (Codex's "No, tell Codex what to do differently" / Esc), to
     confirm the deadline is the only thing that releases the latch there.

   Sample at **0.25 s**, far below any configured evidence cadence, so the
   measurement describes the pane rather than the sampler. Repeat **≥ 5 times**
   per kind. Record every raw number in this plan's Final Implementation Notes.

   The measurement **sizes `SHADOW_SETTLE_SECONDS` in Phase 3b** as
   `ceil(max_observed_gap_seconds) + 1 s` margin. It is a **required pre-ship
   condition** — Phase 3b does not ship with a guessed value. If some repetition
   shows no gap at all, that negative result is recorded explicitly and the latch
   **still ships** with a floor of 2 s: five samples not reproducing a window is
   not proof that it cannot occur. Deliberately *not* expressed in ticks — see
   Phase 3b on why a tick count is cadence-dependent.

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
   the arm gate (:2468) and the mid-loop re-check (:2554), and run it **off the
   event loop**.

   *(Correction from the first draft, which argued for a synchronous call on the
   grounds that `monitor_core.py:2216` does the same. That precedent is the
   **sync** capture path. The **async** path — the one these two call sites live
   on — already offloads it: `_classify_batch` (`monitor_core.py:275-290`) calls
   `agent_key_from_pane` inside a single `asyncio.to_thread` hop. Offloading is
   therefore the established pattern here, not the exception. On a cache miss
   rung 2 runs `pgrep` then `ps`, each bounded at `_LOOKUP_TIMEOUT = 2.0 s`, so
   a wedged process table could block the Textual loop for up to ~4 s — freezing
   the UI and delaying every armed-loop evidence tick.)*

   - Add one overridable app method so tests can drive resolution order
     deterministically:
     ```python
     async def _resolve_shadow_agent_key(self, command, pid, pane_id) -> str:
         return await asyncio.to_thread(
             workflow_phase.agent_key_from_pane, command, pid, pane_id)
     ```
     Do **not** route it through `TmuxMonitor._run_offloaded`: that seam's
     documented contract is "pure compute over plain data" (`monitor_core.py:1650`)
     and this shells out.
   - **Mid-loop (:2554): the new `await` is a suspension point, so it needs the
     same generation guard the capture already has.** Move
     `lifecycle_gen = ctrl.generation` to **before** the resolution await and
     re-check `ctrl.generation != lifecycle_gen` immediately after it, returning
     without mutating anything on a mismatch — then reuse that same snapshot for
     the existing `capture_raw_tail` check. Without this, a disarm/re-arm during
     the lookup could auto-disarm a *freshly armed* lifecycle on stale evidence.
   - **Arm action (:2468): guard the equivalent race.** Snapshot
     `(ctrl.armed, ctrl.generation)` before the await and abandon the arm
     (notify nothing) if either changed — the user may have pressed the key
     again, or the loop may have been armed by another path, while the lookup
     was in flight.

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

### Phase 3b — close the post-interaction settle window structurally

The window measured in Pre-phase step 2 is a **timing** hazard, so a timing
answer ("require a longer hash streak") would only move it. Close it with state:
the loop must positively observe the shadow leave an interaction *into work*, or
wait out a wall-clock deadline, before an empty composer counts as ready.

Two properties are load-bearing, both from the review round; the earlier
tick-counted, dialog-only draft failed each of them:

- **The arming predicate must not depend on prompt-pattern coverage.** Codex's
  startup update prompt is a real on-screen interaction that **no** pattern
  matches — the prototype classifies it from the positive half alone (its `›`
  option row carries visible non-dim text). A latch armed only by "a negative
  pattern matched" would never arm for it, and the same class of gap reopens for
  every future un-patterned dialog. So the latch arms on **anything that is not
  a positively-identified empty composer and not a positively-identified working
  state**. That is strictly more conservative, needs no pattern coverage, and
  also covers a shadow holding user-typed text — where injecting would
  concatenate onto what the user typed.
- **The deadline must be wall-clock, not tick-counted.** The evidence cadence is
  `max(1.0, 0.5 * _refresh_seconds)` and `_refresh_seconds` is user-configurable
  from **two** places (`--interval/-i`, `minimonitor_app.py:3207/3223`, and
  `project_config.yaml: monitor.refresh_seconds`). At `--interval 1` or `2` the
  cadence floors at **1.0 s**, so a fixed `R` sized against the default 1.5 s
  cadence expires ~33 % early and restores the original risk. A monotonic
  deadline is cadence-independent by construction.

12. `review_loop.py` — expose the detector's verdict instead of collapsing it to
    a bool, keeping **one** implementation:
    ```python
    SHADOW_DIALOG, SHADOW_WORKING, SHADOW_READY, SHADOW_BUSY, SHADOW_UNKNOWN = (
        "dialog", "working", "ready", "busy", "unknown")

    def shadow_state(raw_text: str | None, agent: str) -> str: ...
    ```
    `_composer_ready` is refactored to return one of these: `working` = the
    working regex matched; `ready` = a positively-identified **empty** composer;
    `dialog` = a negative pattern matched **or** the positive scan found an
    option-row-shaped `›` line (`^›\s*\d+\.\s`) **or** no composer line at all —
    the structural cases that cover the un-patterned update prompt and the
    question widget; `busy` = a composer carrying genuine typed text;
    `unknown` = capture failed / no detector.
    `shadow_prompt_ready` is then **derived** from `shadow_state` — same
    signature, same behaviour, no second copy of the rules — so the two can
    never disagree.

13. `minimonitor_app.py` — a **wall-clock post-interaction settle latch** on the
    committed evidence tick:
    - `self._loop_shadow_settle_until: float | None = None` (a monotonic
      deadline; `None` = clear). Reset to `None` in `arm()` and at the two
      existing `_loop_shadow_hash_streak = 0` reset sites, so a fresh lifecycle
      never inherits it.
    - `SHADOW_SETTLE_SECONDS` — a module constant in **seconds**, sized by
      Pre-phase step 2 as `max_observed_gap_seconds` rounded up plus a margin.
      Not a tick count; nothing about it references the refresh interval.
    - Injectable clock: `self._loop_now = time.monotonic` (overridable), so the
      tests drive the deadline deterministically rather than sleeping — the same
      no-sleep-timing discipline `_run_offloaded` documents.
    - `state == SHADOW_WORKING` → clear the latch (`None`). The normal exit: the
      shadow demonstrably resumed work.
    - `state` **not** in `(SHADOW_READY, SHADOW_WORKING)` → arm/refresh the
      latch to `now + SHADOW_SETTLE_SECONDS` and force `shadow_ready = False`.
      This is the pattern-coverage-independent predicate above.
    - `state == SHADOW_READY` with the latch armed → force `shadow_ready = False`
      while `now < deadline`; at or past it, clear the latch and let the normal
      three-conjunct verdict stand. **The deadline is itself the escape hatch**,
      and it always expires — so answering a dialog in a way that produces no
      work at all (Codex's "No, tell Codex what to do differently", or Esc) can
      never wedge the armed loop, which a clear-only-on-`WORKING` latch would.
    - Net effect: after any interaction, a fire needs the shadow to either
      demonstrably resume work, or present an empty composer continuously past a
      wall-clock deadline strictly longer than the measured gap — at **every**
      configured refresh interval, not just the default.

### Phase 4 — fixtures and tests

`tests/review_loop_fixtures.py` (the established home for these captures — the
task text says "inline in `test_review_loop.py`", but the shipped practice from
t1159_2 is this separate module; following the shipped practice)

14. Add one single-line raw literal per measured state, ANSI preserved:
    `CODEX_AT_REST_RAW`, `CODEX_TYPED_RAW`, `CODEX_WORKING_RAW`,
    `CODEX_PERMISSION_RAW`, `CODEX_QUESTION_RAW`, `CODEX_UPDATE_PROMPT_RAW`.
    Extend the module provenance docstring with the Codex capture session
    (codex-cli 0.146.0, gpt-5.6-terra, 2026-08-14, 120x30, `capture-pane -p -e`).
    `CODEX_UPDATE_PROMPT_RAW` is the startup update-available dialog — the state
    **no** prompt pattern matches, so it is the fixture that proves the positive
    half is doing the work.

`tests/test_review_loop.py` (`ShadowPromptReadyTests`, stdlib `unittest`)

15. Per-state cases mirroring the Claude ones: at-rest + `hash_stable` → `True`;
    typed / working / permission / question / update-prompt → **not** `True`;
    at-rest with `hash_stable=False` → `False`; `raw_text=None` → `None`.
16. **Isolated positive half** — the task's explicit safety question, as an
    executable assertion. With `PROMPT_PATTERNS_BY_AGENT` patched so `"codex"`
    is empty, `_codex_ready` must still return `False` for all three dialog
    fixtures. Without this, the dialog cases only prove the pattern list fires.
17. **Negative controls** (one mutation each, each with a named failing
    assertion): swap `_CODEX_COMPOSER_RE` for Claude's NBSP form → at-rest stops
    being ready; drop `_CODEX_WORKING_RE` → the working fixture becomes ready,
    pinning that regex as the thing excluding streaming.
18. Fix the now-wrong existing assertion at :473
    (`shadow_prompt_ready(CLAUDE_AT_REST_RAW, "codex", True) is None`) — Codex is
    supported now. Re-point the unknown-agent case at `"opencode"` and add a
    genuinely-unknown key (`"gemini"`), so "unknown agent ⇒ indeterminate" stays
    pinned.

`tests/test_minimonitor_concern_action.py` (:1454-1470) and
`tests/test_shadow_seam.py` (:182)

19. Update the four `match_shadow_pane_info` / `find_shadow_pane_info_async`
    tuple assertions for the new arity, and add cases for the pid field: a
    4-field line yields the pid; 3-field and 2-field lines still resolve with
    `pid = 0`.
19b. **Phase 3b latch cases** (`tests/test_review_loop.py` + the app-level
    module), all driven through the injected `_loop_now` clock — no sleeps:
    - `shadow_state` returns the right verdict for **each** Codex fixture, and
      `shadow_prompt_ready` derived from it is behaviour-compatible on every
      **Claude** fixture (a characterization guard on the refactor).
    - `CODEX_UPDATE_PROMPT_RAW` classifies as `SHADOW_DIALOG` — **not**
      `SHADOW_BUSY`. This is the assertion that pins the structural
      (pattern-independent) arming rule; it fails against a
      pattern-match-only implementation.
    - **End-to-end update-prompt sequence:** `update_prompt → ready → ready …`
      holds until the wall-clock deadline and fires only after it, exactly as
      the permission-dialog sequence does. Without this the un-patterned dialog
      is untested even though it is the case that motivated the rule.
    - `dialog → ready → working → ready` clears the latch early via the
      `WORKING` observation.
    - **Wedge negative control:** a `dialog → ready …` sequence that never
      produces a `working` observation must still fire once the deadline passes
      — pinning the escape hatch a clear-only-on-`WORKING` implementation would
      silently omit.
    - **Cadence independence (concern B, as an executable assertion):** run the
      same sequence twice, once with `_refresh_seconds = 3` (1.5 s cadence) and
      once with `_refresh_seconds = 1` (the 1.0 s floor), advancing the injected
      clock by the respective interval per tick. **The hold must end at the same
      wall-clock offset in both runs, i.e. after more ticks in the 1.0 s run.**
      A tick-counted implementation passes the 1.5 s run and fails this one,
      which is the point.

19c. **Phase 1 async-resolution cases:** with `_resolve_shadow_agent_key`
    overridden to resolve after the caller bumps `ctrl.generation`, the mid-loop
    invocation must mutate nothing and the arm action must not arm — pinning
    both generation guards. Each needs its stale-result path asserted
    explicitly, not just a "does not crash" assertion.

20. New cases for Phase 1+2 at the app level: a shadow pane whose command is
    `node` with a pid whose child is `codex` resolves to `codex` and **arms**
    (the regression this task exists to fix); an `opencode` shadow still hits
    the unchanged refusal; an unresolvable shadow refuses at arm time **without**
    the unsupported-agent wording and **holds** rather than disarms mid-loop.

### Phase 5 — docs

21. `aidocs/framework/shadow_agent.md` (review-loop section) — record that
    shadow **composer/working** patterns are per-agent and live in
    `review_loop.py` (not `prompt_patterns.py`, which owns followed-pane dialog
    patterns), that Codex is now supported, and that the arm gate resolves the
    shadow's agent via the two-rung ladder because Codex reports `node`.
22. `aidocs/framework/monitor_idle_and_prompt_detection.md` — one cross-reference
    to the above, so the "when to edit `prompt_patterns.py`" page does not read
    as the only place per-agent pane text is matched.
    **Obey that page's own third rule:** describe dialog structure in prose;
    never paste an option block verbatim into a doc, task, or plan.

---

### Phase 6 — hand the OpenCode half off as a real task (not a coordination note)

The user-approved scope decision defers OpenCode, which is part of the task's own
scope line ("and `opencode` if its surfaces are observable" — they **are**
observable, and were observed). A coordination paragraph is not a handoff, so
this is an explicit, non-skippable implementation step: **the OpenCode task is
created before this task's Step 8 review**, so it cannot evaporate once Codex
lands.

23. Create the sibling with the measured evidence in its body:
    ```bash
    ./.aitask-scripts/aitask_create.sh --batch \
      --name shadow_readiness_detector_for_opencode \
      --type feature --priority high --effort medium \
      --labels shadow,aitask_monitormini,opencode \
      --anchor 1159 \
      --desc-file <body-file> --commit
    ```
    (Resolve the exact flag spellings against `aitask_create.sh --help` at
    implementation time; `--anchor 1159` keeps it in t1509's topic group.)

    The body **must carry the planning measurements**, because they are the
    expensive part and re-deriving them costs another live session:
    - the composer is a `┃`-gutter box; its positive anchor must be the
      `╹▀▀▀…` **bottom border** plus the composer status row
      (`Build · <model> · <effort>`);
    - the permission dialog **replaces** that box (so the positive half excludes
      it, exactly as for Codex) — but the dialog is *also* a `┃`-gutter box
      containing blank rows, so a naive "a blank `┃` row exists" rule
      false-positives and must be ruled out by a negative control;
    - the gray placeholder hint is **not** a durable readiness signal: it is
      present on a fresh session and **gone after the first turn**;
    - the working state is a blank composer plus an `⬝⬝⬝⬝ esc interrupt` footer,
      and there is **no SGR-dim styling** anywhere in the composer, so
      `_DIM_SPAN_RE` does not transfer;
    - `opencode` already has two live t1467 dialog patterns
      (`opencode_question`, `opencode_permission`) for the negative half;
    - measured against opencode 1.18.18 on 2026-08-14.

    **Acceptance criteria to state in the task:** an `opencode` entry in
    `SHADOW_READY_DETECTORS`; raw-ANSI fixtures for at-rest-fresh,
    at-rest-after-a-turn, typed, working and permission-dialog; an
    **isolated-positive-half** test proving the dialog is excluded with the
    pattern list disabled; the blank-`┃`-row negative control; the same
    post-dialog settle measurement and latch sizing as Phase 3b; and the arm
    refusal remaining reachable for whatever agent is still undetected.

24. Record the new task's id in this plan's Coordination section and in the
    Final Implementation Notes, so the handoff is traceable from the archive.

## Verification

**Required pre-ship conditions** (none of these may be deferred to the
manual-verification follow-up — the follow-up confirms the shipped guard in a
real session, it does not stand in for the evidence that sizes it):

1. **Post-interaction settle measured in seconds** (Pre-phase step 2): ≥ 5
   repetitions each for the permission dialog, the question widget, the startup
   update prompt and the no-work-follows answer, sampled at 0.25 s, with every
   raw number recorded in the Final Implementation Notes — and
   `SHADOW_SETTLE_SECONDS` set from the measured maximum rather than guessed.
2. **The latch is pinned by driven clock sequences** (step 19b), including all
   four of: the update-prompt end-to-end sequence, the `SHADOW_DIALOG`
   classification of the update prompt, the wedge negative control, and the
   **two-cadence** run. A tick-counted or pattern-match-armed implementation
   must fail these.
3. **The OpenCode sibling exists** (Phase 6) with its id recorded here.
4. **The arm refusal is still reachable** and still names the agent — proven by
   a test, not by inspection.

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

- **OpenCode sibling follow-up** — created by **Phase 6 step 23** (an
  implementation step, not a promise), carrying the measured gutter /
  bottom-border evidence and its own acceptance criteria. Its id is recorded
  here at step 24: `t____` (filled in at implementation time).
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

- Phase 1's `agent_key_from_pane` lookup runs `pgrep` + `ps`, each bounded at
  2 s, on a cache miss. Left on the Textual event loop it can freeze the UI and
  stall armed-loop evidence ticks for ~4 s; moved off it, the new suspension
  point can let a stale result act on a superseded lifecycle ·
  severity: medium · → mitigation: none spawned (closed in-plan by Phase 1
  step 6 — `asyncio.to_thread` plus generation guards at both call sites, pinned
  by test step 19c)

### Goal-achievement risk: medium
- The Codex composer/working regexes are pinned to codex-cli 0.146.0 and the
  pane itself already advertises 0.147.0; a UI change makes readiness
  permanently `False`. The failure direction is fail-safe (the loop holds and
  never injects), but it is **silent** — indistinguishable from a shadow that is
  simply busy · severity: low · → mitigation: surface_never_settled_shadow
- **[raised to high in review]** After a Codex interaction is answered the pane
  shows an empty composer with no working indicator for a window measured at
  **≥ 2 s**, while committed evidence ticks run every **1.5 s** (and as little as
  **1.0 s** at `--interval 1`/`2`) and `hash_stable` needs only two identical
  captures. The loop can therefore fire its prompt + Enter into a shadow that has
  not resumed work — the safety failure the feature exists to prevent. Not
  outside the requirement, as the first draft claimed ·
  severity: high · → mitigation: inline pre-phase measure_post_dialog_settle
  (sizes it in seconds) + Phase 3b wall-clock settle latch (closes it)
- **[added in review round 2]** Two ways the Phase 3b guard could be built such
  that it *looks* closed but is not: arming it from a prompt-pattern match
  (which never fires for Codex's un-patterned startup update prompt) or counting
  evidence ticks (which under-covers at any configured refresh below the
  default, since the cadence floors at 1.0 s while the constant would be sized
  at 1.5 s) · severity: medium · → mitigation: none spawned — closed in-plan by
  Phase 3b's structural arming predicate and monotonic deadline, each pinned by
  a test in step 19b that a naive implementation fails

### Planned mitigations
- timing: pre-phase | name: pin_shadow_seam_consumers | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (shadow-seam tuple widening / missed unpack site) | desc: Characterize every consumer's unpack path against the unmodified helpers before widening them, so a missed call site fails a test instead of a live minimonitor tick.
- timing: pre-phase | name: measure_post_dialog_settle | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk 2 (post-interaction settle window, raised to high in review) | desc: Measure the post-interaction empty-composer window live in wall-clock seconds at 0.25s sampling over at least five repetitions per interaction kind (permission, question widget, un-patterned update prompt, no-work-follows answer), and size SHADOW_SETTLE_SECONDS from the measured maximum rather than a guess.
- timing: after | name: surface_never_settled_shadow | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement risk 1 (silent composer-pattern drift across a Codex release) | desc: When the loop is armed and the shadow never reads ready for N consecutive ticks, surface a banner hint that its composer pattern may need re-pinning, turning a silent fail-safe hold into a legible signal.

**Reassessment after inlining and after the review round**
(`risk-evaluation.md` Step 3 note): code-health stays **medium** — the
characterization test closes the missed-unpack path and Phase 1 step 6 closes
the event-loop blocking, but the seam's blast radius and the Phase 2 semantic
change are unchanged, and Phase 3b adds new latch state to an already-subtle
controller. Goal-achievement moves **low → medium**: the review surfaced a
reachable injection window the first draft had dismissed, which is evidence the
plan's own safety reasoning needed correction; it is now closed structurally
(Phase 3b) and gated on measurement (Pre-phase step 2), but the correction
itself is the reason the level is no longer `low`.
