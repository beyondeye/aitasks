---
Task: t2280_measure_shadow_width_composer.md
Base branch: main
Output branch: main
---

# t2280 — Measure the composer-payload grammar at shadow pane widths

## Context

t2275 will gate the minimonitor's shadow-recheck Enter on the same composer-payload proof
the sitrep delivery uses (`review_loop.composer_payload` + `agent_request_delivery.payload_matches`,
t2211_4). That grammar was measured live only on 120x30 panes (`tests/sitrep_request_fixtures.py`;
rule table in `aiplans/archived/p2211/p2211_4_*.md` `## Measurement`). Shadow panes are split at
`shadow_pane_width` (default 60, `monitor_core.py:4665`), so the ~110-char recheck prompt from
`review_loop.compose_recheck_prompt` wraps there. If the width rules (claude W−4, codex W−3, opencode
border−5 / wrap at content−1) do not hold at 60, every recheck would hold with
`pre_enter_composer_unprovable` / `_changed`. That fails closed but kills the auto-recheck loop.
This task measures it before t2275 relies on it, stores the captures as fixtures, and pins them with a test.

Environment already checked: claude 2.1.322, codex-cli 0.167.0, opencode 1.18.34, tmux 3.8. These are
the same versions t2211_4 measured, so any difference is down to width, not version.

## Implementation steps

### 1. Spike driver (scratchpad, not committed)

Write `<scratchpad>/t2280/spike.py`, a small Python driver run with `PYTHONPATH=.aitask-scripts:.aitask-scripts/lib`.
It imports `review_loop` for `shadow_state` / `compose_recheck_prompt` and calls `tmux` through `subprocess`.
That is a throwaway scratch script, so the `.aitask-scripts` raw-tmux gateway rule does not apply.

- **Isolated server.** `SOCK=$(mktemp -d /tmp/ait_t2280_XXXXXX)`, and every call is `tmux -S $SOCK/s -f /dev/null …`.
  The server is never the user's, and `kill-server` only ever targets `-S $SOCK/s`. It uses `/tmp` because the
  scratchpad path is too long for AF_UNIX `sun_path` (t2142). Agent cwd is `$SOCK/proj`, a neutral path, so the
  captured headers carry no home directory or username.
- **Subcommands**, so I can react to boot dialogs by hand instead of scripting blind:
  `start <agent> <W>` (`new-session -d -x W -y 30 -c $SOCK/proj <agent>`), `cap <agent> <W>`
  (`capture-pane -p -e -S -15`, the production extent), `type <agent> <W> <text>` (`send-keys -l`, the same
  literal typing `minimonitor_app.py:6006` uses for the recheck), `key`, `clear`, and `run <agent> <W>`.
  `clear` sends C-c only while `shadow_state == busy`, because C-c on an empty Codex composer quits Codex.
- **`run <agent> <W>` sequence**, after the agent is booted and any trust dialog has been answered by hand:
  1. Warm-up turn: type `Reply with the single word OK`, Enter, then wait for `ready`. A shadow that rechecks
     has always finished at least one round, so the conversation layout is the realistic one (for opencode
     this is the full-width `conv_` box, not the centred home box).
  2. For each phase `PLAN`, `IMPLEMENT`, `None`: type `compose_recheck_prompt(phase, 1)`, wait until two
     consecutive captures match (stable), capture as `recheck_plan` / `recheck_impl` / `recheck_generic`,
     then `clear` and wait for `ready`.
  3. `appended`: the PLAN prompt plus ` plus my own words`. Request = the PLAN prompt.
  4. `history_draft`: type `an unrelated draft of mine`. Request = `Reply with the single word OK`, which is in
     the history.
  5. Edge triplets at the expected wrap width ww (claude W−4, codex W−3, opencode from the measured border):
     `"a"*k + " " + "b"*w + " tail"` with `k+1+w` = ww−1, ww, ww+1. k ≈ ww/2 → `edge_<k>_<total>`. These
     probe the word-wrap boundary exactly, which is the rule in question. They pin `wrap_width` only.
  6. `midtoken`: `">q c12 " + ("abcdefghijklmnopqrstuvwxyz" * 8)[:3*W]`. This is one unbroken token longer than
     two rows, so it forces at least two **hard breaks**. That is the only case where `payload_matches`
     consults `content_width`; a break with a space only reads `wrap_width`. I confirmed this on the 120 set:
     with `content_width + 7`, all 12 `edge_*` captures still match, and all 4 `*_midtoken` captures fail.
     Record the observed hard-break rows: the row lengths, and whether claude breaks in place while
     codex/opencode first move the token to its own row, as at 120.
  7. `post_enter`: type the generic prompt, wait stable, Enter, capture at +0.5 s. Then Escape (twice for
     opencode) and `kill-session`.
  Each capture is saved as `(agent, W, shadow_state(raw), request, raw)` to `<scratchpad>/t2280/captures.json`.
- Run for claude, codex and opencode at W=60 (the default) and W=44 (one narrower width). That is 6 runs with
  one tiny model turn each, plus the post-Enter submit (interrupted right away).
- If an agent cannot be booted (not authenticated, crashes), record it as unmeasured with the reason and do
  not fake it.

### 2. Evaluate and, only if needed, fix the grammar

Run `composer_payload(raw, agent, W)` + `payload_matches(payload, request)` over every capture. Expected:
genuine (`recheck_*`, `edge_*`, `midtoken`) → payload not None and a match, with ≥2 rows for `recheck_*`;
`appended` / `history_draft` → payload not None and no match; `post_enter` → no match.

If any agent fails at 60 or 44: read its plain capture and fix only that agent's branch in
`.aitask-scripts/monitor/review_loop.py` (`_claude_payload` ~L1117, `_codex_payload` ~L1145, `_opencode_payload` ~L1174),
keeping every existing delimiter check. Re-pin against both fixture sets: `tests/test_sitrep_request_delivery.py`
(120) and the new test. Record the corrected rule in this plan. Shared-file gate before the edit:
`git diff --quiet HEAD -- .aitask-scripts/monitor/review_loop.py`.

### 3. `tests/shadow_recheck_fixtures.py` (new)

- Generated from `captures.json` by a scratchpad script: `repr()` of each raw, keys sorted, and **no trimming**.
- Docstring in the same shape as `sitrep_request_fixtures.py`: date, tmux and agent versions, pane geometry
  (Wx30 single-pane session), the `-S -15 -e` extent, the typing path (`send-keys -l`), the tuple shape, and the
  naming scheme `<agent>_w<W>_<variant>` (variants listed above). It also says the names are a stable
  interface consumed by t2275 step 5.
- Scrub check before writing: grep every raw for `$USER`, `$HOME`, the hostname, the git user name, and the
  email local parts from `userconfig.yaml` / `emails.txt`. If anything is found outside the composer rows,
  replace it with a same-length placeholder so the row geometry is unchanged, and list each substitution in
  the docstring. If a capture cannot be scrubbed safely, drop it and say so, the way t2211_4 dropped
  `codex_at_end`.
- `UNMEASURED: dict[str, str]` maps agent → reason. It is empty when all three were measured.

### 4. `tests/test_shadow_recheck_composer.py` (new, unittest, sys.path setup copied from `test_sitrep_request_delivery.py`)

- `test_every_measured_agent_and_width_is_covered`: for each agent in `PAYLOAD_GRAMMAR_AGENTS` minus `UNMEASURED`,
  and each W in (60, 44), every required variant exists.
- `test_the_recheck_requests_are_the_real_prompts`: each `recheck_*` request equals
  `compose_recheck_prompt(phase, 1)`. If the prompt wording changes, this goes red, which signals that the
  widths need measuring again.
- `test_every_genuine_capture_is_proved`: payload not None, `payload_matches` True, and ≥2 rows for `recheck_*`
  (the wrap is really exercised).
- `test_appended_text_and_a_foreign_draft_never_match`: payload not None, no match. For `history_draft`, also
  assert the request is on screen, so a plain search would find it.
- `test_a_post_enter_capture_is_never_the_prompt`.
- `test_the_width_rules`: `content_width` / `wrap_width` per agent as functions of W (the measured table, pinned).
  On its own this only restates the parser's formula, so it is backed by the two perturbation tests below,
  which tie each width to live evidence.
- `test_the_content_width_is_measured_by_the_hard_breaks`: every `midtoken` capture matches, and its payload has
  ≥2 rows that fill exactly `content_width`. With `dataclasses.replace(payload, content_width=cw±1)` it **no
  longer matches**. So a wrong content-width rule is rejected by real captures, not just restated.
- `test_the_wrap_width_is_measured_by_the_edges`: for each agent × W, the three `edge_<k>_<total>` captures match,
  and their **observed layouts** pin both sides of the threshold directly from the captures, not from the
  matcher:
  - `total ≤ ww` (both the ww−1 and the ww capture): `payload.lines[0] == "a"*k + " " + "b"*w`, i.e. the b-word
    fitted. This pins that the agent wraps only *above* ww.
  - `total = ww+1`: `payload.lines[0] == "a"*k` and `payload.lines[1]` starts with `"b"*w`, i.e. it wrapped. This
    pins that the agent wraps already at ww+1.
  - The matcher perturbation is kept only on the side its contract rejects: with `wrap_width+1`, the ww+1 capture
    no longer matches (its break would no longer be justified). There is **no** `wrap_width−1` assertion.
    `payload_matches` rejects a break only when the next word would have fitted (`row+1+word <= wrap_width`), so
    lowering the threshold only accepts more breaks, and a single-row fit is never checked. The layout
    assertions above cover that side. (Checked on the 120 set: all 12 edge captures still match at
    `wrap_width−1`.)
- The content-width perturbation stays ±1 on both sides, because there the contract does reject both ways: a hard
  break is accepted only when `display_width(row) == content_width`, exactly.
- Checked against the 120 set during planning. `cw±1` rejects all 4 midtoken captures and no edge capture.
  `ww+1` rejects exactly the first wrapped edge capture per agent (`claude_edge_100_117`, `codex_edge_100_118`,
  `opencode_edge_50_70`, `opencode_edge_90_111`). `ww−1` rejects nothing.

### 5. Record

Add a `## Measurement` section to this plan with agent × width: composer rows for each prompt, content width
(from the midtoken hard-break rows), wrap width (from the edges), the wrap rule observed at the edges, the
hard-break behaviour, match result, and any layout difference against 120. Include
the scrub result and any unmeasured agent.

## Verification

- `python3 -m unittest tests/test_shadow_recheck_composer.py` (new) and `tests/test_sitrep_request_delivery.py`
  (the 120 set, unchanged) both pass.
- If `review_loop.py` changed: also `tests/test_review_loop.py`, `bash tests/test_sitrep_request_delivery_live.sh`,
  and `bash tests/run_all_python_tests.sh --test-dir tests` (last line: `PYTHON SUITE: PASSED`).
- Negative control (throwaway): patch `payload_matches` to always-True, and the appended test must go red.
- The layout assertions and contract-backed perturbations above are the committed controls for the two width rules. Before committing, confirm
  once that they are not vacuous: temporarily change `_claude_payload`'s `width - 4` to `width - 5`, and the
  claude midtoken/edge tests must go red. Revert by re-editing the line, not with `git restore`.
- `git grep -n "$USER\|$(hostname)" tests/shadow_recheck_fixtures.py` returns nothing.

## Step 9 (Post-Implementation)

Commit `test: Measure the composer grammar at shadow pane widths (t2280)` (plus `review_loop.py` if it was
fixed). Then archive per Step 9. Step 8e: send t2275 a note naming the fixture module, the names and the
measured rules (or the unmeasured agent), because its step 5 renders the fake composer from them.

## Risk

### Code-health risk: low
- Only new test files, unless the grammar needs a fix. In that case the fix is per-agent and stays re-pinned
  against the 120 fixtures, and the live test covers the sitrep delivery · severity: low · → mitigation: none
  (covered by step 2's re-pin)

### Goal-achievement risk: low
- The spike pane is a single-pane Wx30 session, not a split pane beside a real agent, and it runs after a
  one-line warm-up turn, not a full review round. The composer grammar depends on pane width and composer
  state, not on the history above it, and the history-draft case covers echoed history. · severity: low ·
  → mitigation: none
- An agent may not boot (authentication) at measurement time. Step 1 records it as unmeasured and t2275 must
  treat it as unprovable, which the task explicitly allows · severity: low · → mitigation: none

## Measurement (spike, 2026-11-12, tmux 3.8, isolated `-S /tmp/ait_t2280_*/s -f /dev/null` server)

Agents: claude 2.1.322, codex-cli **0.167.2** (it had updated since t2211_4's 0.167.0), opencode 1.18.34.
One single-pane W x 30 session per agent and width, cwd a neutral `/tmp/ait_t2280_*/proj`, agent env with
`CLAUDE*` / `AITASK*` / `TMUX*` / `AIT_*` removed (an inherited `CLAUDE_CODE_*` var otherwise added a warning row
to claude's footer). Text typed with `send-keys -l`; captures `capture-pane -p -e -S -15`; each run after one
warm-up turn. 80 captures in the first run, 42 more in the second (end-of-text) → 122 in `tests/shadow_recheck_fixtures.py`. No agent unmeasured.

| agent | W | recheck rows (plan/impl/generic) | content width (midtoken rows) | wrap width (edges fit/fit/wrap) | hyphen break | result |
|---|---|---|---|---|---|---|
| claude | 60 | 3/3/2 | 56 = W−4 (56,56,56,19) | 56: 55 fit, 56 fit, 57 wrap | never (compound moves whole at 55/56/57) | all match |
| claude | 44 | 3/3/3 | 40 = W−4 (40,40,40,19) | 40: 39 fit, 40 fit, 41 wrap | never | all match |
| codex | 60 | 3/3/2 | 57 = W−3 (6,57,57,57,9; token moved to own row first) | 57: 56 fit, 57 fit, 58 wrap | yes: hyphen-ended prefix stays iff ≤ 57 (56, 57 break after `-`; 58 moves) | hyphen_28_56 **failed pre-fix** |
| codex | 44 | 3/3/3 | 41 = W−3 (6,41,41,41,9) | 41: 40 fit, 41 fit, 42 wrap | yes: ≤ 41 | hyphen_20_40 **failed pre-fix** |
| opencode | 60 | 3/3/2 | 51 = border−5 = W−9 (6,51,51,51,27) | 50 = cw−1: 49 fit, 50 fit, 51 wrap | yes: prefix ≤ 51 = cw stays (49,50,51 break; 52 moves) | recheck_plan/impl + hyphen_25_49/50 **failed pre-fix** |
| opencode | 44 | 4/4/3 | 35 = W−9 (6,35,35,35,27) | 34: 33 fit, 34 fit, 35 wrap | yes: ≤ 35 (33,34,35 break; 36 moves) | recheck_plan/impl + hyphen_17_33/34 **failed pre-fix** |

- **All the W-relative width rules hold at 60 and 44** (claude W−4, codex W−3, opencode content = border−5,
  word wrap at content−1); hard breaks fill exactly the content width; claude breaks a long token in place, codex
  and opencode move it to its own row first — as at 120. Appended text and the foreign draft are rejected
  everywhere; post-Enter at +0.5 s reads `working` (claude, codex) or already `ready` (opencode, W=44).
- **Defect found: hyphen breaks.** codex and opencode also break a line right after a `-` inside a word. The
  120 set never exercised it (no hyphen landed on a wrap). `payload_matches` read such a break as a hard break,
  which must fill the content width, so the real PLAN/IMPLEMENT recheck prompt (`re-run`, `plan-challenge`,
  `sub-procedure`) was **unprovable for opencode at both shadow widths** (rows `…re-run the plan-` /
  `challenge …` at 60; `…round 1: re-` / `run the plan-challenge review sub-` at 44), and codex only escaped by
  luck. In opencode the `re-`/`run` break at 44 (32 + `run` 3 = 35 = cw) shows the fragment's trailing space
  counts, i.e. the same cw−1 threshold as its word wrap.
- **Corrected rule (shipped, revised in Change Request 1):** `ComposerPayload.hyphen_breaks` (codex, opencode
  True; claude False). A break is justified iff the piece it moved would not have fit: `row + sep + piece > limit`
  (sep 1 at a consumed space, 0 after a row ending in `-`). The piece, for a hyphen-breaking agent, is the
  smallest one it could have kept (`[^\s-]*-|[^\s-]+`: up to the first hyphen); for claude the whole word.
  The limit follows the piece's ending, all measured: before a space `wrap_width`; ending in a hyphen or ending
  the text `content_width`. Otherwise the row is judged as a hard break. No leniency remains.
- **End-of-text (measured in the second run):** `endword_*` / `endhyphen_*` at cw−1, cw, cw+1 for all agents at
  60/44, plus opencode at 120: a final piece stays on the row up to cw itself (opencode's cw−1 applies only before a
  space). Codex at exactly cw moves its cursor onto an empty row → `composer_payload` None (unprovable: a typed
  blank line looks identical) — pinned, not loosened.
- Scrub: every capture checked for user name, home path, hostname, git name and email local parts — no hit,
  nothing substituted.

## Final Implementation Notes

- **Actual work done:** spike driver (scratchpad) measured claude/codex/opencode at W=60/44; new
  `tests/shadow_recheck_fixtures.py` (122 captures after Change Request 1, `UNMEASURED = {}`, `WIDTHS`), new
  `tests/test_shadow_recheck_composer.py` (17 tests after Change Request 1: coverage, real-prompt pin, proof, rejection, post-Enter,
  width rules tied to midtoken/edge layouts, hyphen bound from layouts, load-bearing + unjustified-break tests);
  grammar fix in `review_loop.py` (`ComposerPayload.hyphen_breaks`, set by `_codex_payload` /
  `_opencode_payload`, grammar comment) and `agent_request_delivery.py` (`_FRAGMENT_RE`,
  `_moved_piece`, `_hyphen_justified`, `payload_matches` hyphen branch + docstring).
- **Deviations from plan:** added the `hyphen_<k>_<p>` probes (all agents, both widths, opencode also at cw+1)
  once the first opencode run failed — needed to pin the break rule per agent before fixing it. The fix had to
  touch `payload_matches` (agent_request_delivery.py), not only `composer_payload`.
- **Issues encountered:** agent env inheritance from this session (fixed by filtering the server env); codex
  updated to 0.167.2 mid-window.
- **Key decisions:** the moved piece is the smallest one the agent could have kept (conservative: smaller only
  makes a break harder to justify), and its fit limit follows its ending — every ending measured, none assumed.
  The codex cursor-row case at exactly W−3 stays unprovable (fail closed) instead of loosening `_codex_payload`,
  because a typed blank line renders identically.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/agent_request_delivery.py:176 — payload_matches rejected genuine codex/opencode hyphen breaks (fixed here) and accepted typed newlines before a hyphenated compound and after an opencode final word at the content width (fixed here); latent in the t2211_4 sitrep delivery at 120 columns as well`
  - `.aitask-scripts/monitor/review_loop.py:1145 — _codex_payload is None when the last composer row fills exactly W-3 (cursor wraps to a blank row): such a sitrep request or recheck prompt holds instead of submitting; by design (indistinguishable from a typed blank line), recorded, not fixed`
- **Negative controls (throwaway, mocks only):** `payload_matches` always-True → 35 red (all appended / draft /
  post-Enter + perturbations); claude rule W−5 → 26 red (midtoken + edges + rules); no hyphen breaks (pre-fix
  state) → 10 genuine captures unprovable (opencode recheck_plan/impl ×2 widths + 6 hyphen probes).
- **Notes for t2275:** fixtures names are stable (`<agent>_w<W>_<variant>`); the minimonitor fake's composer must
  hyphen-break for codex/opencode; `payload_matches` (which t2275 moves to `agent_submit.py`) now has the hyphen
  branch and `_FRAGMENT_RE` / `_moved_piece` / `_hyphen_justified` must move with it; a codex composer whose last row fills exactly W−3 is unprovable (cursor row), so its fake must render that case as None.
- **Verification run:** `tests/test_shadow_recheck_composer.py` 14 OK; `tests/test_sitrep_request_delivery.py` +
  `tests/test_review_loop.py` 231 OK; `tests/test_sitrep_request_delivery_live.sh` PASS (all mutants red as
  required). Full suite: 12004 passed, 6 skipped, serial carve-out 15 passed, but `PYTHON SUITE: FAILED`.
  The only failures (1 collection error + 3 collection-guard assertions) all name `test_aitask_questions_mcp`, a
  module **another session staged** in the shared tree (`import anyio` — not installed); unrelated to this change.

## Post-Review Changes

### Change Request 1 (2026-11-12 11:30)
- **Requested by user:** the hyphen branch compared every moved piece against `wrap_width`, but opencode keeps a
  hyphen-ended piece up to `content_width`. A typed newline after `a*42-` before `b*7-c*10` (43 + 8 = 51 = cw)
  was accepted, so Enter could be authorised on changed multiline input. Apply the measured boundary per
  ending, measure or reject unmeasured endings, add a negative regression.
- **Verified:** reproduced (True before the fix). The word branch had the same class of false acceptance
  for hyphen-breaking agents: it measured the whole compound (`\S+`), so a newline before `b*10-c*40` whose
  first piece fitted was accepted. Also reproduced.
- **Changes made:** `_moved_piece` (smallest piece + ending-based limit) used by both the word and hyphen branches;
  the end-of-text ending was measured instead of assumed (second spike run, 42 captures incl. opencode@120);
  `tests/test_sitrep_request_delivery.py::test_opencode_wraps_one_column_short_of_a_hard_break` corrected. Its
  synthetic final-word-at-cw "justified" assertion contradicted the measurement (opencode keeps it on the row), so
  it now asserts the space-followed case (unchanged rule) plus the final-word case at cw (rejected) and cw+1
  (accepted). New tests: retyped real opencode composer through `composer_payload` (rejected at cw, accepted at
  cw+1), the compound case, and the `EndOfTextTests` (layouts + `content_width+1` contract perturbation).
- **Controls:** limit-always-`wrap_width` (the reviewed defect) → 13 red; whole-compound word piece → 3 red;
  previous controls still red (51 / 34 / 58).
- **Files affected:** `.aitask-scripts/monitor/agent_request_delivery.py`, `.aitask-scripts/monitor/review_loop.py`
  (comment), `tests/shadow_recheck_fixtures.py`, `tests/test_shadow_recheck_composer.py` (17 tests),
  `tests/test_sitrep_request_delivery.py` (one test corrected).
- **Verification:** the three unit modules 248 OK; live delivery test PASS; pytest collects the new module (17).
