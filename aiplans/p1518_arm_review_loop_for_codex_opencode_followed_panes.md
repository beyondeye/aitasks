---
Task: t1518_arm_review_loop_for_codex_opencode_followed_panes.md
Worktree: (none — current-branch mode, profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1518 — Arm the review loop for Codex / OpenCode followed panes

## Context

The minimonitor auto-recheck loop (`L`) injects a recheck line into the **shadow**
pane once the **followed** agent has produced work and settled. t1509/t1520 closed
the *shadow* half: all three agents now have readiness detectors. The *followed*
half is still Claude-only, and deliberately so — `review_loop.REVIEW_LOOP_AGENTS`
is `("claude",)` because a loop that injects keystrokes must earn each agent with
its own live evidence, separately from `workflow_phase.live_tiers_available`
(which t1467 already made true for Codex and OpenCode).

Two things block widening:

1. **`NATIVE_DIALOG_BOUNDARIES` holds exactly one row** — `("claude",
   "claude_plan_approval")`. A Codex or OpenCode followed pane parked at
   `codex_permission` / `codex_yes_proceed` / `opencode_permission` falls through
   `classify_followed_change`'s conservative tail and classifies **every** content
   change as `UNKNOWN`, which never satisfies the work latch and never resets it.
   Safe but under-detecting.
2. **No live evidence** that arming is safe for either agent.

Intended outcome: Codex and OpenCode followed panes can arm the loop, each backed
by its own live evidence; an agent whose evidence does not hold stays out and the
arm refusal stays reachable and accurate for it.

## What already exists — do NOT rebuild

- `workflow_phase.QUESTION_BLOCK_BOUNDARIES["codex"]` (the `Question N/M` header),
  `QUESTION_BLOCK_STRATEGIES["opencode"]` (contiguous `┃`-gutter scan) and
  `QUESTION_WIDGET_KINDS` for both — t1467. `classify_followed_change` already
  threads the agent into `current_question_block`, so the `SELECTION_ONLY` path
  works today for both agents' **question widgets**. Only the **native dialog**
  path is missing.
- Prompt patterns `codex_permission`, `codex_yes_proceed`, `opencode_permission`,
  `opencode_palette` — `monitor/prompt_patterns.py`.
- Two-rung identity resolution `agent_keys.agent_key_from_pane` — t1509.
- Shadow-side detectors for all three agents — `SHADOW_READY_DETECTORS`.
- **Live captures already in the tree**: `tests/review_loop_fixtures.py` holds
  `CODEX_PERMISSION_RAW`, `CODEX_PERMISSION_WITH_RUNNING_RAW` and
  `OPENCODE_PERMISSION_RAW`, and both t1467 boundary candidates are already
  visible in them at the predicted geometry (Codex `Would you like to run the
  following command?` at distance 13; OpenCode `△ Permission required` at 10).
  These are single frames, not selection pairs — they corroborate the geometry
  but do not discharge the measurement.
- The measurement **recipe** — `aidocs/framework/shadow_agent.md` §"Recipe:
  measuring a new agent's readiness surfaces" (lines 820–866). Follow it; do not
  re-derive it. Its harness is scratchpad-only **by standing decision** (t1520)
  — do not commit the driver.

---

### Pre-phase (risk mitigations)

1. `[gate_code_on_measured_boundaries]` **The durable artifact is the checked-in
   plan `aiplans/p1518_arm_review_loop_for_codex_opencode_followed_panes.md`** —
   not the agent-private plan file, which is transient and unreviewable. Step 1's
   measurement table goes into that file's `## Measurement` section, with an
   explicit **B1 / B2 / B3 verdict per (agent, kind) candidate**, and is
   **committed before the first code edit**:

   ```bash
   ./ait git add aiplans/p1518_arm_review_loop_for_codex_opencode_followed_panes.md
   ./ait git commit -m "ait: Record t1518 boundary measurement table"
   ```

   The ordering is then provable from git history — the plan commit precedes the
   `feature: … (t1518)` code commit — rather than from a transient working-tree
   observation. Apply the gate against that committed table: a candidate with any
   verdict other than pass ships **no** `NATIVE_DIALOG_BOUNDARIES` row (nor
   strategy entry), and its agent is not added to `REVIEW_LOOP_AGENTS`. Verify:

   - `git log --oneline -- aiplans/p1518_*.md .aitask-scripts/monitor/review_loop.py`
     shows the measurement commit strictly before any `review_loop.py` commit;
   - `git show <measurement-commit>:aiplans/p1518_*.md` contains a verdict row for
     every (agent, kind) pair that ends up in the shipped tables, and every shipped
     entry maps 1:1 onto a **passing** verdict in that committed table.

   If Step 6's externalization has not yet produced `aiplans/p1518_*.md` when the
   measurement finishes, write the file first (naming + metadata header per
   `planning.md` §"Save Plan to External File"), then commit — the artifact must
   exist and be committed before the gate can be discharged.

---

## Step 1 — Live measurement (scratchpad harness, real agents)

Per the recipe: private socket `AITASKS_TMUX_SOCKET=t1518meas_$$` (**never** the
`-L ait` gateway), `TMUX`/`TMUX_PANE` scrubbed, 120x30, throwaway repo under the
scratchpad, capture with the production argv verbatim
(`capture-pane -p -e -t <pane> -S -15`) piped through `ansi_utils.strip_ansi`.
Set `AITASKS_TMUX_SOCKET` **before** importing `monitor.monitor_core` (it is
resolved once at import). Codex needs its boot interstitial dismissed; the others
must not be sent a stray Enter.

Provoke cheap dialogs (a `printf > out.txt` exec approval for Codex; a
touch-outside-cwd permission for OpenCode) so turn cost stays modest.

Per **(agent, dialog)**, ≥5 repetitions, capture at least: at-rest, working,
dialog-selection-state-1, dialog-selection-state-2, and dialog-with-new-output-
above. Answer three questions per candidate boundary line:

- **B1 — exactly once.** The line matches exactly once in the live capture.
  (`_boundary_index` takes the *last* match, so a stale echo higher in the tail is
  tolerated by construction; B1 is about the live frame.)
- **B2 — only while live.** The line is absent from the at-rest and working
  captures of the same repetition.
- **B3 — always above the change.** Its index is strictly less than the index of
  every line that differs between selection state 1 and 2.

Also record, for the **question widget** of each agent (the `SELECTION_ONLY` path
t1467 already shipped): a selection pair and an output-above pair, so the safety
bar's second observation has captured evidence behind it as well.

**Candidate boundaries to confirm — re-measure, do not copy on faith:**

One row **per (agent, kind)**, not per dialog — the pre-phase gate requires a 1:1
mapping from shipped entry to passing verdict, so a shared boundary still needs a
verdict recorded under each kind that will carry it:

| agent | kind | candidate line |
|---|---|---|
| codex | `codex_permission` | `Would you like to run the following command?` |
| codex | `codex_yes_proceed` | `Would you like to run the following command?` (same dialog) |
| opencode | `opencode_permission` | `△ Permission required` (or the gutter-run top — see the branch rule) |

`codex_permission` and `codex_yes_proceed` are the **same** exec-approval dialog
anchored at two distances (footer at 1, option row at 5); which kind is reported
depends on whether the footer scrolled out — `CODEX_PERMISSION_WITH_RUNNING_RAW`
is a live capture of exactly that. Both kinds therefore share one boundary regex.

**OpenCode decision rule (settled by measurement, not by preference).** OpenCode
renders its permission dialog inside a `┃`-gutter block, so there are two viable
boundaries: the `Permission required` phrase (distance 10), or the structural top
of the contiguous gutter run (distance 11) that `workflow_phase._opencode_block_start`
already computes. t1467's own guidance prefers structural geometry to a quotable
phrase.

**Rule — exactly one of the two mechanisms carries the `("opencode",
"opencode_permission")` key**, decided by the measurement, never both. Note the
scope carefully: the branch decides which table holds the **entry**, not which
symbols exist. Both tables are defined unconditionally (see Step 2a) — a module
whose shape depends on a measurement outcome would make the precedence lookup a
`NameError` on one branch and force callers into `globals().get` crutches.

- **Phrase branch** — take it if B1–B3 all hold against `Permission required`,
  i.e. no line between the gutter top and the phrase line changes across selection
  states. The entry goes in `NATIVE_DIALOG_BOUNDARIES`;
  `NATIVE_DIALOG_STRATEGIES` is defined and holds no OpenCode entry.
- **Structural branch** — take it if any such line changes (B3 fails for the
  phrase) while the gutter-run top holds. The entry goes in
  `NATIVE_DIALOG_STRATEGIES`; no `NATIVE_DIALOG_BOUNDARIES` row is added for
  `("opencode", "opencode_permission")`.

Record which branch the evidence selected, and the per-line diff that decided it,
in the `## Measurement` table.

Record the resulting table (agent, kind, line, distance, B1/B2/B3 verdicts, CLI
version, and the OpenCode branch selected) in a `## Measurement` section of
`aiplans/p1518_*.md`, as t1509/t1520/t1525 did — see the pre-phase gate for the
commit that discharges it.

## Step 2 — Boundary rows (`.aitask-scripts/monitor/review_loop.py`)

Add entries **only** for pairs that passed B1–B3, with a provenance comment naming
the CLI version and capture date (the existing habit for version-sensitive TUI
text):

```python
# Codex's exec-approval dialog. `codex_permission` (footer, distance 1) and
# `codex_yes_proceed` (option row, distance 5) are the SAME dialog anchored at
# two distances — which kind is reported depends on whether the footer scrolled
# out — so both map to one boundary. Live codex-cli 0.146.0 capture, <date>.
_CODEX_EXEC_APPROVAL_RE = re.compile(r"Would you like to run the following command\?")

NATIVE_DIALOG_BOUNDARIES: dict[tuple[str, str], re.Pattern] = {
    ("claude", "claude_plan_approval"): ...,          # unchanged
    ("codex", "codex_permission"): _CODEX_EXEC_APPROVAL_RE,
    ("codex", "codex_yes_proceed"): _CODEX_EXEC_APPROVAL_RE,
    # ("opencode", "opencode_permission"): only on the phrase branch — see below
}
```

### 2a — `NATIVE_DIALOG_STRATEGIES` (defined in **both** variants)

Add the second mechanism **exactly mirroring `workflow_phase`'s proven two-table
idiom**, so the contract is not invented here. The **symbol and the lookup are
unconditional**; only the OpenCode entry is branch-dependent:

```python
# Native dialogs delimited by SHAPE rather than by a header line, keyed like
# NATIVE_DIALOG_BOUNDARIES. Same split, and for the same reason, as
# workflow_phase.QUESTION_BLOCK_BOUNDARIES / QUESTION_BLOCK_STRATEGIES: a regex
# matching OpenCode's gutter glyph alone would match EVERY line of the block,
# including an earlier already-answered one higher in the tail.
#
# Defined even when empty. `classify_followed_change` consults it before the
# regex table on every native-dialog kind, so a conditionally-defined symbol
# would be a NameError on one branch and force callers into `globals().get`.
NATIVE_DIALOG_STRATEGIES: dict[tuple[str, str], Callable[[list[str]], int | None]] = {
    # structural branch only:
    # ("opencode", "opencode_permission"): workflow_phase._opencode_block_start,
}
```

**Contract — pinned, not implied:**

- **Signature** `Callable[[list[str]], int | None]`: takes the ANSI-stripped
  `splitlines()` of one capture, returns the index of the line that *starts* the
  live dialog block, or `None` when it cannot be located. Identical to
  `workflow_phase.current_question_block`'s strategy contract.
- **Precedence: strategy first, regex second** — the same order
  `current_question_block` uses (`workflow_phase.py:408-418`). In
  `classify_followed_change`, look up `NATIVE_DIALOG_STRATEGIES` before
  `NATIVE_DIALOG_BOUNDARIES`; a hit in either resolves the kind, a miss in both
  falls through to the conservative `UNKNOWN`. This lookup is written **once,
  unconditionally** — on the phrase branch it is a live miss followed by a regex
  hit, which is an exercised path, not a dead one.
- **`None` from a strategy means `UNKNOWN`**, exactly as `start_prev is None or
  start_curr is None` already does on the regex path — never a guess, never a
  default index.
- **Reuse, do not reimplement:** the callable *is*
  `workflow_phase._opencode_block_start`. Do not fork the gutter scan; if it needs
  to become public, rename it there and update `QUESTION_BLOCK_STRATEGIES` in the
  same edit so there remains one implementation.

Both `_boundary_index` and the strategy return an index into the same line list,
so the `prev_lines[:start_prev] != curr_lines[:start_curr]` comparison that
follows is shared verbatim between the two paths — factor the shared tail rather
than duplicating it.

**The conservative fallthrough is not touched.** `classify_followed_change`'s
final `return UNKNOWN` stays exactly as it is — it is the reason an unmapped
dialog cannot misfire, and it must survive this task.

### 2b — Record deliberate non-coverage as data, not as omission

An unmapped kind is currently indistinguishable from a forgotten one, which is
precisely what lets a deleted row pass unnoticed. Add a third table making the
absence a **property of the table** (the argument `workflow_phase.NATIVE_KIND_PHASE`
already makes for its empty rows):

```python
# (agent, kind) pairs that deliberately have NO boundary, with the reason.
# Consumed by the completeness guard in tests/test_review_loop.py: a kind that
# is in neither strategy table and not listed here is an OMISSION and fails.
# Keyed per AGENT, including for kinds that come from the cross-agent
# PROMPT_PATTERNS_BY_AGENT["all"] group — a generic prompt can need a different
# boundary per agent, so it is resolved or exempted once per armed agent.
DELIBERATELY_UNANCHORED_KINDS: dict[tuple[str, str], str] = {
    ("opencode", "opencode_palette"):
        "overlay; renders ~21 lines up, outside _PROMPT_DETECTION_TAIL_LINES, so "
        "it is never a followed-pane awaiting_input_kind (t1520)",
    ("claude", "claude_trust_folder"): "no measured boundary (pre-t1518)",
    ("claude", "claude_proceed"): "no measured boundary (pre-t1518)",
    ("claude", "claude_help_bar"): "no measured boundary (pre-t1518)",
}
```

The three Claude entries record **existing** under-detection — a Claude pane
parked at a tool-permission dialog classifies `UNKNOWN` today, the same gap this
task closes for Codex. That is a pre-existing finding, not this task's scope;
record it verbatim in the plan's "Upstream defects identified" bullet at Step 8 so
Step 8b can offer it as a follow-up. Do **not** fix it here.

## Step 3 — Widen the gate and fix the refusal wording

- `REVIEW_LOOP_AGENTS` — add each agent whose Step 5 safety bar passed, one at a
  time. Update the constant's comment to say what earned each entry.
- `minimonitor_app.action_toggle_review_loop` — the refusal currently hardcodes
  `"the recheck loop is Claude-only for now"`, which becomes false the moment the
  tuple widens. **Derive it from the tuple** so it cannot drift:

  ```python
  supported = ", ".join(review_loop.REVIEW_LOOP_AGENTS)
  self.notify(
      f"Auto-recheck unavailable for '{snap.pane.current_command or 'unknown'}' — "
      f"the recheck loop supports {supported}",
      severity="warning")
  ```

  The invariant the existing test pins — the refusal names the refused agent — is
  preserved. Update the branch's comment, which currently explains why Codex and
  OpenCode are excluded.

## Step 4 — Unit tests (`tests/test_review_loop.py`, `tests/review_loop_fixtures.py`)

Add the new live captures to `review_loop_fixtures.py` with a provenance docstring
paragraph in the module header (agent, CLI version, date, socket, geometry, and
what the trim extent is), following the `CODEX_*` / `OPENCODE_*` precedent. Store
at the extent production actually reads — do **not** copy the `CODEX_*` trim-to-15
habit onto OpenCode; it was measured to drop a load-bearing row.

Extend the existing classes (do not duplicate them):

- `PerAgentBlockBoundaryTests` — add, per agent and per native dialog, **both
  directions** over the real captures:
  - selection-state pair → `SELECTION_ONLY`
  - new output above the boundary → `WORK`
  - `codex_yes_proceed` classifies identically to `codex_permission` (shared row)
- **OpenCode branch coverage — pinned to the branch actually shipped**, so the
  mechanism cannot be a nominal table that is never reached. Assertions are about
  the **entry**, never about whether the symbol exists — both tables are always
  defined, so a symbol-existence test would assert the wrong thing and would break
  the moment the other branch was chosen:
  - a premise assertion that exactly one mechanism carries
    `("opencode", "opencode_permission")` — in `NATIVE_DIALOG_BOUNDARIES` xor in
    `NATIVE_DIALOG_STRATEGIES` — which fails if both or neither hold it;
  - **on the structural branch**: a test forcing that path and proving both
    directions through it — selection movement inside the gutter block →
    `SELECTION_ONLY`, output above the gutter top → `WORK` — plus its negative
    control (replace the strategy with one returning `None`, assert `UNKNOWN`,
    proving the strategy and not the regex fallback classified);
  - **on the phrase branch**: the same two directions through the regex path, plus
    an assertion that `NATIVE_DIALOG_STRATEGIES` holds **no OpenCode entry**
    (`("opencode", "opencode_permission") not in rl.NATIVE_DIALOG_STRATEGIES`).
- **The strategy mechanism is proven live on either branch.** On the phrase branch
  the callable arm of the lookup is never taken by shipped data, which would leave
  it unexercised. Cover it directly: a test that inserts a synthetic
  `("opencode", "<synthetic_kind>")` strategy, drives a change under that kind, and
  asserts the callable's index — not the regex table — decided `SELECTION_ONLY` /
  `WORK`. This runs on **both** branches, so the precedence contract in Step 2a is
  pinned by execution regardless of which branch the measurement selected.
- **The conservative default survives** (explicit, its own test):
  - `("opencode", "opencode_palette")` is in neither strategy table, and a change
    under that kind classifies `UNKNOWN`
  - `claude_trust_folder` still `UNKNOWN` (the existing case, kept)
  - every `DELIBERATELY_UNANCHORED_KINDS` entry carries a non-empty reason string
- `ReviewLoopAgentSupportTests` — replace `test_wired_agents_are_still_not_loop_supported`
  with the new truth table: each widened agent True, each agent still without
  evidence False, unknown/empty/synthetic keys False. Keep
  `test_predicate_matches_its_constant`.
- **New completeness guard — total over every kind an armed agent can report.**
  A weaker "the agent has *some* strategy" guard is useless here: Codex and
  OpenCode already satisfy the question-widget half from t1467, so such a guard
  stays green while a permission-dialog entry is omitted or later deleted, and the
  loop arms while classifying that dialog `UNKNOWN` — exactly the gap this task
  closes. The invariant must therefore be **total**:

  ```python
  def test_every_armed_agent_kind_resolves(self):
      """For each agent the loop may arm, EVERY awaiting-input kind prompt
      matching can report for it must resolve to a strategy — or be explicitly
      recorded as deliberately unanchored, with a reason."""
      for agent in rl.REVIEW_LOOP_AGENTS:
          # Derived from the PRODUCTION seam, not reassembled by hand:
          # `TmuxMonitor` defaults its pattern list to `all_patterns()`
          # (monitor_core.py:1481) and `classify_content` narrows it with
          # `scope_patterns`, which is SUBTRACTIVE and deliberately retains the
          # `"all"` group for every resolved agent (prompt_patterns.py:229-232).
          # Rebuilding the union here would silently exclude that group.
          kinds = {p.name
                   for p in pp.scope_patterns(pp.all_patterns(), agent)}
          self.assertTrue(kinds, f"{agent} has no reportable prompt kinds")
          for kind in kinds:
              resolved = (
                  kind in wp.QUESTION_WIDGET_KINDS.get(agent, ())
                  or (agent, kind) in rl.NATIVE_DIALOG_BOUNDARIES
                  or (agent, kind) in rl.NATIVE_DIALOG_STRATEGIES
                  or (agent, kind) in rl.DELIBERATELY_UNANCHORED_KINDS)
              self.assertTrue(resolved, (
                  f"{agent}/{kind} resolves to no boundary strategy and is not "
                  f"in DELIBERATELY_UNANCHORED_KINDS — an armed agent's dialog "
                  f"would classify UNKNOWN"))
  ```

  **The kind set must come from `scope_patterns(all_patterns(), agent)`, not from
  `PROMPT_PATTERNS_BY_AGENT[agent]`.** The two differ exactly on the `"all"`
  group — empty today, but documented as the place generic cross-agent prompts go.
  A pattern added there becomes reportable for *every* agent, so a guard keyed on
  the agent group alone would stay green while a Codex or OpenCode pane reports a
  kind that falls straight through to `UNKNOWN`. Deriving from the production seam
  also means the guard follows automatically if `scope_patterns`' retention rule
  ever changes, instead of drifting from it.

  Exemptions and strategies stay keyed by **`(agent, kind)`** even for an `"all"`
  kind — a generic prompt can legitimately need a different boundary per agent, so
  a generic kind must be resolved (or exempted) once per armed agent rather than
  globally. Note that consequence beside `DELIBERATELY_UNANCHORED_KINDS`.

  Deleting a boundary row no longer passes: the kind falls into none of the four
  buckets. Re-listing it under `DELIBERATELY_UNANCHORED_KINDS` still lets it
  through — deliberately: that is a reviewable edit carrying a written reason, not
  a silent omission.

- **Negative controls for the guard** (each must fail, and fail for the right
  reason — a passing negative control is itself a defect; mutate values in-test,
  never delete source lines, so the failure is an assertion and not a
  `NameError`/`KeyError`):
  - drop `("codex", "codex_permission")` from the shipped mapping; assert the
    guard fails naming `codex/codex_permission`.
  - add a synthetic agent to `REVIEW_LOOP_AGENTS` with prompt patterns but no
    strategies; assert the guard fails naming it.
  - **generic-pattern control (pins the `"all"` derivation):** append a synthetic
    `PromptPattern("synthetic_generic_prompt", …)` to
    `PROMPT_PATTERNS_BY_AGENT["all"]` and assert the guard fails **for every**
    agent in `REVIEW_LOOP_AGENTS`, naming that kind. This is the control that
    fails if the kind set is ever narrowed back to the agent group — the guard
    would go green under the mutation, which is the defect. Then assert it passes
    once the kind is exempted for each armed agent, proving the exemption path is
    the intended escape and not an accident.

`tests/test_minimonitor_concern_action.py`:

- Retarget `test_refuses_followed_agent_the_loop_does_not_support` onto a
  **synthetic** unsupported agent key (the shape t1520 used for
  `test_refuses_shadow_agent_without_detector_naming_it` via `_UNDETECTED_KEY`),
  asserting it is genuinely absent from `REVIEW_LOOP_AGENTS` as a premise, that
  the refusal fires, and that it names the agent. Do not delete it — the refusal
  must stay reachable for a future agent wired ahead of its evidence.
- `test_refuses_unresolvable_followed_pane` (the real `node` case) is unchanged
  and stays as the real-agent-shaped refusal.
- **New positive control:** a followed pane for each newly-supported agent **arms**
  — the counterpart the refusal test cannot prove.

## Step 5 — Live acceptance

**5a — checked-in live-tmux test.** Add a class to
`tests/test_minimonitor_concern_smoke.py` (reusing its per-PID socket and
isolation scaffolding rather than duplicating ~100 lines): real tmux panes whose
`pane_current_command` is `codex` / `opencode`, painted with the **real captured
frames** from Step 1, driven through the real `action_toggle_review_loop` and
`_service_review_loop` and the real capture path. Assert: arming succeeds; a
selection-only transition fires **nothing**; a work-above-boundary transition
followed by a settled shadow fires **exactly one** round. No TUI boot, so it stays
in the parallel lane (it must not need the serial carve-out).

**5b — the three live observations the task requires, per agent** (real Codex /
OpenCode agent, real minimonitor, real shadow, private socket). Record verbatim
in the plan's `## Measurement` section:

1. the loop arms with that agent as the **followed** pane and fires exactly one
   automatic round;
2. pure option-cursor movement inside its question widget fires **nothing**;
3. the same for its native dialog, once the boundary row exists.

An agent whose observations do not reproduce **stays out of the tuple**, its
boundary row is still shipped (it is independently correct and reduces
under-detection), and the shortfall is reported explicitly rather than quietly
scoped away.

## Step 6 — Documentation

- `aidocs/framework/shadow_agent.md` — the "**Phase available ≠ recheck loop
  armable**" paragraph (~line 994) says Codex and OpenCode "deliberately" do not
  satisfy the second predicate and that widening is its own task. Rewrite to the
  post-t1518 state: which agents are armable and what earned them, keeping the
  distinction between the two predicates (it is still real for a future agent).
- `website/content/docs/tuis/minimonitor/how-to.md:247` — "The **followed** agent
  must be Claude Code … refuses with `the recheck loop is Claude-only for now`"
  is user-facing and quotes the exact refusal string. Update both the claim and
  the quoted string to match Step 3.
- Note the two-mechanism split beside the `NATIVE_DIALOG_BOUNDARIES` docstring,
  mirroring `workflow_phase.py`'s comment — including *why*
  `NATIVE_DIALOG_STRATEGIES` is defined even when empty (the lookup is
  unconditional), and which branch the measurement selected for OpenCode.
- `aidocs/framework/shadow_agent.md` — document `DELIBERATELY_UNANCHORED_KINDS`
  and the completeness guard beside the per-agent availability table, so the rule
  "an armed agent's every kind resolves, or is exempted with a reason" is stated
  where a future agent's author will look. Memory says a narrow source-scan guard
  needs a bidirectional doc↔module reference: name the guard's test in the doc and
  the doc in the table's comment.

## Verification

- `python3 tests/test_review_loop.py` — boundary entries both directions per agent
  per dialog; the OpenCode branch pinned by the xor premise and exercised through
  the mechanism actually shipped; conservative-`UNKNOWN` default asserted
  explicitly; truth table; the total completeness guard.
- `python3 tests/test_minimonitor_concern_action.py` — refusal retargeted and
  still reachable; positive-control arm for each widened agent.
- `python3 tests/test_minimonitor_concern_smoke.py` — live 5a acceptance.
- `bash tests/run_all_python_tests.sh` — **read the final stderr verdict line
  only** (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); an earlier
  `Results: N passed` line belongs to one module. Use `set -o pipefail` if piping.
- **Negative controls — each must fail, with the named failing test id recorded,
  and each mutation applied in isolation** (a passing negative control is itself a
  defect; mutate values in-test rather than deleting source lines, so the failure
  is an assertion and not a `NameError`/`KeyError`):
  1. neuter a boundary regex → the selection-only test fails on
     `SELECTION_ONLY` vs `UNKNOWN`;
  2. drop `("codex", "codex_permission")` from the shipped mapping → the
     completeness guard fails, naming `codex/codex_permission`;
  3. add a synthetic agent to `REVIEW_LOOP_AGENTS` with prompt patterns but no
     strategies → the completeness guard fails, naming it;
  4. append a synthetic pattern to `PROMPT_PATTERNS_BY_AGENT["all"]` → the
     completeness guard fails for **every** armed agent, naming that kind (this
     is the control that catches the guard's kind set being narrowed back to the
     per-agent group);
  5. replace the synthetic-kind strategy with one returning `None` → the
     strategy-mechanism test fails on `UNKNOWN`, proving the callable and not a
     regex fallback did the classifying (runs on both branches; on the structural
     branch apply the same mutation to the real OpenCode strategy as well).
- Ordering gate discharged: `git log` shows the `## Measurement` plan commit
  strictly before any `review_loop.py` commit, and every shipped entry maps onto a
  passing verdict in that committed table (pre-phase step 1).
- Live 5b observations recorded in `aiplans/p1518_*.md`.
- `shellcheck` — not applicable (no shell changes).

## Risk

### Code-health risk: low

- Adds **version-sensitive TUI literals** to a safety-relevant classification
  path. Codex/OpenCode UI churn rots them, and the failure is *silent in
  production*: a boundary that stops anchoring returns `UNKNOWN`, so the loop
  simply never fires, while the tests keep passing against the old stored fixture.
  Widening from one agent to three triples that surface · severity: medium ·
  → mitigation: t1542
- Everything else is contained: the change is additive and table-driven in an
  established idiom, the conservative `UNKNOWN` fallthrough is untouched (and
  becomes explicitly asserted rather than merely present), and the refusal string
  stops being a literal that can drift from the tuple · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: medium

- A boundary candidate may fail B1–B3 for an agent, so the plan would otherwise
  ship an unmeasured literal. OpenCode is the likelier of the two — its dialog
  reflows a right-hand status column into the same physical lines, which is why
  its prompt patterns already had to tolerate trailing content · severity:
  medium · → mitigation: inline pre-phase gate_code_on_measured_boundaries
- The 5b observation "arms and fires exactly one round" needs a genuine
  work→settle cycle **plus** a ready shadow, and may not reproduce on demand.
  t1509 measured **zero** injectable windows for a Codex *shadow* across 15
  repetitions — that is the other end of the loop, and `SHADOW_SETTLE_SECONDS`
  exists to cover it, but it is direct evidence that these live cycles are not
  reliably reproducible · severity: medium · → mitigation: none needed (already a
  plan step — the 5a checked-in live test; an agent whose 5b evidence does not
  hold stays out of the tuple and the shortfall is reported)
- Both CLIs must stay authenticated and within quota for the session ·
  severity: low · → mitigation: none needed (pre-registered fallback, t1467:
  record the refusal verbatim, ship only what the evidence supports, do not infer
  geometry)
- A future widening could land with a *partial* strategy set — the armable agent
  has its question widget covered but its permission dialog omitted or later
  deleted, so the loop arms and classifies that dialog `UNKNOWN`, re-opening this
  task's own gap · severity: medium · → mitigation: none needed (already a plan
  step — the **total** completeness guard in Step 4, keyed off
  `PROMPT_PATTERNS_BY_AGENT` with an explicit reasoned exemption table, plus its
  two negative controls)

### Planned mitigations
- timing: pre-phase | name: gate_code_on_measured_boundaries | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — shipping an unmeasured, version-sensitive boundary literal | desc: no line of review_loop.py is edited until Step 1's B1/B2/B3 table is recorded in the plan, and every shipped row maps 1:1 onto a passing verdict
- timing: after | name: boundary_anchor_failure_is_observable | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: code-health — silent rot of a native-dialog boundary literal, whose surface triples when the agent set widens | desc: surface a native-dialog boundary that has stopped anchoring, so literal rot is an observable signal instead of a loop that silently never fires | created: t1542

**Reassessment after inlining** (`risk-evaluation.md` Steps 1–2, re-run against the
augmented plan): the pre-phase gate is a bounded, independently-verifiable
ordering constraint — it adds no code and no blast radius, so **code-health stays
`low`**. It removes the "unmeasured literal" path but not the live-reproduction
risk, which is the dominant one, so **goal-achievement stays `medium`**.

## Step 9 reference

Post-implementation (merge into `main`, gate run, archival) follows the shared
task-workflow Step 9. The task's active gate set is `risk_evaluated`, materialized
at claim time; the Step-9 orchestrator records it, so planning does **not**
self-record it.

---

## Measurement

Executed **2026-08-17**, per the recipe in `aidocs/framework/shadow_agent.md`
§"Recipe: measuring a new agent's readiness surfaces". Private tmux socket
`t1518meas_1668172` (never the `-L ait` gateway), `TMUX`/`TMUX_PANE` scrubbed,
120x30 panes, throwaway repo under the session scratchpad. Captures taken with
the production argv verbatim (`capture-pane -p -e -t <pane> -S -200`) and
classified through the production seams (`monitor_core.classify_content` for the
kind, `review_loop.classify_followed_change` for the verdict).
Versions: **codex-cli 0.146.0** (gpt-5.6-terra high), **OpenCode 1.18.18**
(GPT-5.4). Harness is scratchpad-only and not committed (t1520 standing
decision).

**Three channels per frame** (recipe step 4). (A) harness ground truth — the
driver knows which frame is at-rest / working / dialog-sel1 / dialog-sel2, and
for every selection step asserts the **raw** capture changed before accepting the
frame; (B) literal screen evidence — plain substring searches, not the shipped
regexes; (C) the detector's own verdict. **No channel disagreement was observed
in any accepted rep.**

### Verdicts — one row per (agent, kind)

| agent | kind | candidate boundary line | index | B1 exactly-once | B2 only-while-live | B3 above-the-change | reps |
|---|---|---|---|---|---|---|---|
| codex | `codex_permission` | `Would you like to run the following command?` | −13 | **pass** | **pass** | **pass** | 5/5 |
| codex | `codex_yes_proceed` | *(same line, same dialog)* | −13 | **pass** | **pass** | **pass** | see note |
| opencode | `opencode_permission` | `△ Permission required` | −11 | **pass** | **pass** | **vacuous** | 5/5 |

Totals across **every** capture taken, not only the analysed reps:
codex 10 dialog frames / 15 non-dialog frames, **0 violations**;
opencode 12 dialog frames / 14 non-dialog frames, **0 violations**. "Violation"
= a dialog frame not containing the candidate exactly once (B1), or a
non-dialog frame containing it at all (B2).

### Codex — `codex_permission`

Provoked with a command **outside** the workspace sandbox
(`touch /home/ddt/t1518probe_<n>.txt`); an in-workspace write is auto-approved
and renders no dialog. Selection moved with `Down`.

- B1: exactly one match per live frame — **including at rep 6, whose transcript
  already held five resolved approval dialogs**. The header does not persist
  once the dialog closes, which is the strongest available form of B2.
- B3: the only lines differing between selection states are the option rows at
  −5 and −4 (the `›` cursor); the boundary sits at −13, strictly above both.
- Current behaviour **without** the row (positive control that the gap is real):
  the selection pair and the work pair both classify `unknown`.

### Codex — `codex_yes_proceed`: shipped, but not reachable on 0.146.0

`codex_yes_proceed` was **never** the reported kind across all 23 codex captures
— every dialog frame reported `codex_permission`. This is structural rather than
incidental: the dialog's footer (`Press enter to confirm or esc to cancel`,
distance 1) and its option row (`Yes, proceed (y)`, distance 5) are both inside
`_PROMPT_DETECTION_TAIL_LINES` (6), and matching is first-wins with
`codex_permission` listed first, so the footer always wins. t1467's expectation
that it "remains a real backstop when the footer scrolls" was a hypothesis about
a state, not an observation of one; nothing renders below that footer.

Disposition: **ship the row anyway**, mapped to the same boundary. B1/B2/B3 are
satisfied — they are properties of the dialog frame, which is identical — and
what is unconfirmed is only the kind's *reachability*. Shipping costs nothing and
classifies correctly if a future version does surface it; omitting it would mean
silently degrading to `UNKNOWN` in exactly that case. Recorded here so the entry
is not later mistaken for a measured-live kind.

### OpenCode — `opencode_permission`, and why B3 is vacuous

Provoked with `touch /home/ddt/t1518oc_<n>.txt` (outside the project directory).

**First attempt was invalid and was discarded.** `Tab` was sent to move the
selection on the strength of the widget's `⇆ select` hint; the raw capture came
back **byte-identical**, i.e. the key never registered (`tab` is globally bound
to "agents"). Had the ground-truth channel not been checked, the resulting
"stripped text unchanged" reading would have been recorded as a property of the
widget rather than as a dead keypress. `Right` is the key that moves it, and
every accepted rep asserts the raw frame changed first.

With a *valid* selection change:

- the **raw** capture changes (ground truth: selection moved);
- the **ANSI-stripped** capture is byte-identical — OpenCode renders the
  selection purely as styling.

`classify_followed_change` compares stripped content, so it returns `NO_CHANGE`
**before** any boundary is consulted. B3 is therefore *vacuously* satisfied —
there are no differing lines for the boundary to sit above — and is recorded as
`vacuous`, not as a pass. Measured verdict today, with no boundary row:
`none` (`NO_CHANGE`), which already never satisfies nor resets the work latch.

**The row is still needed, for the other direction.** Work performed *above* a
live permission dialog currently classifies `unknown` (measured on a pair of
dialog frames whose content above the boundary differs). That is the actual gap
for OpenCode; the selection direction was never the problem.

### OpenCode branch decision: **phrase**

The plan's decision rule was to prefer the structural gutter-run top if any line
between it and the phrase changes during selection. Measured: the gutter top is
at −12, the phrase at −11, so exactly one line (−12) lies between them, and it
does **not** change during selection (nothing does). The two mechanisms are
therefore *equivalent on the evidence*, and the rule selects the **phrase
branch** — the simpler mechanism, and no new entry in the strategy table.

Per the approved plan, `NATIVE_DIALOG_STRATEGIES` is still **defined** (empty of
OpenCode) so the precedence lookup in `classify_followed_change` is
unconditional.

### Safety-bar observation 2 — question widgets (live, per agent)

Pure option-cursor movement inside each agent's question widget, through the
path t1467 shipped and this task does not modify:

| agent | kind | key that moved it | raw changed | verdict |
|---|---|---|---|---|
| codex | `codex_question` | `Down` | yes | `selection_only` |
| opencode | `opencode_question` | `Down` | yes | `none` (`NO_CHANGE`) |

Neither is `WORK`, so neither can fire the loop. Confirmed live for both agents.

### Gate discharge

Every entry shipped in Step 2 maps 1:1 onto a **passing** verdict row above.
No candidate failed, so no agent is excluded on boundary grounds.

### Safety-bar observation 1 — arm and fire, live per agent

Real Codex / OpenCode process as the **followed** pane, a real Claude shadow
bound via `@aitask_shadow_target`, arming through the real
`MiniMonitorApp.action_toggle_review_loop` and firing through the real
`ReviewLoopController.tick`, with every tick's work signal classified from a
live `capture-pane` of the followed pane.

| agent | `pane_current_command` | resolved `agent_key` | armed | work ticks | parked at prompt | fires |
|---|---|---|---|---|---|---|
| codex | `node` | `codex` | **yes** | t001–t007 | t007 | **1** (t009) |
| opencode | `opencode` | `opencode` | **yes** | t001–t008 | t008 | **1** (t010) |

Both then held FIRED for the remainder of a 90-second window — one automatic
round, not a repeat. Arming emitted `Auto-recheck loop armed — press 'L' again
to disarm` in both cases.

The Codex row also exercises **rung 2** of `agent_keys.agent_key_from_pane`
live: its pane really does report `node` (the npm wrapper shape), so
command-only resolution would have answered `""` and the arm would have been
refused as unresolvable rather than granted.

Two harness findings worth recording, since both would have produced a
*silently wrong* result rather than an error:

- **A single long literal `send-keys` is coalesced by Codex.** A 78-character
  prompt reached the composer as `518arm.txt`, so the agent did unrelated work
  and never reached a dialog — indistinguishable, from the loop's side, from
  "the boundary does not work". Sending in 30-character chunks fixes it. This is
  the same coalescing t1525 measured for the shadow-side delivery; it applies to
  any driver typing into a Codex pane.
- **The composer must be verified non-empty before Enter.** A first OpenCode
  attempt submitted nothing at all and reported `fires=0`, which reads exactly
  like a failed observation. The driver now asserts `shadow_state == busy`
  pre-Enter, so a vanished send fails loudly instead of scoring as evidence.

### Verdict

Both agents satisfy all three safety-bar observations, so both are added to
`REVIEW_LOOP_AGENTS`. No agent was excluded.

---

## Post-review changes

### Change Request 1 (2026-08-17) — both concerns confirmed and fixed

**1. Misplaced test entry point (blocking).** `tests/test_minimonitor_concern_action.py`
carried `if __name__ == "__main__": unittest.main()` at **line 1095** of a
3100-line file. `unittest.main()` calls `sys.exit()`, so running the file
directly stopped the interpreter there and every class below was never defined —
`Ran 55 tests ... OK`, silently skipping 122 others including the entire
`ReviewLoopArmTests` class this task modified. Discovery-based runs
(`python3 -m unittest`, the suite runner) import the module rather than executing
it as `__main__`, which is why it had gone unnoticed.

I had found this and recorded it as an out-of-scope upstream defect. That was the
wrong call: it makes the plan's own verification command report green on a subset,
so it is this task's problem. The entry point is now at the true end of the file,
with a comment saying why it must stay there. `python3 tests/test_minimonitor_concern_action.py`
now reports **177 tests** and collects all four new arming tests.

**2. Step 5a did not exercise the application path (blocking).**
`FollowedPaneClassificationSmokeTests` drove real panes through the real capture,
but then called `classify_followed_change` and `ReviewLoopController.tick`
**directly** — so a defect in `action_toggle_review_loop`'s shadow lookup, in the
baseline `_service_review_loop` seeds and maintains, or in the fire/delivery
wiring would have left every new smoke test green. That is not what Step 5a
promised.

The class now also creates a **real shadow pane** per agent (the Claude-shaped
composer stub under a binary named `claude`, bound via `@aitask_shadow_target`)
and adds:

- `test_app_arms_and_fires_one_round_through_the_real_path` — for **both**
  Codex and OpenCode: arms via the real `action_toggle_review_loop` (real
  server-wide shadow lookup, real two-rung agent resolution, real readiness
  detection), services real snapshots through the real `_service_review_loop`,
  and asserts the recheck line lands in the shadow pane **exactly once**;
- `test_app_does_not_fire_on_a_selection_redraw` — the negative control, same
  path, asserting nothing is injected.

Three implementation notes, each a defect found while building it:

- The shadow must be its **own window**, not a split of the followed pane: a
  split halves the followed pane's height and the bottom-aligned fixtures came
  back truncated (130 rows → 65).
- The app must be armed with `stale=False`. `action_toggle_review_loop` passes
  `pending_work=(self._shadow_feedback_stale is True)`, so arming while already
  stale opens the work latch immediately — correct in production, but it made
  the negative control fire and would have let the positive test pass for a
  reason unrelated to the boundary. Staleness is switched on after arming, and
  the test asserts `work_seen` is False at arm time.
- Negative controls re-run against the new tests: an injected residual
  `claude-only` guard fails the arming assertion for both agents, and neutering
  both boundary regexes fails the fire assertion (`'waiting' != 'fired'`) for
  both agents.

`bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.

### Change Request 2 (2026-08-17) — negative app-path test parametrized

**Confirmed.** `test_app_does_not_fire_on_a_selection_redraw` hardcoded
`agent = "codex"` while the positive app-path test iterated both. That left
OpenCode's selection path unexercised *through the application*, and it is not
the same path as Codex's: Codex draws a `›` cursor, so its pair differs once
stripped and classifies `SELECTION_ONLY` via the boundary, whereas OpenCode
draws selection purely as ANSI styling, so its pair is byte-identical stripped
and returns `NO_CHANGE` **before** any boundary is consulted. Covering one said
nothing about the other.

Now parametrized over both agents with each one's measured selection fixtures,
asserting per agent that the controller does not reach `FIRED` **and** that the
shadow pane's recheck count is unchanged.

**Discriminating negative control:** mutating only the branch OpenCode depends on
(`prev_plain == curr_plain` → return `WORK` instead of `NO_CHANGE`) fails the
new OpenCode subtest (`'fired' == 'fired' : opencode: a selection redraw must
not fire`) alongside `test_opencode_dialog_selection_does_not_signal_work`
(`'work' != 'none'`) — so the subtest is genuinely load-bearing rather than
passing vacuously.

`bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.

---

## Final Implementation Notes

- **Actual work done:** Measured both agents' native-dialog boundaries live (5
  reps each, three evidence channels), then shipped them: `NATIVE_DIALOG_BOUNDARIES`
  rows for `codex_permission`, `codex_yes_proceed` and `opencode_permission`; a
  new `NATIVE_DIALOG_STRATEGIES` table (defined, empty) consulted **before** the
  regex table via `_native_block_start`; `DELIBERATELY_UNANCHORED_KINDS` making
  deliberate non-coverage a property of the table; `native_dialog_anchored` as
  the shared predicate. `REVIEW_LOOP_AGENTS` widened to
  `("claude", "codex", "opencode")`, and minimonitor's arm refusal now
  interpolates that tuple instead of claiming "Claude-only for now". Tests: real
  captured fixtures, both directions per agent per dialog, a total completeness
  guard with three built-in negative controls, and a live-tmux class driving the
  real application path end to end. Docs updated in `shadow_agent.md` and the
  minimonitor how-to.

- **Deviations from plan:** The plan's OpenCode branch rule chose between a
  phrase boundary and the structural gutter scan on whether lines between them
  change during selection. Measurement selected the **phrase branch**, but for a
  reason the rule did not anticipate: OpenCode renders selection purely as ANSI
  styling, so *no* stripped line changes at all and B3 is **vacuous** rather than
  passing. Recorded as `vacuous` instead of scored as a pass, and the row's real
  purpose (the WORK direction) documented at the definition. `NATIVE_DIALOG_STRATEGIES`
  ships empty, as the approved plan required.

- **Issues encountered:**
  - Codex auto-approves in-workspace writes; a command **outside** the sandbox is
    needed to provoke the exec-approval dialog at all.
  - `codex_yes_proceed` was never the reported kind across 23 live captures — its
    footer always wins first-match and nothing renders below it. The row ships
    anyway (same dialog, same evidence) and the non-reachability is recorded so
    it is not later mistaken for measured-live.
  - The first OpenCode selection measurement was **invalid**: `Tab` was sent on
    the strength of the widget's `⇆ select` hint and never registered (raw
    byte-identical). Only the ground-truth channel caught it; the resulting
    "stripped text unchanged" reading would otherwise have been recorded as a
    property of the widget. `Right` is the key; `tab` is bound to "agents".
  - Live driving of Codex needs **chunked** `send-keys`: one long literal burst
    is coalesced and arrives truncated (a 78-char prompt became `518arm.txt`).
  - Building the live smoke surfaced three fixture-hygiene traps, each producing
    a false `WORK`: tmux history persisting across paints, `\x1b[2J` scrolling
    the old screen into the freshly-cleared history, and a shadow *split* halving
    the followed pane's height. Resolved by bottom-aligning frames inside a pane
    tall enough to hold them, overwriting in place with absolute cursor
    addressing and no newlines, and giving the shadow its own window.

- **Key decisions:**
  - Ship the boundary row for a kind that is currently unreachable rather than
    exempt it — the evidence is the same dialog frame, and omission would mean
    silent `UNKNOWN` if a future version surfaces it.
  - Derive the completeness guard's kind set from `scope_patterns(all_patterns(),
    agent)` — the production seam — rather than from `PROMPT_PATTERNS_BY_AGENT[agent]`,
    so the cross-agent `"all"` group is covered and the guard follows any change
    to the scoping rule.
  - Keep `NATIVE_DIALOG_STRATEGIES` defined even when empty, so the precedence
    lookup is unconditional and callers never need `globals().get`.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/review_loop.py:DELIBERATELY_UNANCHORED_KINDS — Claude's `claude_help_bar`, `claude_proceed` and `claude_trust_folder` have no measured boundary, so a Claude pane parked at a tool-permission dialog classifies UNKNOWN and the loop silently never fires — the same under-detection this task closed for Codex and OpenCode. Pre-existing; closing it needs its own live measurement of Claude's dialogs.`
  - `tests/test_minimonitor_concern_action.py:1095 — `unittest.main()` sat mid-file in a 3100-line module, so direct invocation exited after 55 of 177 tests and silently skipped every class below, including all review-loop arming tests. FIXED in this task (moved to the end with a comment); listed because the same shape may exist in other long test modules and is invisible under discovery-based runs.`
