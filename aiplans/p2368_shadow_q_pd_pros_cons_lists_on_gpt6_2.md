---
Task: t2368_shadow_q_pd_pros_cons_lists_on_gpt6_2.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2368 — Shadow decision help: quick `>q`, full `>qd`, and `>pd` lists

**Naming (user, 2026-11-27).** The full comparison is `>qd`, not `>qw`, and
`>pd` keeps its name. The `d` then reads the same in both families: `>qd` is
the decision on screen with pros and cons per option, `>pd` is the plan's
design decisions with pros and cons per decision. The scan matcher tries `qd`
before `q`.

## Context

The shadow agent runs on `codex/gpt6_2_sol` by default. Its "help me weigh it"
shortcodes do not give the user what they want:

- `>pd` should give a pros list and a cons list per design decision. On
  gpt-6.2-sol it gives one prose paragraph per decision.
- `>q` was meant to also give pros and cons per option. During planning the
  user saw that form on a routine workflow menu and found it silly there:
  generic points, the menu's own controls listed as options, and a
  recommendation against the followed agent's with a one-clause reason.

**Decision (user, 2026-11-27): split decision help into two commands, so the
depth is chosen explicitly.**

- `>q` is the quick answer: what is being decided and why it matters; when the
  followed agent recommends an option, which one and why; the shadow's own
  recommendation with a short reason tied to the task; any disagreement with
  the agent explained. Concise. No required pros and cons lists.
- `>qd` is the full comparison: the situation first; each substantive option
  with its own Pros and Cons lists; the recommendation after the comparison.
  Menu controls such as free text and chat are skipped. No invented points.
  When only one option is realistic, it says why.
- Both share the screen refresh, the context gathering and the advisory
  behaviour.
- The `>pd` change stays in scope.

The wording is measured on the real CLI before it is committed, within the
budget already approved, and a free scan of local session logs is added so the
result can be re-measured on real use.

## Evidence re-measured during planning (2026-11-26)

The task's table reproduces exactly from `~/.codex/sessions/2026/{10,11}`:

| code | model | n | median chars | answers with `Pros:` and `Cons:` labels |
|---|---|---|---|---|
| `>pd` | gpt-6.1-sol | 48 | 2373 | 46 |
| `>pd` | gpt-6-astra | 12 | 2521 | 11 |
| `>pd` | gpt-6.2-sol | 7 | 1615 | 0 |
| `>q` | gpt-6.1-sol | 411 | 995 | 0 |
| `>q` | gpt-6.2-sol | 38 | 911 | 0 |

These are the **before** numbers.

- **Base instructions.** 58 gpt-6.2-sol sessions carry a 27,750-char text that
  no other model's session carries. It holds the rules the task quotes ("Do
  not use colons to introduce explanations or examples, including after list
  labels", "prefer using lists when it helps the reader scan items or steps").
- **The colon hypothesis stays untested.** Five sessions ran 6.2 under the old
  base text, but they hold no `>pd` answer.
- **Pane width.** The shadow pane is 60 columns wide
  (`project_config.yaml` `shadow_pane_width: 60`). A table does not fit. Lists
  do.
- **Observation, not evidence.** The Codex shadow following this session
  (gpt-6.2-sol, new base text, old skill wording) wrote `Pros` and `Cons`
  headings without a colon over bullets for one `>q` and one `>pd`. It had
  this plan in its context, so it shows the model can write the form when the
  ask is explicit. It does not show the skill wording alone is enough.
  Sessions that follow t2368 are excluded from the scan numbers.

## Design

### Output form of a pros and cons block (`>qd`, `>pd`)

Two short bulleted lists, one under a bold `**Pros**` line and one under a bold
`**Cons**` line. No colon after the label, no table. It is stated as the format
the user wants, not shown as an example. If the live check misses, the one
allowed revision uses `Pros` / `Cons` as plain list headings.

### `>q` and `>qd` in `.claude/skills/aitask-shadow/SKILL.md.j2`

The current `>q` bullet (lines 281-300) is replaced by these two bullets:

```
- `>q` — **Help me decide what to do now** ("help me decide", "what should I
  do?", "what do I answer?", "explain it simply and help me decide") — the
  quick answer, in **every** state the followed agent can be in, not only
  when it is asking a question. Any ask for decision help that does not
  explicitly ask for a comparison is `>q`. `>qd` below is the full
  comparison. Both follow these steps:
  1. **Capture the screen again first.** Run Step 1 and re-read `--phase`, even
     if you captured recently.
  2. **Gather whatever context the decision needs** — you are not limited to
     the followed agent's captured output.
  3. **Work out the choices.** A question on screen: the options it offers.
     **No question on screen** (still working, stuck or erroring, a plan
     waiting for approval, finished): the realistic next moves — wait,
     approve the plan, answer, interrupt or redirect the agent, or ask for a
     deeper shadow capability such as `>d`, `>pc` or `>i`. A deeper
     capability is **offered by its shortcode, never started on your own**;
     the user asks for it.
  4. **Write the answer** for the code that was asked.
  5. Remind the user that whatever they decide, they type it into the followed
     agent themselves — you do not.

  **The `>q` answer is short** and has no pros and cons lists:
  - what is being decided and why it matters, in simple words;
  - when the followed agent recommends an option, which one and its reason;
  - your recommendation, with a short reason tied to this task. When it
    differs from the followed agent's, say why its reason does not hold here.
- `>qd` — **The decision's options, with their pros and cons** ("compare the options", "pros and
  cons of each option", "weigh the options") — the full comparison, only
  when a comparison is explicitly asked for. Follow steps 1, 2, 3 and 5 of
  `>q`, and write the answer in this order:
  - **The situation in simple words**, first, before any recommendation: what
    is happening and what has to be decided, with the background someone new
    to it would need.
  - **Each substantive option**: what choosing it does in practice, then two
    lists, one headed **Pros** and one headed **Cons**, one real point per
    item. The two separate lists are the format the user wants: a sentence
    that mixes a benefit and a cost does not replace them. The menu's own
    controls, such as free text or chat, are not options. Every point is
    specific to this situation: what the user gains or loses for this task.
    Never invent a point to fill a list. When an option has no real downside,
    its Cons list is one item saying so. When only one option is realistic,
    say why and skip the lists.
  - **Your recommendation**, after the comparison, with the reason drawn from
    this task's facts. When it differs from the followed agent's, say why its
    reason does not hold here.
```

Other edits in the same file:

- Line 147 (the proactive offer after a capture): still offers `>q`, and names
  `>qd` for the full comparison.
- The `>e` bullet's pointer "that is `>q`" stays.
- The shortcode form rule ("one or two letters") already covers `>qd`.

### `>pd`

`SKILL.md.j2`, the `>pd` bullet (lines 311-318): "Plain prose: the task in
brief, then only the choices that were real trade-offs — each with its
realistic alternative, the plan's stated reason, and its pros and cons —"
becomes "The task in brief, then only the choices that were real trade-offs —
each with its realistic alternative, the plan's stated reason, then a list of
its pros and a list of its cons —".

`.claude/skills/aitask-shadow/plan-decisions.md`:

- Lines 8-10: "each with its pros and cons" becomes "each with a list of its
  pros and a list of its cons".
- Line 35: "It is prose for a human, nothing more." becomes "It is an answer
  for a human, nothing more."
- Step 4, the decisions item, becomes:

  ```
  - **The decisions**, most consequential first. For each: a line naming the
    decision, then two or three sentences on what the plan chose, the
    realistic alternative, and the plan's reason for its choice — or "the
    plan does not say why" when it gives none. Then two lists, one headed
    **Pros** and one headed **Cons**, one real point per item. The two
    separate lists are the format the user wants; do not fold the pros and
    cons into the sentences above.

    Write only real pros and cons. If you cannot name a real con, the choice
    was not a trade-off — drop it.
  ```

Unchanged: "Signal, not coverage", the selection test in step 3, "There is no
target number", "Never emitted unprompted", "Not a concern producer". The
format fixes the shape of the pros and cons of a decision already selected. It
adds no quota, which is what t1894 ruled out.

### `>t` and `>px` (report only)

- `>t` asks for short paragraphs in a fixed order. No label or colon is needed
  in the answer. No dependency.
- `>px` asks for an "Introduction" and a "Motivation" per subject, a labelled
  pair that could meet the same base rule. Not measured. The scan counts `>px`
  and `>t` answers, and a follow-up task is suggested if they show a problem.

## Files to change

| file | change |
|---|---|
| `.claude/skills/aitask-shadow/SKILL.md.j2` | `>q` bullet rewritten, new `>qd` bullet, line 147, `>pd` bullet wording |
| `.claude/skills/aitask-shadow/plan-decisions.md` | header sentence, line 35, step 4 |
| `tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md` | regenerated in the same commit |
| `tests/test_skill_render_aitask_shadow.sh` | shortcode list, Test 2q pins, `>pd` pins (below) |
| `aidocs/framework/shadow_agent.md` | `>q` / `>qd` summary (lines 124-130), shortcode list (line 190), `plan-decisions.md` entry (lines 147-160) |
| `website/content/docs/workflows/shadow-agent.md` | table rows 46-48 plus a `>qd` row, the "Help you decide" section (78-83), the `>pd` bullet (93) |
| `aidocs/benchmarks/shadow_q/scan_sessions.py` | new, the session-log scan |
| `tests/test_shadow_scan_sessions.py` | new, offline test on synthetic logs |
| `aidocs/benchmarks/shadow_q/harness.py` | the literal `prompt = ">q"` (line 990-991) reads `self.turn_prompt`, default `">q"`, and passes the matching turn kind into the session spec; one extra scenario name registered without changing the pilot's cell set |
| `aidocs/benchmarks/shadow_q/validate.py` | turn kind on `SessionSpec` (default `q`); `qd` and `pd` validity rules |
| `tests/test_shadow_q_harness.py` | offline tests for the turn kinds, the mixed-sequence failure counter, the runner lock, the headroom `acquire`; pilot totals unchanged |
| `aidocs/benchmarks/shadow_q/variants/v5_quick.md`, `variants/README.md` | the new `>q` bullet, byte-equal to production, and its README row. `VARIANTS` is not extended |
| `aidocs/benchmarks/shadow_q/adhoc_live_check.py` | new, the thin runner |
| `aidocs/benchmarks/shadow_q/fixtures/MANIFEST_workflow_menu.json` | new, hashes only, for the new fixture. `fixtures/MANIFEST.json` is not changed; `require_manifest` in `harness.py` is scoped to the run's scenarios |
| `aidocs/benchmarks/shadow_q/runs/t2368/` | numbers-only results and the one budget journal |
| `aidocs/benchmarks/shadow_q/README.md` | rows for the scan script and the runner |
| private store, project `aitasks_go`: `aidocs/shadow_q_store/fixtures/workflow_menu/` (with its own `PROVENANCE.md`) | new fixture (below), committed there by named paths only |

Not changed: `aidocs/benchmarks/shadow_q/frozen/` and `variants/v1..v4`, which
freeze the old `>q` text by design. Rendered variants under `.claude/skills/*-/`,
`.agents/skills/*-/` and `.opencode/skills/*-/` are gitignored and re-render on
use. The same source renders for all three agents, so no port task is needed.
The `>q` codes of the sitrep and brainstorm skills are separate and untouched.

### Test pins (`tests/test_skill_render_aitask_shadow.sh`)

- `SHORTCODES`: add ``'`>qd`'``.
- Test 2q `DECIDE_LINES` becomes: ``'`>q` — **Help me decide what to do now**'``,
  ``'`>qd` — **The decision's options, with their pros and cons**'``,
  `'**Capture the screen again first.**'`, ``'re-read `--phase`'``,
  `'you are not limited to'`, `'**Work out the choices.**'`,
  `'**No question on screen**'`, `'does not'` + `'explicitly ask for a comparison'`,
  `'Follow steps 1, 2, 3 and 5'`,
  `'never started on your own'`, `'has no pros and cons lists'`,
  `'which one and its reason'`, `'**The situation in simple words**'`,
  `'one headed **Pros** and one headed **Cons**'`, `'are not options'`,
  `'Never invent a point'`, `'When only one option is realistic'`,
  `'Explanation only: give no recommendation'`.
- `>pd` block: keep all current assertions; add `assert_contains` for
  `'one headed **Pros** and one headed **Cons**'` and `assert_not_contains` for
  `'prose for a human'`; `assert_not_contains 'Plain prose'` on the rendered
  SKILL.md.

## Implementation order

1. Write `scan_sessions.py` and its test. Run it and confirm the before table.
2. Write the new fixture in the private store and commit it there. Scope
   `require_manifest` to the run's scenarios and write
   `MANIFEST_workflow_menu.json`.
3. Write `v5_quick.md`, the harness and validator changes with their offline
   tests, and `adhoc_live_check.py`. `python3 tests/test_shadow_q_harness.py`
   must pass, mixed-kind sequence included, before any paid launch.
4. Run the live check (paid, within the approved count) and score it. A miss
   is handled as "Revision, and what counts toward shipping" defines.
5. Apply the wording that passed to `SKILL.md.j2` and `plan-decisions.md`, with
   the byte-equality checks.
6. Regenerate the three goldens; update the test pins, the framework doc and
   the website page.
7. Run the checks in "Verification", then Step 8 review and commit.
8. Send the notes. Step 9 (post-implementation: archival and the
   `risk_evaluated` gate) follows the shared workflow.

### `scan_sessions.py`

A port of the scan in the task file, numbers-only.

- `--agent codex` (default) reads `~/.codex/sessions/<year>/<month>/*/rollout-*.jsonl`
  that mention `aitask-shadow`. `--agent claude` reads
  `~/.claude/projects/*/*.jsonl` the same way. `--root` overrides the
  directory, which is what the test uses.
- Codes: `q`, `qd`, `pd`, and `px`, `t` for the report-only question. The
  matcher tries `qd` before `q`, so a `>qd` is never counted as a `>q`.
- Per (code, model, base-text length, skill-text class) it prints: n, median
  chars, answers with labelled `Pros:`/`Cons:` lines (the old matcher),
  answers with a Pros block and a Cons block in the new form (a line that is
  only `Pros`/`**Pros**`, colon optional, followed by at least one list item,
  and the same for Cons), and the median count of such block pairs. For `>q`
  under the new text the expected share with blocks is low and the number to
  watch is the length; for `>qd` and `>pd` it is the share with blocks.
- **Before and after are separate samples, split by the skill text the answer
  was produced under, not by date or model.** A pane opened before the
  rollout keeps the old skill. Each answer is classed from positive evidence
  only:
  - The evidence is the output of a tool call whose command names the
    relevant file: a rendered `aitask-shadow-*/SKILL.md` for `>q` and `>qd`,
    `plan-decisions.md` for `>pd`. The call and its output are paired by call
    id. Text from any other file is ignored.
  - `new`: that output contains a sentence that exists only in the new text.
    `old`: one that exists only in the old text.
  - `unknown`: no such read before the answer, a read whose output holds
    neither sentence (a bounded or truncated read that missed the section),
    or one that holds both. When several reads qualify, the last one before
    the answer decides. Unknown answers are counted and printed and belong to
    neither sample.
  - The marker sentences are constants taken from the shipped texts.
- `--exclude-task <id>` (repeatable) drops sessions whose log mentions
  `t<id>`. All reported numbers use `--exclude-task 2368`.
- The matcher is exposed as functions so the live-check runner scores with
  the same code.
- It prints counts only and never writes or echoes answer text.

`tests/test_shadow_scan_sessions.py` builds synthetic rollouts in a temp dir
and asserts the counts: old form, new form, a mixed sentence, a
mentioned-not-invoked code, `>qd` against `>q`, a model switch mid-session, a
partial read that omits the section (expected `unknown`), and a marker that
appears only in another file (expected `unknown`).

### New fixture `workflow_menu` (private store)

The user asked that `>q` be checked on a routine workflow decision. The four
existing fixtures are three substantive technical questions and one "agent is
busy" screen. None is a workflow menu, and all deliberately omit any
recommended label. So one fixture is added:

- A reconstructed screen, like the others: the followed agent has finished
  planning the same task the other fixtures use and asks a workflow question
  with one option it recommends and says why (the risk-mitigation disposition
  menu: no mitigations / apply recommended / choose per item), plus the UI's
  free-text and chat entries.
- It reuses the `working_wait` task and plan copies, so the context helper
  resolves a plan. Phase line `PHASE:PLAN|WAITING:WAITING`.
- No scorer reference or controls, because nothing is judged.
- It is committed in the aitasks_go repository by named paths (that checkout
  has unrelated uncommitted changes, which are not touched). Its provenance
  notes go in a new `fixtures/workflow_menu/PROVENANCE.md`; the shared
  `fixtures/PROVENANCE.md` is not edited. The commit is not pushed by me; the
  final report names it so the user can push it.
- **Fixture validation is scoped to each run, and the shared manifest is not
  changed.** Today `require_manifest` compares the whole store with
  `fixtures/MANIFEST.json`, so the new fixture would break it both ways: a
  store with the fixture is refused as `unlisted:`, and a regenerated
  manifest would refuse every other checkout of the store, where the new
  fixture does not exist. So:
  - `fixtures/MANIFEST.json` stays byte-identical. The pilot scenario list
    and `pilot_cells()` stay as they are.
  - `require_manifest` takes the scenarios of the run. It checks
    `instructions/`, `skill_listing/` and those scenarios' directories, with
    the same `unlisted:` / `changed:` / missing refusals inside that scope.
    Fixture directories of other scenarios are outside the scope. `pilot`,
    `preflight` and `smoke` pass the pilot scenarios, so they keep working on
    a store with or without the new fixture.
  - The new fixture is pinned by its own
    `fixtures/MANIFEST_workflow_menu.json` (store commit and per-file
    sha256, written by the same manifest code, which refuses untracked
    files). Only the t2368 runner requires it, for the cells that use it.
  - Offline tests: a store with an extra fixture directory passes the pilot
    validation; a changed or unlisted file inside a pilot scenario is still
    refused; the runner refuses a missing or changed `workflow_menu`.
  - The t2368 cells on `workflow_menu` can only be re-run from a checkout
    that has the private commit. That is stated in the README row.

### `adhoc_live_check.py`

It imports `harness` and reuses `resolve_agents`, `resolve_store`,
`require_manifest`, `Budget`, `Experiment.run_session` and `Cell`. Harness
defaults keep every existing `>q` path as it is.

- **Old wording:** the real frozen tree with `v1_baseline`.
- **New wording:** the frozen tree is copied to the scratchpad. In the copy the
  `>qd` bullet is inserted after the `>q` bullet, the `>pd` bullet and
  `plan-decisions.md` are edited, and `harness.FROZEN` points at the copy. The
  `>q` bullet itself comes from `v5_quick` through the normal span
  substitution. The real `frozen/` is not touched, so
  `test_freeze_record_matches_files` stays green.
- **Model:** `agents["codex"]["cli_id"]` is set per `Experiment` to
  `gpt-6.2-sol` or `gpt-6.1-sol`, both in the one batch `t2368`. After each
  session the runner checks `reported_model`. A mismatch is not counted as
  evidence, but its invocations stay charged. Reasoning effort is the user's
  Codex config (`high`), as in real use.
- **Validity by turn kind (before any paid run).** The validator calls a turn
  `valid` only after a screen and `--phase` capture, and `Experiment._finish`
  feeds that into the consecutive-failure counter that opens the circuit
  after three. A correct `>pd` turn needs no capture, so it would count as a
  failure. `SessionSpec` therefore gains a turn kind, set from the same
  `turn_prompt` the session sends:
  - `q` (default): unchanged.
  - `qd`: the `q` rule, and the startup read must also have returned the
    `>qd` bullet.
  - `pd`: the capture requirement is replaced. The turn must have read
    `plan-decisions.md` with output containing the step-4 text of the copy the
    sandbox served, and must have called `aitask_shadow_context.sh` with the
    stub's output delivered unmodified. Reading the plan file directly is
    allowed.
  - Kept for every kind: reported model present, `SKILL.md` sha unchanged and
    variant loaded at startup, no tmux or off-path helper use, tool-call and
    time limits, stub output match, non-empty answer.
  - Offline tests: two capture-less `>pd` answers followed by one failed `>q`
    turn leave the next cell runnable; a `>pd` turn that never read
    `plan-decisions.md` is not valid; a `>qd` turn without the bullet read is
    not valid; three real failures still open the circuit; existing `>q`
    results do not change.
- **Scoring:** the scan matcher over each valid turn's final text, plus my own
  read of each answer. No judge calls.
- **Privacy:** raw answers stay in the private store (`runs/t2368/`). The
  public repo gets counts only. `check_public.py --staged` runs before the
  commit. The store's run files are left uncommitted and named in the final
  report.

### Run matrix (revised; same approved budget)

One cell is one fresh session: a startup turn and one shortcode turn, so 2
`codex exec` invocations and about 68k non-cached tokens (pilot mean).

| # | model | wording | code | fixture | what it shows |
|---|---|---|---|---|---|
| 1 | 6.2 | new | `>q` | `workflow_menu` | quick answer on a routine workflow decision |
| 2 | 6.2 | old | `>q` | `workflow_menu` | control for row 1, same fixture |
| 3 | 6.2 | new | `>qd` | `file_selection` | full comparison on a substantive decision |
| 4 | 6.2 | new | `>q` | `file_selection` | pair of row 3: same skill text, same screen, the other command. Shows the depth follows the command and not the screen |
| 5 | 6.2 | new | `>pd` | `working_wait` | pros and cons lists per decision |
| 6 | 6.2 | old | `>pd` | `working_wait` | control for row 5, same fixture |
| 7 | 6.1 | new | `>qd` | `file_selection` | the new list format on the model that worked |
| 8 | 6.1 | new | `>pd` | `working_wait` | no regression of `>pd` on 6.1 |

**8 cells, 16 invocations, about 0.55M tokens, plus the reserve of 8
invocations. Hard cap 24 invocations; 1.0M non-cached tokens with headroom.**
This is the budget approved on 2026-11-27. The cell list is new, so approving
this plan confirms it.

What the matrix does not cover, stated so it is a choice:

- `>qd` has no old-wording control on its fixture. Row 4 took that slot,
  because without it the check could pass while the shadow picks the depth
  from the screen and ignores the command. The old `>q` control stays on
  `workflow_menu` (row 2).
- The quick `>q` is not run on gpt-6.1-sol. Its risk is low (a short answer
  with no required format) and 6.1 is no longer the shadow default.
- Each new wording has one answer per model. This is a go/no-go check, not a
  measurement.
- `>qd` is run on one substantive fixture, not on `go_versions` as well.
- No state without a question on screen is run for `>q` or `>qd`.
- The colon hypothesis is not tested.
- No Claude Code or OpenCode paid run.

**One shared, durable budget.**

- **One batch, one journal.** All cells run in batch `t2368` with one `Budget`
  and one journal (`runs/t2368/budget_journal.jsonl`), recovered on every
  start. The 6.2 and 6.1 cells use two `Experiment` objects that share it.
  The runner records the requested and reported model per cell in its own
  numbers-only `cells.jsonl`.
- **One runner process at a time.** `Budget` serializes reservations with an
  in-process lock only. The runner takes an exclusive, non-blocking `flock`
  on `runs/t2368/budget_journal.jsonl.lock` before it recovers the journal
  and holds it until it exits. A second runner refuses to start. The lock
  file is git-ignored.
- **24 invocations is a strict cap.** Under that lock, `Budget.acquire`
  reserves a slot in the journal before each launch and refuses the 25th,
  across restarts. A launch whose usage was never recorded stays counted.
- **1.0M tokens, with headroom checked at every invocation.** A small `Budget`
  subclass refuses in `acquire` when accrued tokens plus 200k would pass
  1.0M. Every launch goes through `acquire`: startup turns, shortcode turns,
  retries and resumed turns. The 200k is an estimate (five times the largest
  pilot call), not a bound, so the total can end above 1.0M by the excess of
  one call. The per-turn tool-call and time limits in `limits.json` limit a
  single call.

**Pass bar.**

- **`>q` (rows 1 and 4):** it says what is being decided and why it matters;
  it gives its own recommendation with a reason about the fixture's task. It
  has no Pros or Cons block, does not list the menu's free-text or chat
  entries as options, and is at most 1,500 characters (real-use median is
  about 900). Row 1 only, where the screen shows a recommended option: it
  names that option and the agent's reason, and if it differs, says why.
- **Depth follows the command (rows 3 and 4, same screen):** row 4 has no
  Pros or Cons block and row 3 has one per substantive option. Either one
  failing this is a miss for its shortcode.
- **`>qd` (rows 3 and 7):** the situation comes before any recommendation;
  every substantive option has a Pros block and a Cons block; the
  recommendation comes after the comparison; menu controls are not listed as
  options; on my read the points are about the fixture's task.
- **`>pd` (rows 5 and 8):** every decision it reports has a Pros block and a
  Cons block.
- Rows 2 and 6 are controls and have no bar. They are reported beside their
  pair.

**Revision, and what counts toward shipping.** A miss on either model allows
one revision of the wording for the shortcode that missed (for `>qd` and
`>pd`, the plain-heading form). Only answers produced by the exact final
wording count:

- Revising a shortcode voids every new-wording answer for it, passing ones
  included. All of its new-wording cells are re-run on the final text, the
  gpt-6.1-sol cell too: 2 cells (4 invocations) each for `>q` (rows 1, 4),
  `>qd` (rows 3, 7) and `>pd` (rows 5, 8).
- A revision of the shared steps 1-3 or 5 voids both `>q` and `>qd` (4 cells,
  8 invocations, the whole reserve).
- Before the production edit, the runner checks that the production `>q`
  bullet is byte-equal to `v5_quick.md`, and that the production `>qd`
  bullet, `>pd` bullet and `plan-decisions.md` are byte-equal to the edited
  copies the counted cells ran on.
- The reserve of 8 covers any two shortcodes. It does not cover all three
  (12), or two after a failed launch used part of it. In that case I do not
  ship: I list the cells not run on the final wording and ask before any
  further spend or any production edit.
- A miss on the final wording, on either model, stops the task before the
  production edit. There is no second revision. I report the numbers and ask.

## Verification

1. `python3 tests/test_shadow_scan_sessions.py`
2. `python3 tests/test_shadow_q_harness.py`
3. `bash tests/test_skill_render_aitask_shadow.sh`
4. `bash tests/test_shadow_phase_advisory.sh`
5. `python3 tests/test_concern_parser.py` and
   `python3 tests/test_shadow_disposition_surfaces.py`
6. `./.aitask-scripts/aitask_skill_verify.sh`
7. `python3 aidocs/benchmarks/shadow_q/check_public.py --staged`
8. In `website/`: `python3 check_links.py --build`
9. `python3 aidocs/benchmarks/shadow_q/scan_sessions.py --exclude-task 2368`
   prints the before table. The live-check counts go in the plan's final
   notes.
10. After landing: the scan is re-run on real use some days later. The
    confirmed "after" mitigation task `rescan_shadow_q_pd_real_use` (created at
    Step 8d) carries this. It is not also put on a manual-verification
    checklist at Step 8c.

## Other agents

- **Codex:** the live check above.
- **Claude Code:** `scan_sessions.py --agent claude` gives numbers from local
  transcripts, if any shadow turns exist there. No paid run.
- **OpenCode:** not measured. Recorded as a gap.

## Notes to send (after the commit)

With `./ait note … --from 2368`:

- **t2187** and **t2179_2:** production `>q` changed and `>qd` was added, so
  the frozen v1 baseline no longer describes production and the experiment's
  single-command premise no longer holds. The free session-log scan and its
  numbers. The gpt-6.2-sol base-instruction finding, stated as a hypothesis.
  The harness now takes a turn prompt and has a `workflow_menu` fixture.
- **t2186:** a session-log scan is a zero-cost evidence source to consider.

## Risk

### Code-health risk: low
- The harness and its validator gain a turn kind with the old behaviour as
  default, covered by offline tests, and two new dev scripts sit beside them.
  Production code is not touched, only skill text, its goldens and its tests
  · severity: low · → mitigation: none

### Goal-achievement risk: medium
- gpt-6.2-sol may not follow the list format, because the cause is a
  hypothesis · severity: medium · → mitigation: none (the live check with its
  one revision and stop rule is part of the plan)
- The live check has one answer per wording and model on replay fixtures.
  Real answers could still mix pros and cons in one sentence, or `>q` could
  drift long · severity: medium · → mitigation: rescan_shadow_q_pd_real_use
- Users must learn a second code. Someone who types `>q` expecting the full
  comparison gets the short answer · severity: low · → mitigation: none (the
  `>q` bullet, the capability list and the docs name `>qd`)

### Planned mitigations
- timing: after | name: rescan_shadow_q_pd_real_use | type: test | priority: medium | effort: low | inline_risk: high | added_complexity: low | addresses: one answer per wording and model on replay fixtures; real answers could still mix pros and cons or >q could drift long | desc: Some days after t2368 lands, re-run aidocs/benchmarks/shadow_q/scan_sessions.py on real shadow sessions, record the numbers for >q, >qd and >pd on gpt-6.2-sol as two samples split by the skill text each session read (old / new, with n for each, same matcher), read how >q answers on workflow menus and >qd answers look, and report >px / >t and Claude counts
