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

4. **Fail-open on an unrecognized command — but it must never *claim* to be
   scoped.** Measured on the live tmux server during planning, the fail-open
   path is the **common case, not an edge**. An `agent-*` window holds three
   `PaneCategory.AGENT` panes (the category comes from the window-name prefix,
   `monitor_core.py:1741-1749`), and only one of them resolves:

   | pane | `pane_current_command` | `agent_key_from_command` |
   |---|---|---|
   | followed agent | `claude` | `claude` |
   | **shadow (also Claude Code)** | **`node`** | `""` |
   | companion TUI | `python` | `""` |

   So `pane_current_command` is **not a reliable agent identifier**, and a
   fail-open that silently applies the flat list to two panes in three would
   leave the per-agent outcome mostly unrealized while reading, from the code,
   as though it had been achieved. The rule therefore has two halves:

   - **Matching** stays fail-open: an unresolved key removes nothing, so no
     detection that works today is lost. Scoping removes only patterns that
     *provably belong to another agent*; unknown names (a caller's custom
     pattern, a test's) survive; `prompt_patterns=[]` still disables detection
     entirely, because the filter operates on the **supplied list**, never on the
     module dict.
   - **Reporting** stops pretending. `ClassifyResult` carries the resolution
     outcome (`agent_key: str`, `scoped: bool`), so "this kind was matched under
     scoped rules" and "this kind came from the unscoped flat list" are
     **distinguishable states** rather than one indistinguishable one. Every
     consumer that reasons about the kind can then tell which it has, and the
     phase composer already does the right thing for `agent=""` (ledger-only,
     `detail` = "no agent supplied", `workflow_phase.py:419-422`).

   The residual exposure is narrow and is closed by construction rather than by
   the key: a new pattern is admitted only if the pre-phase measured it
   **disjoint from every existing pattern** (criterion (d)), and §5 asserts that
   disjointness against real captured Claude pane text. A foreign match on an
   unscoped pane therefore requires a pattern that was measured not to match it.

   **Resolution ladder (in scope, decided after the pre-phase measurement).**
   `pane_current_command` alone leaves Codex permanently unresolved, which would
   ship §1–§4 wired-but-dormant for it. So resolution gains a second rung:

   1. the pane's own command (today's rule, exact for Claude and OpenCode);
   2. **one level of child processes** — Codex's node wrapper spawns the real
      `codex` binary as its direct child, so the answer is one `pgrep -P` away.
      `pane_pid` is already on `TmuxPaneInfo` (`monitor_core.py:805`), so no
      launch-site changes are needed and manually-started panes are covered too.

   Bounded deliberately at **one** level: deeper descent starts matching
   grandchildren an agent merely *spawned* (`codex-code-mode-host` is already at
   depth 2), which would resolve a pane to whatever it happens to be running.
   Any failure — no `pgrep`, timeout, unreadable table, more than one matching
   child — returns `""`, i.e. exactly today's behaviour, so the rung can only
   add resolution, never break it. Cached per `pane_pid` (stable for the pane's
   life) so the subprocess runs once per pane, not once per tick.

   The **durable** fix — an engine-owned `@aitask_agent` pane option stamped at
   launch, exact instead of inferred — stays a follow-up (§7): it touches ~5
   launch sites and covers only framework-launched panes. Nothing in this task
   may be written as though `current_command` were authoritative.

5. **One canonical command→agent mapper, in `lib/`.** `workflow_phase.agent_key_from_command`
   (`:135-145`) keys off `QUESTION_WIDGET_KINDS`; classification needs the same
   mapping keyed off `PROMPT_PATTERNS_BY_AGENT`, and two mappers would drift the
   moment an agent is added to one table only. But the mapper must **not** live
   in `monitor/prompt_patterns.py`: the dependency direction is strictly one-way
   — `monitor_core.py:38-39` puts `lib/` on `sys.path` and imports
   `workflow_phase`, while `workflow_phase.py:41` inserts only its own `lib/`
   directory and declares itself stdlib-only. Importing `monitor/` from it would
   invert the layering and break its standalone `signal` CLI.

   So the canonical mapper goes in a **new, tiny `lib/agent_keys.py`** (stdlib
   only, no tmux, no Textual — the same contract as `gate_ledger.py`), holding
   the agent-key tuple and `agent_key_from_command`. `workflow_phase.py` imports
   it from its own directory and **re-exports the name**, so
   `workflow_phase.agent_key_from_command` keeps its signature and every existing
   caller (`monitor_app.py:1631`, `minimonitor_app.py:1067`, `:2438`,
   `review_loop.py`) is untouched. `monitor/prompt_patterns.py` reaches it with a
   `__file__`-derived `sys.path` insert plus an `ImportError` fallback, the idiom
   `review_loop.py:54` already uses. Pinned by an import-direction test (§5.8).

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

   **MEASUREMENT RESULTS (executed 2026-08-13; Codex CLI 0.146.0, OpenCode
   1.18.18; isolated tmux socket `ait1467`, 163×50 pane, captured via
   `capture-pane -p -e -S -N` + `ansi_utils.strip_ansi`).**

   *Static pass — mostly negative, and that is itself the finding.* Codex stores
   its literals as **split 8-byte instruction immediates** (`Yes, pro` + `ceed`
   in adjacent `mov`s), so exact wording is **not** statically recoverable; a
   naive `grep -c "Yes, proceed"` returns 0 on a binary that plainly contains it,
   which would have been read as "the pattern is dead". OpenCode's one contiguous
   i18n bundle belongs to its **desktop/web** UI (`settings.*`, `editor.*`,
   `activityBar.*` namespaces), not the TUI; the TUI's option labels live in a
   Bun/JSC bundle as a hardcoded array (`"Allow once"` / `"Always allow"` /
   `"Reject"`) that shows **no** locale variants. Conclusion: the static pass
   cannot size either agent, and the localization risk is **lower** than assumed
   for the TUI surface — but is asserted, not trusted, by the §5.6 control.

   *Live pass — both agents have a question widget.* This was the open question
   the whole Tier A half depended on, and the answer is yes for both:

   | agent | currency marker (distance above bottom) | block boundary | in 6-line window? |
   |---|---|---|---|
   | Codex | `tab to add notes \| enter to submit answer` (**1**) | `Question 1/1 (1 unanswered)` — a `Question N/M` header, once, only while live (**9**) | yes |
   | OpenCode | `↑↓ select  enter submit  esc dismiss` (**2**) | topmost line of the contiguous `┃` gutter block (**13**) | yes |

   Codex's `Question N/M` header is a direct analogue of Claude's `☐ <Header>`
   chip. OpenCode has no single header line, so its boundary is the **top of the
   contiguous `┃`-gutter run** — structural in the same sense (the widget renders
   as one gutter-marked block and the anchor must sit inside it), not a distance.

   *Native permission dialogs — measured, and deliberately phase-less.* Both are
   generic tool confirmations, so per the t1420 design they get a **currency
   marker but no `NATIVE_KIND_PHASE` row**:

   | agent | bottom-anchored marker (distance) | dialog header |
   |---|---|---|
   | Codex | `Press enter to confirm or esc to cancel` (**1**); `Yes, proceed (y)` (**5**) | `Would you like to run the following command?` (13) |
   | OpenCode | `Allow once   Allow always   Reject` (**2**) | `△ Permission required` (10) |

   `codex_yes_proceed` therefore **still fires** on 0.146.0 (distance 5, inside
   the window) — it is not dead. OpenCode, having no patterns at all, currently
   reads as **idle while blocked on a permission dialog**; fixing that is real
   monitor value independent of the phase work, the same class as t1474.
   OpenCode's dialog wraps a right-hand status column into the same lines, so its
   patterns must tolerate trailing content rather than anchoring on `$`.

   *Blocking finding — Codex panes do not resolve to an agent.* `claude` is a
   native ELF binary, so tmux reports `claude`. `opencode`'s npx bin is likewise
   native → `opencode`. **Codex is a node wrapper that spawns the real binary as
   a child**, so `pane_current_command` is `node` and
   `agent_key_from_command` returns `""`:

   ```
   3419311  node /home/ddt/.local/share/mise/installs/node/25.2.1/bin/codex
   3419337   \_ .../codex-linux-x64/vendor/.../bin/codex        ← the real agent
   ```

   Confirmed on the user's live session too: the Codex shadow bound to this very
   task's pane reads `node`. **Everything in §1–§4 is unreachable for Codex until
   agent identity is resolved** — the tables would be wired and dormant. This
   supersedes the §7 note that deferred the identity problem, and it corrects
   that note's premise: the `node` panes are **Codex** shadows, not Claude ones.
   Note it is **install-shaped**, not universal: a natively-installed Codex would
   report `codex`, so the fix must improve resolution without assuming either
   shape.

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

## 1. Per-agent prompt scoping — `lib/agent_keys.py` (new) + `monitor/prompt_patterns.py` + `monitor/monitor_core.py`

**New `lib/agent_keys.py`** — stdlib only, no imports outside the standard
library, so both layers can reach it without inverting the `monitor → lib`
direction (decision 5):

```python
AGENT_KEYS: tuple[str, ...] = ("claude", "codex", "opencode")


def agent_key_from_command(current_command: str) -> str:
    """Canonical pane-command → per-agent table key, or "" when unrecognised.

    THE one mapper, so an agent cannot land in one per-agent table's key set and
    not another's. Exact basename match — a pane running `claude-something-else`
    is not Claude Code. `"all"` is a pattern GROUP, never an agent key.

    KNOWN LIMIT (measured, t1467): `pane_current_command` is not an authoritative
    agent identifier. A Codex pane reports `node` (its launcher is a node wrapper
    that spawns the real binary as a child) and a companion TUI reports `python`,
    yet both are PaneCategory.AGENT. `""` therefore means "could not resolve",
    never "not an agent", and callers must degrade rather than conclude. Use
    `agent_key_from_pane` to get the second rung. See
    `aidocs/framework/monitor_idle_and_prompt_detection.md`.
    """


def agent_key_from_pane(current_command: str, pane_pid: int | None = None) -> str:
    """Two-rung resolution: the pane's own command, then ONE level of children.

    Rung 2 exists because a wrapper-style install hides the agent one level down
    (measured: `node` → `codex`). Bounded at one level on purpose — at depth 2
    Codex already runs `codex-code-mode-host`, so a deeper walk would resolve a
    pane to whatever it happens to have spawned.

    Every failure path returns `""`, which is exactly the pre-t1467 answer: no
    `pgrep`, a timeout, an unreadable process table, or **more than one** matching
    child (ambiguity suppresses rather than picking). Result is cached per
    `pane_pid`, which is stable for the pane's lifetime, so the subprocess runs
    once per pane rather than once per tick.
    """
```

Portability: `pgrep -P <pid>` + `ps -o comm= -p <pid>` are the pair that works on
both Linux and BSD/macOS (`ps --ppid` is GNU-only — see
`aidocs/framework/sed_macos_issues.md` for why that class of flag is avoided).
Both run with a short timeout and their failure is indistinguishable, by design,
from "unresolved".

`workflow_phase.py` imports it from its own directory and **re-exports**
`agent_key_from_command` under its existing name, keeping every current caller
working unchanged.

**`prompt_patterns.py`** delegates to it (via a `__file__`-derived path insert
with an `ImportError` fallback, the `review_loop.py:54` idiom) and gains one
pure helper; `all_patterns()` is untouched, five call sites depend on it:

```python
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
`prompt_patterns`, and `ClassifyResult` (`:180-187`) gains two fields carrying
the resolution outcome (decision 4):

```python
    agent_key: str = ""      # resolved per-agent key, "" = unresolved
    scoped: bool = False     # True only when matching WAS narrowed to that key
```

`scoped=False` is the honest default: a `ClassifyResult` built by the fail-closed
`except` path (`:231-233`) or by a caller that passed no agent has not been
scoped, and must not read as though it had. `_apply_bookkeeping` (`:2142-2150`)
carries both onto `PaneSnapshot` beside `awaiting_input_kind`, so every consumer
that reasons about the kind can tell which regime produced it.

The five call sites all have `pane` in scope and pass
`agent=agent_key_from_pane(pane.current_command, pane.pane_pid)`:

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

**The four patterns, from the measurement** (question widget first in each row,
permission dialog second, existing generic last):

| name | anchor (measured distance) | role |
|---|---|---|
| `codex_question` | `tab to add notes \| enter to submit answer` (1) | Tier A currency marker |
| `codex_permission` | `Press enter to confirm or esc to cancel` (1) | generic confirm — **no** phase row |
| `opencode_question` | `↑↓ select  enter submit  esc dismiss` (2) | Tier A currency marker |
| `opencode_permission` | `Allow once` … `Allow always` … `Reject` (2) | generic confirm — **no** phase row |

Each anchors on a **footer hint line**, not on a label a document could quote:
these lines are key-binding legends, which is both the most stable part of a TUI
widget across versions and the part least likely to appear in prose. The two
permission patterns are deliberately *not* `NATIVE_KIND_PHASE` keys — a tool
confirmation carries no workflow phase, and the drift guard's `LEAKED:-` check
fails if one is added.

OpenCode's dialog wraps a right-hand status column into the same physical lines,
so its patterns must **not** anchor on `$` — trailing content is normal there.
The separator run in `↑↓ select  enter submit` is written `\s+` rather than a
fixed two-space literal, since column wrapping can reflow it.

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
    "claude": _QUESTION_HEADER_RE,        # ☐ <Header> chip (t1420, measured)
    "codex": _CODEX_QUESTION_HEADER_RE,   # "Question N/M (K unanswered)" (t1467)
    # opencode has no header line — its boundary is the top of the contiguous
    # `┃` gutter run, which needs a scan rather than a line match, so it is
    # expressed as a strategy (below) rather than a regex.
}


def current_question_block(lines: list[str], agent: str = "claude") -> int | None:
```

OpenCode needs a **scan**, not a line match: its widget renders as a contiguous
run of `┃`-gutter lines with no header, so the block starts at the **topmost
line of the gutter run that reaches the bottom of the tail**. That is structural
in the same sense as the chip — "is the anchor inside the current widget" — and
is expressed as a small strategy function rather than forced into a regex:

```python
_GUTTER_RE = re.compile(r"^\s*┃")   # ┃

def _opencode_block_start(lines: list[str]) -> int | None:
    """Top of the contiguous ┃-gutter run that reaches the last gutter line.

    A gap of non-gutter lines ends the run, so an earlier, already-answered
    widget higher in the scrollback is a DIFFERENT run and is excluded — the
    same property the chip gives Claude.
    """
```

so `QUESTION_BLOCK_STRATEGIES: dict[str, Callable]` carries `opencode`, and the
regex table carries `claude` / `codex`; `current_question_block` consults the
strategy first, then the regex table, then returns `None`. Two mechanisms rather
than one is a real cost, and the alternative — a regex that matches the gutter
character alone — is rejected because it would match **every** line of the block
including ones above an earlier answered widget, which is exactly the staleness
the boundary exists to exclude.

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

- `QUESTION_WIDGET_KINDS["codex"] = ("codex_question",)` and
  `["opencode"] = ("opencode_question",)` — the measured question widgets.
- `NATIVE_KIND_PHASE["codex"] / ["opencode"]` stay **`{}`**. This is a measured
  result, not an omission: neither CLI has an `ExitPlanMode` analogue, so the
  only native dialogs either one renders are tool confirmations, which carry no
  workflow phase by construction. Their comments change from "t1467 owns
  inventorying" to a statement of what the inventory **found**, so a later reader
  does not re-open a closed question. `codex_yes_proceed`, `codex_permission` and
  `opencode_permission` remain deliberately absent keys; the drift guard's
  `LEAKED:-` check fails if any is added.

  Consequence worth stating plainly: for Codex and OpenCode the phase comes from
  **Tier A or the ledger, never Tier B** — which is a narrower claim than
  "comparable to Claude" and is what the availability table must say.
- `agent_key_from_command` (`:135-145`) becomes a one-line delegation to
  **`agent_keys.agent_key_from_command`** (the new stdlib-only `lib/` module),
  keeping its name, signature and docstring intent. `monitor/prompt_patterns.py`
  imports **the same `lib/agent_keys` helper** — it does **not** define its own
  and `workflow_phase` does **not** delegate to it; delegating downward into
  `monitor/` is exactly the layering inversion decision 5 exists to prevent.
  One owner, two re-exports, and §5.8 asserts the two public names resolve to
  the identical function object so a future edit cannot fork them.
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

## 4b. Who consumes the resolution provenance

Decision 4's `agent_key` / `scoped` fields are worthless unless something reads
them: a field nobody consumes makes the *code* look honest while every visible
surface still presents an unresolved `node` pane exactly like a scoped one.
Named consumers, all four paths:

**Phase** — `GateSummaryCache.phase_for` (`monitor_core.py:3221-3234`) takes the
agent from `snap.agent_key` instead of re-deriving it, and `compose`
(`workflow_phase.py:419-426`) grows a **third** case between its existing two.
Today `agent=""` yields *"live tiers unavailable: no agent supplied"*, which
blames the caller; that is right when the caller genuinely said nothing, and
wrong when the caller tried and the pane's command was unresolvable. Split them:

```
no agent supplied            → caller error (unchanged wording)
agent unresolved             → "live tiers unavailable: pane command '<cmd>'
                               does not resolve to a known agent (see
                               @aitask_agent follow-up)"
```

The composer needs the raw command to say this, so `compose` takes an optional
`current_command` used **only** in that message — never in a matching decision.

**UI — the qualifier must be ORTHOGONAL to the phase, not a phase value.**
`awaiting_input_kind` is not rendered as text on any card today (it feeds counts
at `monitor_app.py:1505-1510` / `minimonitor_app.py:931-936`, ordering at
`:1368-1380`, and the phase), so inventing a new badge would be scope creep —
the phase label is the right surface. But an `_UNKNOWN_TEXT` cause is **not**,
and this is the trap: `_phase_body` (`:520-534`) consults that table only inside
`if sig.phase == UNKNOWN_PHASE`. A task **with** ledger history falls back to
`IMPLEMENT` / `POSTIMPL` and renders `IMPLEMENT ⏸` — indistinguishable from a
scoped pane — even though `_ledger()` (`:407-409`) took that very `⏸` from the
`awaiting_input` an **unscoped** match produced. Provenance that only survives
when the phase is unknown is provenance that disappears exactly when the phase
is most confident.

So resolution becomes its **own field with its own vocabulary**, rendered as a
suffix in *both* branches:

```python
RESOLUTIONS = ("scoped", "no_markers", "unresolved", "absent", "unknown")
```

`PhaseSignal` gains `resolution: str = "unknown"`, validated by `format_signal`
and degraded by `parse_signal` like every other vocabulary field, and carried on
the wire as `RESOLUTION:`. The format is key-based, so an old reader ignores the
new key and a new reader defaults a missing one — no `@aitask_shadow_phase`
compatibility break with a stale minimonitor (t1116).

`compose` sets it from what it was actually given:

| `agent` | `current_command` | resolution |
|---|---|---|
| non-empty, has markers | — | `scoped` |
| non-empty, no markers | — | `no_markers` |
| `""` | supplied | `unresolved` (the caller tried; the command did not map) |
| `""` | not supplied | `absent` (the caller said nothing) |

`_phase_body` appends the suffix **outside** the UNKNOWN branch, from a single
`_RESOLUTION_SUFFIX` table with a wide and a narrow column — the same
one-table-two-columns shape `_UNKNOWN_TEXT` uses, so the forms cannot drift:

```
full:    phase: IMPLEMENT ⏸ (agent unresolved)   /   phase: unknown (agent unresolved)
narrow:  IMPLEMENT ⏸?                             /   unknown?
```

Narrow gets a single `?`, not a word: that line is ~36 cells shared with the gate
summary (t1479), and a qualifier that pushes the counts off the row is not
readable even though it is present. `scoped` and `absent` render **no** suffix —
`absent` is a caller that never asked, and marking it would put a qualifier on
every CLI invocation.

**This also removes a latent fragility.** `_phase_body`'s existing `ledger_only`
cause is selected by `"no prompt markers" in sig.detail` (`:529`) — a substring
sniff on a human-readable string that *this task rewrites*. With `resolution` as
an explicit field, that branch reads `sig.resolution == "no_markers"` and the
detail wording is free to change without silently killing the rendering.

**Review loop** — `minimonitor_app.py:2438` (arm gate) and `:2530` (change
classification) take the key from `snap.agent_key`. The two **shadow**-side
sites (`:2459`, `:2546`) keep resolving from `shadow_command`: there is no
snapshot for the shadow pane, so there is nothing to consume. That is a
deliberate exception, stated here so it does not read as a missed site — and it
is precisely the path the §7 upstream defect concerns.

**Applink** — `pusher.py:414-432` adds two **additive optional** payload fields
beside `awaiting_input_kind`:

```python
        # Additive optional fields — no protocol `v` bump (aidocs/applink/
        # protocol.md "Versioning": clients ignore fields they don't recognize).
        if snap.agent_key:
            frame["payload"]["agent_key"] = snap.agent_key
        frame["payload"]["awaiting_input_scoped"] = snap.scoped
```

This follows the `status` precedent already in that function verbatim, including
its comment citing the versioning rule, so no schema change and no `v` bump. A
mobile client can then distinguish the two regimes; one that does not, ignores
them.

**Single-derivation rule.** After this, `agent_key_from_command` is called from
exactly **two** kinds of site: the five `classify_content` call sites (which
produce the value) and the two shadow-command sites (which have no snapshot).
Every other consumer reads `snap.agent_key`. §5.10 pins that with an asserted
hit count, so a later re-derivation cannot creep back in and silently diverge
from the value that actually scoped the match.

## 5. Tests

Run `bash tests/run_all_python_tests.sh` (**last line only**), each new/edited
bash test individually, and `shellcheck .aitask-scripts/aitask_*.sh`.

1. **`tests/test_prompt_detection.py`** — the pre-phase characterizations, plus:
   the **cross-agent negative control** (a `codex_yes_proceed` body on a pane
   with `current_command="claude"` must NOT report a codex kind — this fails
   against today's build, which is what makes it discriminating), the fail-open
   control (`current_command="node"` still matches the flat list **and reports
   `scoped is False`, `agent_key == ""`**), the `prompt_patterns=[]` disable path
   under scoping, and the custom-pattern survival case.
   `_check_all_patterns_flattens_per_agent_groups` (`:172`) derives its count
   from `PROMPT_PATTERNS_BY_AGENT`, so it absorbs new patterns — but its three
   explicit name assertions (`:180-182`) get siblings for the new names.
   **Positive control first:** the scoping tests must fail against the
   unmodified module, asserted by running them once before the change.

1b. **Call-site coverage, deterministically — `tests/test_monitor_finalize_offload.py`
   (+ `tests/test_monitor_shadow_status.py`).** The live post-phase is
   *acceptance evidence*, not the detector: it depends on a real tmux server and
   on both CLIs' auth, and a failed fixture would let a missed call site ship.
   So every one of the five paths gets a deterministic assertion driving the
   **monitor entry point**, not `classify_content` directly — that is the whole
   point, since the function can be correct while one caller never passes
   `agent=`. One table-driven case per path, each feeding a pane with
   `current_command="claude"` and content carrying **codex** prompt text, and
   asserting `awaiting_input_kind != "codex_yes_proceed"` and `scoped is True`:

   | path | entry point |
   |---|---|
   | sync | `TmuxMonitor._finalize_capture` (`monitor_core.py:2167`) |
   | shadow capture | the `_classify_one` lambda at `:2259` |
   | async single | `:2341` |
   | off-loop single | `:2391` |
   | off-loop batch | `_classify_batch` via `:2525` |

   Plus the mirror case (claude text on a `codex` pane) and the existing
   sync-vs-offload parity assertions (`test_monitor_finalize_offload.py:208`,
   `:320`, `:335`) extended to compare `agent_key` / `scoped` too — so the two
   lanes cannot diverge on the new fields. These tests must **fail against a
   build where any single call site is reverted**; verify by reverting each of
   the five in turn and confirming exactly the corresponding case fails.
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
8. **Import-direction / standalone-CLI guard** (new,
   `tests/test_workflow_phase_standalone.sh` or a case in the drift guard) —
   `workflow_phase.py` must stay reachable **without `monitor/` on the path**:
   run `python3 .aitask-scripts/lib/workflow_phase.py signal <fixture>` from a
   directory outside the repo with a **scrubbed `PYTHONPATH`**, and assert exit 0
   plus a well-formed `PHASE:` line. Plus a source-level assertion that
   `workflow_phase.py` and `lib/agent_keys.py` import **nothing** from `monitor.`
   (the same AST/source shape `tests/test_gate_ledger_public_api.py` already uses
   for the no-private-imports contract). This is the guard that would have caught
   the layering inversion this plan originally proposed. Plus the single-owner
   assertion: `workflow_phase.agent_key_from_command is
   prompt_patterns.agent_key_from_command is agent_keys.agent_key_from_command`
   — identity, not equal behaviour on a sample, so a forked reimplementation
   fails even if it happens to agree on the fixtures.
9. **Unscoped-pane honesty** (in `test_prompt_detection.py`) — a pane whose
   command resolves through **neither** rung reports `scoped is False` and
   `agent_key == ""` even when a kind matched, and a `current_command="claude"`
   pane reports `scoped is True`. Asserting both directions is what stops the
   fields becoming a constant.
9b. **Resolution ladder** (new, `tests/test_agent_keys.py`) — `agent_key_from_pane`
   against a **real** process tree, not a mock: spawn `sh -c 'exec sleep 30'`
   wrappers so the child's `comm` is controllable, and assert
   - rung 1 wins when the pane command itself resolves (no subprocess at all —
     assert by patching the child lookup to raise, proving it is never reached);
   - rung 2 resolves the measured `node` → `codex` shape;
   - **more than one** matching child returns `""` (ambiguity suppresses);
   - a missing `pgrep`, a non-zero exit, and a timeout each return `""` — driven
     by pointing the helper at a `PATH` without `pgrep`, not by mocking, so the
     real failure path is exercised;
   - the cache calls the subprocess **once** per `pane_pid` across repeated
     calls (assert a call counter, since a per-tick subprocess is the cost this
     design exists to avoid);
   - depth is bounded: a grandchild named `codex` under a non-agent child does
     **not** resolve (the `codex-code-mode-host` shape).
10. **Provenance is actually exposed** — one assertion per §4b consumer, on the
   **emitted artifact** rather than on the field, since the fields are only worth
   having if something downstream differs:
   - *applink* (`tests/test_applink_pusher*.py`): serialize a `pane_status`
     frame for a `node` pane and for a `claude` pane; assert
     `json.loads(frame)["payload"]["awaiting_input_scoped"]` is `False` / `True`,
     that `agent_key` is absent / `"claude"`, and that `"v"` is still `1` (the
     additive-field contract).
   - *phase render — the full 2×2×2 matrix*, because the whole point is that the
     qualifier survives a **confident** phase: {`render_phase`,
     `render_phase_narrow`} × {empty ledger → `UNKNOWN`, `plan_approved pass` →
     `IMPLEMENT`, `review_approved pass` → `POSTIMPL`} × {`resolution="scoped"`,
     `"unresolved"`}. Assert the qualifier is present in **every** unresolved
     cell — including `IMPLEMENT ⏸`, the cell that renders clean today — and
     absent in every scoped cell. A test that only covered the no-ledger case
     would pass against the rejected `_UNKNOWN_TEXT` design, so it must include
     the ledger cases to discriminate at all.
     Also assert the narrow forms stay within the ~36-cell budget (t1479) and
     that `scoped` / `absent` add nothing.
   - *resolution vocabulary*: `RESOLUTIONS` pinned by value; `format_signal`
     refuses a non-member; `parse_signal` degrades one to `"unknown"`; a
     round-trip over every member is exact; and a line **without** a
     `RESOLUTION:` key parses to `"unknown"` rather than raising — the stale-writer
     (t1116) compatibility case.
   - *no substring sniffing*: assert `_phase_body`'s `no_markers` branch fires
     from `sig.resolution`, by composing a signal whose `detail` deliberately
     omits the phrase "no prompt markers" — this fails against the current
     substring implementation, which is what makes it a real guard.
   - *compose*: an unresolved pane's `detail` names the pane command and does
     **not** say "no agent supplied"; a caller that passed no agent at all still
     gets the original wording. These are the two cases the split exists for, so
     a build that collapsed them must fail here.
   - *single-derivation guard*: a source grep asserting a **hit count** of
     `agent_key_from_command(` call sites — 5 producer sites + 2 shadow-command
     sites — with the shadow exceptions named in the test's own comment, so
     re-derivation from `current_command` beside an available snapshot fails
     loudly rather than silently diverging. (Never a `grep -q`: a zero-match
     grep and a renamed symbol are indistinguishable without the count.)

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
  split and the follow-ups it implies. Edit only this task's own file.

## 7. Follow-ups this task deliberately does NOT do

Recorded here so they are visible at review, and raised through the normal
Step 8b / 8d offers rather than created inline:

- **`@aitask_agent` stamped pane option.** The measurement above shows
  `pane_current_command` is inference, not identity — a Claude Code shadow reads
  `node`. The durable fix is an engine-owned stamp written at launch by
  `aitask_codeagent.sh`, with `current_command` demoted to a fallback rung. That
  is a framework-launch change touching the codeagent launcher and every pane
  consumer; it is out of scope here, and this task must not be written as though
  `current_command` were authoritative.
- **Upstream defect (for the Step-8 Final Implementation Notes).**
  `.aitask-scripts/monitor/minimonitor_app.py:2459` — the shadow-side arm gate
  resolves `agent_key_from_command(shadow_command)` and refuses when the key is
  not in `SHADOW_READY_DETECTORS`; a Claude Code shadow pane reports `node`, so
  the key is `""` and the lookup misses for *every* shadow, making the refusal
  path ("no readiness detection yet") reachable for a shadow that is in fact
  Claude Code. Measured on the live server during planning; pre-existing and
  independent of this task.

  **Corrected by the measurement.** The `node` panes are **Codex** shadows, not
  Claude ones (the shadow bound to this task's own pane runs
  `codex -m gpt-5.6-terra $aitask-shadow %361 1467`). So the defect's real shape
  is: a Codex pane — followed *or* shadow — never resolves to an agent key, and
  the `SHADOW_READY_DETECTORS` miss is one symptom of that single cause.
  **`agent_key_from_pane`'s rung 2 fixes it at the root**, provided the shadow
  path is switched to the two-rung resolver too; `minimonitor_app.py:2459` and
  `:2546` resolve from `shadow_command` with no pane snapshot, so they need the
  shadow pane's pid threaded to benefit. Wiring that is **t1509's** call, not
  this task's — this task supplies the resolver and says so.
- **The pattern work here strengthens t1509's negative half** (its own
  Coordination note): `shadow_prompt_ready`'s exclusion consults
  `PROMPT_PATTERNS_BY_AGENT[agent]`, so §2's measured Codex/OpenCode dialog
  patterns make "no dialog is showing" reliable for those agents for free. That
  is a reason to land §2's patterns as authored here rather than duplicating
  pattern work in t1509 — but note the exclusion is only reached once the key
  resolves, which is the defect above.
- **Unlocking the auto-recheck loop for Codex/OpenCode** — gated behind
  `REVIEW_LOOP_AGENTS` by decision 6, and earns its own task once the per-agent
  boundary strategies have live evidence.

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

1. Every test in section 5, with the discriminating ones **run against a build
   that should fail them, and shown to fail**: 5.1 (cross-agent negative
   control) and 5.6 (locale degradation) against the pre-change build; 5.1b
   against five builds, each reverting one `agent=` call site, confirming
   exactly the corresponding path's case fails; 5.8 against a `workflow_phase.py`
   that imports from `monitor/`.
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
  · severity: low (residual — caught **deterministically** by Verification 5.1b,
  one case per path driven through the monitor entry point and validated by
  reverting each call site in turn; the inline post-phase `prove_scoping_live`
  is acceptance evidence on top, not the detector, so an unavailable live
  fixture cannot let the regression ship) · → mitigation: inline post-phase
  prove_scoping_live
- `pane_current_command` is **not** an authoritative agent identifier — measured
  on the live server, a Claude Code shadow pane reports `node` and a companion
  TUI reports `python`, while all three panes in an `agent-*` window are
  `PaneCategory.AGENT`. A fail-open that silently applied the flat list to two
  panes in three would leave the per-agent outcome mostly unrealized while
  reading as achieved. · severity: low (residual — the resolution outcome is
  carried explicitly as `agent_key` / `scoped` **and consumed by four named
  paths** (§4b: phase, UI wording, review loop, applink), so unscoped is a
  distinguishable state on the emitted artifacts and not only in the struct;
  new patterns are admitted only if measured disjoint from every existing one;
  pinned by Verification 5.9 and 5.10. The exact fix — an engine-owned
  `@aitask_agent` stamp — is scoped out to §7 rather than half-built here)
  · → mitigation: none (design change, decisions 4 + §4b)
- Resolution provenance rendered as an `_UNKNOWN_TEXT` cause would vanish
  precisely when the phase is most confident: `_phase_body` (`:520-534`) consults
  that table only when `phase == UNKNOWN`, so a task with ledger history would
  render `IMPLEMENT ⏸` — with the `⏸` supplied by the unscoped match itself —
  identically to a scoped pane. · severity: low (residual — `resolution` is an
  independent vocabulary field rendered as a suffix in both branches (§4b), and
  Verification 5.10's 2×2×2 matrix includes the ledger cells that the rejected
  design would have passed) · → mitigation: none (design change, §4b)
- `_phase_body` selects its `ledger_only` cause by testing
  `"no prompt markers" in sig.detail` — a substring dependency on a
  human-readable string that this task rewrites, so the rendering could die
  silently. · severity: low (residual — the branch moves to the explicit
  `resolution` field and Verification 5.10 pins it with a detail that omits the
  phrase) · → mitigation: none (design change, §4b)
- Provenance fields that nothing reads would make the code look honest while
  every visible surface still presents an unresolved pane identically — and
  five snapshot-derived sites currently re-derive the agent from
  `pane_current_command` independently, so the carried value could drift from
  the one that actually scoped the match. · severity: low (residual — §4b names
  every consumer and collapses derivation to producer-plus-two-documented-shadow
  exceptions; Verification 5.10 asserts on the serialized frame and the rendered
  text, not on the field, and pins the call-site count) · → mitigation: none
  (design change, §4b)
- Placing the canonical mapper in `monitor/` would invert the one-way
  `monitor → lib` dependency and break `workflow_phase.py`'s standalone `signal`
  CLI (it inserts only its own `lib/` directory and declares itself stdlib-only).
  · severity: low (residual — the mapper lives in the new stdlib-only
  `lib/agent_keys.py`, and Verification 5.8 runs the CLI from outside the repo
  with a scrubbed `PYTHONPATH` and asserts no `monitor.` import in either lib
  module) · → mitigation: none (design change, decision 5)

- Adding a subprocess to the per-pane classify path could cost a `pgrep` on
  every tick for every unresolved pane, on the hot refresh loop.
  · severity: low (residual — cached per `pane_pid`, which is stable for the
  pane's life, and Verification 5.9b asserts a call count of exactly one rather
  than trusting the cache by inspection) · → mitigation: none (design change,
  decision 4)
- A child-process descent is inference, and a deeper or greedier walk would
  resolve a pane to whatever it happened to spawn (`codex-code-mode-host` sits
  at depth 2 under a real Codex). · severity: low (residual — bounded at one
  level, ambiguity (>1 matching child) returns `""`, and every failure path
  degrades to the pre-t1467 answer; the exact seam stays §7)
  · → mitigation: none (design change, decision 4)

### Goal-achievement risk: low

**Reassessed after the pre-phase measurement** — the two `medium` bullets below
were the open questions the inline pre-phase existed to settle, and it settled
one positively and the other negatively, with both now recorded as fact rather
than risk.

- ~~Whether a structural block boundary exists~~ — **RESOLVED positively.**
  Codex renders `Question N/M (K unanswered)`, a direct analogue of Claude's
  chip; OpenCode renders a contiguous `┃` gutter run. Tier A ships for both.
  · severity: resolved · → mitigation: inline pre-phase inventory_prompt_surfaces_live
- ~~Whether a phase-bearing native dialog exists~~ — **RESOLVED negatively.**
  Neither CLI has an `ExitPlanMode` analogue, so `NATIVE_KIND_PHASE` stays empty
  for both and the phase comes from Tier A or the ledger. This is a real
  narrowing of "comparable to Claude", which §6 must state rather than imply
  away. · severity: low (residual — documented in the availability table and
  asserted by the absence-safety controls; no capability is lost, since a tool
  confirmation never carried a phase for Claude either)
  · → mitigation: inline pre-phase inventory_prompt_surfaces_live
- Codex's identity resolution is install-shaped: a wrapper-style install needs
  rung 2, and a future launcher change could move it again.
  · severity: low (residual — the ladder degrades to today's behaviour at every
  failure, and the durable `@aitask_agent` seam is recorded in §7)
  · → mitigation: none (design change, decision 4)
- Patterns are pinned to Codex 0.146.0 / OpenCode 1.18.18 footer wording; a TUI
  rewording silently disables the marker. · severity: low (residual — anchored
  on key-binding legends, the most stable part of a TUI widget, and each pattern
  records the version it was measured against; the same standing exposure
  `claude_askuserquestion` already carries) · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: inventory_prompt_surfaces_live | type: test | priority: high | effort: medium | inline_risk: medium | added_complexity: low | addresses: goal-achievement — whether a structural question-block boundary and a phase-bearing native dialog exist at all for Codex/OpenCode; code-health — geometrically wrong regexes and the OpenCode localization blast radius | desc: Enumerate candidate markers statically from the shipped codex binary and the opencode i18n bundle (including ≥2 non-English locales), then drive each CLI in an isolated tmux fixture through its approval / live-question / answered-question / idle states, capturing via the monitor's own capture-pane + strip_ansi path and recording line, distance above bottom, strip survival, disjointness from existing patterns, and boundary existence — before any pattern is authored.
- timing: pre-phase | name: characterize_classify_content | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — per-agent scoping moving awaiting_input_kind across the badges, pane ordering, the applink wire and the review-loop latch | desc: Pin today's (awaiting_input, awaiting_input_kind) for every existing pattern across current_command in {claude, codex, opencode, node, ""} plus the prompt_patterns=[] disable path and the category gate, run green against unmodified monitor_core.py, and table the intended flips before making the change.
- timing: post-phase | name: prove_scoping_live | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — one of the five classify_content call sites missing the agent= thread while unit tests stay green | desc: In a real tmux session with a Claude pane and a Codex pane, put each agent's prompt text on the other's pane and confirm from a captured monitor render that neither reports the foreign kind while each still reports its own.
