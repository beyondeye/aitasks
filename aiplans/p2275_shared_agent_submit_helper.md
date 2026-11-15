---
Task: t2275_shared_agent_submit_helper.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2275 — One shared agent-submit helper (minimonitor recheck + sitrep request), carrying t2274's payload proof

## Context

Two copies of the same pre-Enter / mode-gate / bounded-retry submit loop exist:

- `.aitask-scripts/monitor/minimonitor_app.py` `_submit_shadow_prompt` (≈L6011-6170), fed by
  `_fire_shadow_recheck` (≈L5910-6009, writes the prompt with `send_keys(..., literal=True)`);
- `.aitask-scripts/monitor/agent_request_delivery.py` `deliver_sitrep_request`, phase-3 loop
  (L366-418, t2211_4, e16e440e4).

They can drift. A t2001-style fix applied to one silently misses the other. They already
have drifted: t2211_4 added a **per-Enter composer-payload proof** (`review_loop.composer_payload`
+ `payload_matches`) that the minimonitor lacks, which is defect t2274. t2274's session was
killed mid-pick (stale lock, no plan, no code), and the user chose to **fold t2274 into t2275**. So this
task extracts ONE helper that owns the shared sequence *including* the payload proof, and
switches both callers to it. Each caller keeps its own result labels.

## Step 0 — housekeeping (runs right after ExitPlanMode, before externalization)

These are the planning-phase Ad-Hoc Fold writes, deferred only because plan mode is read-only.
They run immediately, so the fold is in place even though the `measure_shadow_width_composer`
"before" task stops this session at Step 7. Steps 1-6 below run on the re-pick, after that task lands.
On the re-pick the plan is force re-verified, and the measured fixtures feed the step-5 fake renderer.

1. t2274's stale state (dead pid 479253, verified gone): `./.aitask-scripts/aitask_lock.sh --unlock 2274`,
   `./.aitask-scripts/aitask_update.sh --batch 2274 --status Ready --assigned-to ""`, then commit with
   `./.aitask-scripts/aitask_task_commit.sh -m "ait: Revert t2274 to Ready (session ended without abort)" <t2274 file>`.
2. Ad-Hoc Fold: `aitask_fold_validate.sh --exclude-self 2275 2274` → `aitask_fold_content.sh <t2275> <t2274>
   | aitask_update.sh --batch 2275 --desc-file -` → `aitask_fold_mark.sh --commit-mode fresh 2275 2274`
   (expect `COMMITTED:`).
3. Shared-file gate before the first edit of each code file: `git diff --quiet HEAD -- <file>`
   (`minimonitor_app.py`, `agent_request_delivery.py`, `review_loop.py`, the two test modules).
   Leave the foreign dirty `.aitask-scripts/lib/task_utils.sh` alone, and never commit it.

## Design

### New module `.aitask-scripts/monitor/agent_submit.py` (pure mechanics, no labels)

Moved here from `agent_request_delivery.py` (which re-exports them, so `d.payload_matches`,
`d.display_width` and every importer keep working): `display_width`, `_WORD_RE`, `payload_matches`,
its t2280 private helpers `_FRAGMENT_RE`, `_moved_piece`, `_hyphen_justified` (part of
`payload_matches` since c3cc5f580 — hyphen-break justification for codex/opencode),
`_pane_width` (renamed `pane_width`, kept as `_pane_width` alias in the old module).

*Re-pick verification (2026-11-15, HEAD 57b660ff0):* `agent_submit.py` absent; all target files
clean; current anchors — `agent_request_delivery.py` L163-247 matcher block, L328 `_pane_width`,
L345 `deliver_sitrep_request`; `minimonitor_app.py` L5992 `_fire_shadow_recheck`, L6093
`_submit_shadow_prompt`. t2281/t2283 touched the minimonitor but not the submit loop. t2280
note (acknowledged): fixtures in `tests/shadow_recheck_fixtures.py` (widths 60/44, all three
agents measured); the minimonitor fake composer for codex/opencode must hyphen-break like the
`hyphen_*`/`recheck_*` fixtures; a codex last row of exactly W-3 reads unprovable (kept
fail-closed, not hit at 60/44).
A new module avoids a circular import: minimonitor must not import the sitrep module, and
the sitrep module imports the helper.

```python
# neutral observed outcomes — each caller maps these to ITS labels
PRE_NOT_BUSY, PRE_UNPROVABLE, PRE_CHANGED, PRE_MODE_UNREADABLE, PRE_IN_MODE,
ENTER_NOT_SENT, POST_SUBMITTED, POST_UNVERIFIED, POST_UNPROVABLE, POST_CHANGED,
EXHAUSTED, STOPPED

@dataclass(frozen=True)
class Observation:            # what the attempt's pre-Enter reads saw
    attempt: int; state: str; in_mode: bool | None; mode_name: str

@dataclass(frozen=True)
class SubmitOutcome:
    kind: str; attempt: int; state: str = ""      # SHADOW_* of the deciding read
    obs: Observation | None = None                # last pre-Enter observation
    enter: tuple[str, str] = ("", "")             # transport's (state, reason)
    stop: object = None                           # checkpoint's stop value

async def submit_typed_text(monitor, pane, agent, text, *, send_enter, sleep,
                            checkpoint=None, before_retry=None) -> SubmitOutcome
```

Per attempt, `for attempt in range(review_loop.SHADOW_SUBMIT_RETRIES + 1)`:

1. `attempt > 0` → `await before_retry()` (sitrep's `pause("before_retry")` seam).
2. `await sleep(COMPOSER_DRAIN_SECONDS)`; capture tail; `pane_width`; `query_pane_mode`.
   **The mode is the last read**, so the order is capture → width → mode.
3. `checkpoint("pre_enter", obs)`. It is **synchronous**, so no await can sit between the mode read and
   the Enter. A non-None return → `STOPPED` (the minimonitor's token check).
4. Classify: `state != BUSY` → `PRE_NOT_BUSY`; payload None → `PRE_UNPROVABLE`;
   `not payload_matches` → `PRE_CHANGED`; mode None → `PRE_MODE_UNREADABLE`; mode → `PRE_IN_MODE`.
5. `await send_enter()` returns `monitor_core` dispatch `(state, reason)`; anything but
   `DISPATCH_SENT` → `ENTER_NOT_SENT` carrying it. **Contract: `send_enter` is a zero-arg
   *async* callable** (`async def`, awaited exactly once per Enter). Both callers' adapters are
   `async def`. A plain lambda returning a tuple would send the key and *then* raise `TypeError` at the
   `await`, skipping post-Enter verification. That was the review finding, reproduced: the send
   happens before the exception. `test_agent_submit` pins the contract with a sync-callable case that
   must fail before any key is sent. The helper checks `inspect.iscoroutinefunction(send_enter)` up
   front and raises `TypeError` without touching the pane.

**Lookup-site rule (keeps every existing patch seam live).** The helper resolves its collaborators
by **module attribute at call time**: `monitor_core.capture_raw_tail`,
`monitor_core.query_pane_mode`, `review_loop.shadow_state`, `review_loop.composer_payload`, and its own
module global `payload_matches`. It never uses `from … import` for them. The real-server mutants in
`tests/test_sitrep_request_delivery_live.sh` patch `mc.query_pane_mode` and `rl.composer_payload`.
A from-import would let the "no pre-Enter mode read" mutant survive.
6. drain; capture; READY/WORKING → `POST_SUBMITTED`; not BUSY → `POST_UNVERIFIED(state)`;
   BUSY → re-read width + payload: None → `POST_UNPROVABLE`; mismatch → `POST_CHANGED`;
   exact match → swallowed Enter, retry.

After the loop: `checkpoint("exhausted", obs)` (non-None → `STOPPED`), then `EXHAUSTED`.

### Caller A — `deliver_sitrep_request` (labels byte-identical)

Phase 3 becomes one `submit_typed_text` call with
`async def send_enter(): return await asyncio.to_thread(monitor_core.guarded_send_key, monitor, ident, "Enter", nonce())`
(a fresh nonce per Enter, as today; the only suspension is inside the dispatch itself, as today),
`before_retry = pause("before_retry")`, `checkpoint=None`, plus a mapping table:

| outcome | DeliveryResult (unchanged) |
|---|---|
| PRE_NOT_BUSY dialog / unknown / other | UNKNOWN `pre_enter_dialog` / `pre_enter_unreadable` / `text_not_in_composer` |
| PRE_UNPROVABLE | UNKNOWN `composer_unprovable` |
| PRE_CHANGED attempt 0 / >0 | TYPED `composer_changed` / UNKNOWN `composer_changed_after_enter` |
| PRE_MODE_UNREADABLE / PRE_IN_MODE | TYPED_MODE_UNREADABLE / TYPED_IN_MODE |
| ENTER_NOT_SENT skipped+in_mode / skipped other / else | TYPED_IN_MODE `enter_skipped` / refused:identity_changed `enter_skipped` / UNKNOWN `enter_unacknowledged` |
| POST_SUBMITTED | SUBMITTED |
| POST_UNVERIFIED s | UNKNOWN `post_enter_<s>` |
| POST_UNPROVABLE / POST_CHANGED | UNKNOWN `composer_unprovable_after_enter` / `composer_changed_after_enter` |
| EXHAUSTED | TYPED `submit_unconfirmed` |

One accepted observable difference: a pre-Enter refusal now happens after the mode read, not
before it, so a failure path costs one extra `display-message`. The labels do not change. The event
order on every Enter path (`capture, width, mode, enter`) is unchanged. `test_a_ready_agent_gets_the_request_submitted`
pins the success sequence. The early-exit cases assert codes and `"enter" not in events` only,
so they hold. I'll confirm that per test in the pre-phase table.

### Caller B — minimonitor (labels kept + the new t2274 holds)

`_submit_shadow_prompt` becomes a thin mapper over `submit_typed_text` with an **async adapter
around the synchronous sender**. Its body has no internal `await`, so there is no suspension point
between the checkpoint and the keystroke:

```python
async def send_enter():
    ok = monitor.send_keys(shadow_pane, "Enter")
    return (monitor_core.DISPATCH_SENT, "") if ok else (monitor_core.DISPATCH_FAILED, "send_keys")
```

`sleep=_composer_drain` is read from the module global at call time, so `_stub_drain` still works.
The checkpoint sets
`self._loop_delivery_detail = {**_pane_mode_detail(...), "pre_enter_verdict": obs.state}` and then
returns `HOLD_DELIVERY_SUPERSEDED` when `not ctrl.delivery_valid(token)`. That reproduces today's
"token check after the attempt's last await, ahead of every branch" and the pre-exhaust check.

| outcome | minimonitor result |
|---|---|
| STOPPED | `("not_ready", HOLD_DELIVERY_SUPERSEDED)` (unchanged) |
| PRE_NOT_BUSY dialog / unknown / ready-working | hold `pre_enter_dialog` / hold `pre_enter_unreadable` / fail `text_not_in_composer` (unchanged) |
| PRE_MODE_UNREADABLE / PRE_IN_MODE | hold `pre_enter_mode_unreadable` / `pre_enter_in_mode` (unchanged) |
| ENTER_NOT_SENT | fail `enter_send_failed` (unchanged) |
| POST_SUBMITTED | `("sent", prompt)` (unchanged) |
| POST_UNVERIFIED dialog/unknown | warning toast + `("sent", prompt)` (unchanged) |
| EXHAUSTED | fail `submit_unconfirmed` (unchanged) |
| **PRE_UNPROVABLE** (new, t2274) | hold **`HOLD_PRE_ENTER_COMPOSER_UNPROVABLE`** |
| **PRE_CHANGED** (new, t2274) | hold **`HOLD_PRE_ENTER_COMPOSER_CHANGED`** |
| **POST_CHANGED / POST_UNPROVABLE** (new, t2274) | warning toast "recheck sent, but the shadow composer then held other text — submission could not be verified" + `("sent", prompt)`; **no retry Enter** |

Why these holds and not disarms: the composer is BUSY, so `shadow_prompt_ready` is not-True and the
loop provably holds without re-writing (the same argument as `HOLD_PRE_ENTER_IN_MODE`, pinned by
`AmbiguousVerdictsHoldTests`). Why "sent" after the Enter: the prompt left the composer and
foreign text replaced it, so the prompt most likely went. A retry would submit the user's draft.
A hold would re-fire and duplicate the round. This mirrors the existing post-Enter
dialog/unknown "sent + warn" rule and t2009's `confirm_fire` handling of a stale "sent".

`review_loop.py`: two new `HOLD_*` constants, `LOOP_REASON_MESSAGES` entries, and `LOOP_HOLD_BANNERS`
entries (≤76 cells, e.g. "⟳ holding: shadow composer changed — Enter withheld"). The messages must
**not** contain "left in the shadow composer", because `test_the_leftover_message_is_used_only_where_text_is_left`
pins that set.

**Transport decision (the task asked for one): the minimonitor keeps `send_keys`.** Adopting
`guarded_send_key` needs a shadow `RunIdentity` read at fire time. Its frozen-shadow semantics are
unmeasured. It only makes sense together with a guarded *paste* of the prompt, which changes the
write transport t1525's drain sweep measured. Its one gain is closing the documented t2001 residual
(a mode entered in the single round trip before the Enter). The helper takes `send_enter` as a
callable, so that switch becomes a one-line change later. I'll offer it as a follow-up task, not
part of this one.

## Implementation steps

### Pre-phase (risk mitigations)

1. [pin_caller_labels] Before editing either caller, add `tests/test_submit_labels_pinned.py`. It is a
   table-driven characterization over **both** callers, using scripted fakes like the existing ones:
   one row per outcome branch of today's code, giving input tails / modes / acks / send results and
   the expected label. For minimonitor that is `(outcome, code)` plus the `_loop_delivery_detail` keys
   and the number of `send_keys("Enter")` calls; for sitrep it is `(code, detail)` plus the `enter` event
   count. Include the supersession rows: disarm during the pre-Enter reads → `delivery_superseded` with
   no Enter; disarm during the last post-Enter capture → `delivery_superseded`, not `submit_unconfirmed`;
   a non-BUSY post-Enter read after a disarm still returns `sent`. Run it green on the pre-refactor
   HEAD (record the run in this plan), then keep it green through steps 2-4. The **only** rows allowed
   to change are the t2274 branches: minimonitor appended text, a foreign draft after the Enter, and an
   unprovable composer. Mark those rows `t2274` and record their old→new labels in the plan.

1. Create `monitor/agent_submit.py` as designed (module docstring: the shared contract, the
   ordering invariant, and the neutral vocabulary). Move `display_width` / `payload_matches` /
   `pane_width` there, and re-export them from `agent_request_delivery.py`. **One-shot
   verification, not a committed test:** right after the move, run a throwaway scratchpad script
   over the explicit moved list `("display_width", "_WORD_RE", "_FRAGMENT_RE", "_moved_piece",
   "_hyphen_justified", "payload_matches", "pane_width")`.
   It is an AST scan of top-level bindings, imports excluded, and checks that each name is defined
   in `agent_submit.py` and in no other module of `monitor/`, and that `agent_request_delivery` imports
   each back. Record the script verbatim and its output in this plan under `## Verification
   record`. A copy left behind would otherwise pass every other check.
2. Rewrite `deliver_sitrep_request` phase 3 onto the helper with the mapping table above.
   Keep the module docstring's phase-3 description and point it at the helper.
3. Add the two hold codes, messages and banners in `review_loop.py`.
4. Rewrite `_submit_shadow_prompt` onto the helper. Keep its long docstring rationale, edited to
   say the gates now live in `agent_submit` and to add the payload-proof paragraph. Leave
   `_fire_shadow_recheck` untouched, except that it may check the prompt with
   `request_line_error(prompt)`: `compose_recheck_prompt` already guarantees single-spaced, one line.
   Add a unit test, not a runtime check.
5. Tests:
   - `tests/test_agent_submit.py` (new): drive the helper directly with a scripted fake. Cover every
     outcome kind; that the mode read is immediately before every Enter; that the checkpoint stops
     before any verdict and before EXHAUSTED; that `before_retry` runs only on attempts > 0; and that
     there is no retry on POST_CHANGED.
   - `tests/test_minimonitor_concern_action.py`: `_LoopFakeMon.tmux_run_async` dispatches
     `display-message` on its format. A `pane_width` query answers width and does NOT count as a mode
     query or fire `on_mode_query`. Its typed tail renders the **actual composer text** into the
     shadow agent's composer (claude: the `❯\xa0` line of `claude_short` with greedy wrap at W−4;
     codex/opencode via their fixtures). New t2274 regressions: appended user text → no Enter, hold
     `pre_enter_composer_changed`; BUSY foreign draft after the Enter → no retry Enter, "sent" + warning;
     plus a **pre-fix control**, run once as a throwaway negative control, showing the BUSY-only gate
     accepting both. It is recorded in the plan, not committed as a must-fail test.
   - `tests/test_sitrep_request_delivery.py`: unchanged assertions must pass as-is. That is the
     label-pinning proof for caller A.
   - `tests/test_sitrep_request_delivery_live.sh`: **retarget the occurrence-count mutant** from
     `(d, "payload_matches", …)` to `(agent_submit, "payload_matches", …)`, the helper's real
     lookup site. Rebinding the re-export in `agent_request_delivery` no longer reaches the matcher.
     Keep its requirement that **both** (j) and (k) turn red, and update the header comment. The
     `mc.query_pane_mode` / `rl.composer_payload` patches stay as they are, because the lookup-site
     rule keeps them live. `test_agent_submit` adds a cheap unit twin: patching
     `agent_submit.payload_matches` to always-True must turn the appended-text case into an Enter.
   - `tests/test_review_loop.py` reason-code guards pick up the new codes automatically.
6. Docs: `aidocs/framework/shadow_agent.md` item 9. In the pre-Enter gate, `SHADOW_BUSY` **and** an exact
   composer payload authorise the Enter. Add the two new holds to the verdict table. In the post-Enter
   gate, BUSY is a swallowed Enter only with an exact payload. Name `monitor/agent_submit.py` as the one
   implementation shared with the sitrep delivery. One short pointer goes into the
   `agent_request_delivery.py` docstring.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (last line `PYTHON SUITE: PASSED`), and
  focused: `python -m pytest tests/test_agent_submit.py tests/test_sitrep_request_delivery.py
  tests/test_minimonitor_concern_action.py tests/test_review_loop.py tests/test_review_loop_log.py
  tests/test_minimonitor_concern_smoke.py tests/test_sitrep_tui_requests.py`.
- `bash tests/test_sitrep_request_delivery_live.sh`: real-server cases (a)-(l) stay green, and every
  mutant turns its cases red. The retargeted occurrence-count mutant must report (j) **and** (k) red.
  As a negative control, run it once with the mutant left on the old `d.payload_matches` target and
  confirm it reports a surviving mutant. That proves the retarget is what makes it bite.
- `bash tests/test_no_raw_tmux.sh` (the helper goes through `monitor.tmux_run_async` / gateway only).
- Label pinning: the pre-phase table (below) is green on the pre-refactor HEAD and on the result.

## Risk

### Code-health risk: low
- Both callers are load-bearing delivery paths. The refactor must keep minimonitor's supersession
  invariants exactly (t2001: a token check after the attempt's last await and ahead of every branch,
  plus one before the exhausted return; t2009: a non-BUSY "sent" is not re-checked). It must also keep
  the mode as the last read before every Enter on both paths. A moved await or a reordered check
  silently changes which lifecycle a fatal code kills · severity: low (residual — addressed by inline
  pre-phase pin_caller_labels) · → mitigation: inline pre-phase pin_caller_labels
- The minimonitor test fake (`_LoopFakeMon`) has to change: width-query dispatch, and a composer
  that renders the real prompt. A fake change can mask a behaviour change in a 4.8k-line suite
  · severity: low (residual — the label table is proven on pre-refactor HEAD with its own fakes,
  independent of `_LoopFakeMon`) · → mitigation: inline pre-phase pin_caller_labels
- The two Enter transports stay different behind one helper (`send_keys` vs guarded `if-shell`).
  The t2001 residual stays open on the minimonitor side · severity: low · → mitigation: t2309

### Goal-achievement risk: medium
- The composer grammar (`composer_payload`) was measured at 120-column panes only. Shadow panes
  are about 60 columns (`shadow_pane_width`), so the ~110-char recheck prompt wraps there in every agent.
  If the W-relative width rules do not hold at 60, every recheck holds with
  `pre_enter_composer_unprovable` / `_changed`. That fails closed, with no wrong submit, but it breaks
  the auto-recheck loop · severity: medium · → mitigation: t2280

### Planned mitigations
- timing: pre-phase | name: pin_caller_labels | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — supersession/ordering invariants and test-fake masking | desc: table-driven label characterization of both submit callers, proven green on pre-refactor HEAD and kept green except the marked t2274 rows
- timing: before | name: measure_shadow_width_composer | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — composer grammar unmeasured at shadow pane widths | desc: live spike with real claude/codex/opencode in an isolated tmux server at the shadow width (60 cols, plus one narrower) holding the real recheck prompt and an appended-text variant; store the captures as fixtures and assert composer_payload + payload_matches accept the genuine ones and reject the edited ones (fix the grammar if they do not) | created: t2280
- timing: after | name: guarded_enter_for_shadow | type: enhancement | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: code-health — two Enter transports; t2001 single-round-trip residual on the minimonitor | desc: give the minimonitor's send_enter (and possibly the prompt write) the identity- and mode-guarded if-shell dispatch through agent_submit's transport callable, with a shadow RunIdentity read at fire time | created: t2309

## Step 9 (Post-Implementation)

Commit `refactor: Share one guarded agent-submit helper between minimonitor and sitrep (t2275)`
by path, then the standard Step 9 archival. t2274 is archived with t2275 as folded. Offer the
guarded-Enter transport follow-up.

## Final Implementation Notes

- **Actual work done:** `monitor/agent_submit.py` (new) owns the matcher (`display_width`,
  `_WORD_RE`, `_FRAGMENT_RE`, `_moved_piece`, `_hyphen_justified`, `payload_matches`,
  `pane_width`), moved verbatim from `agent_request_delivery.py` (which re-exports them) and
  `submit_typed_text` with the neutral outcome vocabulary as designed. `deliver_sitrep_request`
  phase 3 is one helper call + `_delivery_result` (labels unchanged). `_submit_shadow_prompt` is a
  checkpoint + async `send_keys` adapter + mapper; the t1606/t2001 rationale comments moved into
  the mapper. `review_loop.py`: `HOLD_PRE_ENTER_COMPOSER_CHANGED` / `_UNPROVABLE` + messages
  (no "left in the shadow composer") + banners. `aidocs/framework/shadow_agent.md` item 9 updated.
  Transport decision as planned: the minimonitor keeps `send_keys` (guarded-Enter follow-up).
- **Deviations from plan:**
  - New test helper `tests/composer_render.py`: the minimonitor fake's composer renderer
    (greedy wrap over the measured `ComposerPayload` parameters, substituted into the
    `<agent>_w<W>_recheck_plan` capture). Needed because the loop tests use round-2 prompts and
    the fixtures hold round 1. Verified against every genuine capture (100/100 row-exact,
    `test_agent_submit.ComposerRenderTests`). One measured agent difference surfaced:
    claude fills the current row before hard-breaking an over-long token (`FILL_LONG`);
    codex/opencode start it on a new row. Its `composer_payload` is bound at import so a test
    that patches the production reader (the pre-fix control) does not change what it renders.
  - `_LoopFakeMon`: the three canonical TYPED captures (`_TYPED_RENDER`) now mean "render the
    typed text"; width queries answer `shadow_width` (default 60) and are not mode queries;
    `pane_width_reply` overrides only the width answer.
  - `tests/test_minimonitor_concern_smoke.py`: the real-tmux Claude composer stub drew a bare
    `❯ buf` line, which the measured grammar cannot prove; it now draws the measured region
    (rule row, `❯`+NBSP, two-space continuations wrapped at W-4, rule row), painted with
    absolute addressing so nothing scrolls into history. Not in the plan's file list.
  - `RecheckPromptShapeTests` (in `test_agent_submit.py`) is the step-4 prompt-shape unit test.
- **Issues encountered:** the first pre-fix control run "passed" because the patched
  `review_loop.composer_payload` broke the fake's renderer and the script counted only
  failures, not errors. Fixed by binding the renderer's reader at import and counting errors.
- **Key decisions:** post-Enter BUSY with a foreign / unprovable payload → `sent` + warning, no
  retry (as planned); the two new pre-Enter outcomes are holds.
- **Upstream defects identified:** None

## Verification record

### Pre-phase pin_caller_labels on pre-refactor HEAD (f9b5888cd, monitor/ clean)

`tests/test_submit_labels_pinned.py` rows driven through a scratch runner that expects `old`
for t2274 rows: `MISMATCHES: 0` (21 minimonitor rows, 17 sitrep rows). t2274 rows, old → new:

| row | pre-refactor | now |
|---|---|---|
| t2274_appended_text | sent, 1 Enter | not_ready `pre_enter_composer_changed`, 0 Enters |
| t2274_unprovable_composer | sent, 1 Enter | not_ready `pre_enter_composer_unprovable`, 0 Enters |
| t2274_foreign_draft_after_enter | sent, 2 Enters | sent + warning, 1 Enter |
| t2274_unprovable_after_enter | sent, 2 Enters | sent + warning, 1 Enter |

Every other row identical before and after (the committed test asserts `expect`).

### One-shot moved-name AST check (step 1)

```python
"""One-shot (t2275 step 1): each moved name is defined (top-level, imports
excluded) in agent_submit.py and in no other monitor/ module, and
agent_request_delivery imports each back from agent_submit."""
import ast, pathlib, sys
MOVED = ("display_width", "_WORD_RE", "_FRAGMENT_RE", "_moved_piece",
         "_hyphen_justified", "payload_matches", "pane_width")
mon = pathlib.Path(".aitask-scripts/monitor")
defs = {}
for f in sorted(mon.glob("*.py")):
    tree = ast.parse(f.read_text())
    for node in tree.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for n in names:
            if n in MOVED or n == "_pane_width":
                defs.setdefault(n, []).append(f.name)
ok = True
for n in MOVED:
    where = defs.get(n, [])
    good = where == ["agent_submit.py"]
    ok &= good
    print(f"{n:18} defined in {where} {'OK' if good else 'BAD'}")
print(f"{'_pane_width':18} defined in {defs.get('_pane_width', [])} (alias must be import-only)")
ok &= "_pane_width" not in defs
tree = ast.parse((mon / "agent_request_delivery.py").read_text())
imported = {}
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == "monitor.agent_submit":
        for a in node.names:
            imported[a.name] = a.asname or a.name
for n in MOVED:
    good = n in imported
    ok &= good
    print(f"agent_request_delivery imports {n:18} as {imported.get(n)} {'OK' if good else 'BAD'}")
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
```

Output:

```
display_width      defined in ['agent_submit.py'] OK
_WORD_RE           defined in ['agent_submit.py'] OK
_FRAGMENT_RE       defined in ['agent_submit.py'] OK
_moved_piece       defined in ['agent_submit.py'] OK
_hyphen_justified  defined in ['agent_submit.py'] OK
payload_matches    defined in ['agent_submit.py'] OK
pane_width         defined in ['agent_submit.py'] OK
_pane_width        defined in [] (alias must be import-only)
agent_request_delivery imports display_width      as display_width OK
agent_request_delivery imports _WORD_RE           as _WORD_RE OK
agent_request_delivery imports _FRAGMENT_RE       as _FRAGMENT_RE OK
agent_request_delivery imports _moved_piece       as _moved_piece OK
agent_request_delivery imports _hyphen_justified  as _hyphen_justified OK
agent_request_delivery imports payload_matches    as payload_matches OK
agent_request_delivery imports pane_width         as _pane_width OK
RESULT: PASS
```

### Pre-fix control (t2274 regressions vs a BUSY-only gate)

```python
"""Throwaway pre-fix control (t2275): neutralise the payload proof so the
shared loop authorises on SHADOW_BUSY alone (the pre-t2274 minimonitor gate),
then run the two t2274 regressions. Both must FAIL (an Enter is sent)."""
import sys, unittest
from unittest import mock
sys.path.insert(0, ".")
import test_minimonitor_concern_action as t
from monitor import agent_submit, review_loop
busy_only = [mock.patch.object(agent_submit, "payload_matches", lambda p, e: True),
             mock.patch.object(review_loop, "composer_payload", lambda *a, **k: object())]
for p in busy_only: p.start()
suite = unittest.TestSuite([
    t.ComposerPayloadProofTests("test_appended_user_text_gets_no_enter"),
    t.ComposerPayloadProofTests("test_a_foreign_draft_after_the_enter_gets_no_retry_enter"),
])
r = unittest.TextTestRunner(verbosity=0).run(suite)
for test, tb in r.failures + r.errors:
    print("FAILED AS EXPECTED:", test.id().rsplit(".", 1)[-1], "|", tb.strip().splitlines()[-1][:120])
print("CONTROL:", "BITES" if len(r.failures) == 2 and not r.errors else "DOES NOT BITE")
```

Result: all 6 subtests fail with the Enter sent (appended: `1 != 0` Enters for claude, codex,
opencode; foreign draft: `2 != 1` for all three). The script's final `CONTROL:` line compares
against 2 test-level failures and so printed "DOES NOT BITE"; the six recorded subtest
failures are the evidence. With the real gate all six pass.

### Live (`tests/test_sitrep_request_delivery_live.sh`)

Real-server cases (a)-(l) OK; every mutant red on its cases; retargeted occurrence-count
mutant: (j) red (`received '>t c12 plus my words\r'`), (k) red (`'>t c12\r\r'`). Negative
control (a scratch copy with the mutant left on `d.payload_matches`): rc=1,
`(j) stayed green`, `(k) stayed green`, so the retarget is what makes it bite.

### Suites

- `test_no_raw_tmux.sh`: ALL TESTS PASSED.
- focused set (agent_submit, submit_labels_pinned, sitrep_request_delivery (unchanged, 46),
  shadow_recheck_composer, minimonitor_concern_action, review_loop, review_loop_log,
  minimonitor_concern_smoke, sitrep_tui_requests): all pass.

## Post-Review Changes

### Change Request 1 (2026-11-15 20:10)
- **Requested by user:** (review finding, medium, blocking) `_submit_shadow_prompt` mapped
  `PRE_CHANGED` / `PRE_UNPROVABLE` to the pre-submission holds regardless of `out.attempt`.
  With captures [prompt, prompt, foreign draft] one Enter had already gone, yet the result was
  `pre_enter_composer_changed` ("nothing submitted"), no warning; `abort_fire` keeps the work
  latch and streak and stamps no cooldown, so a later tick could fire a duplicate round.
- **Changes made:** on `attempt > 0` those two outcomes take the post-Enter treatment
  (`sent` + warning, no retry); attempt 0 keeps the holds. The sitrep mapping already split
  `PRE_CHANGED` by attempt (`composer_changed_after_enter`) and reports `PRE_UNPROVABLE` as
  `unknown`, never a pre-submit claim, so it is unchanged. New pinned rows
  `t2274_retry_pre_read_changed` / `_unprovable` (old: sent, 2 Enters; now: sent + warning,
  1 Enter) and the end-to-end regression
  `ComposerPayloadProofTests.test_a_changed_composer_at_the_retry_is_sent_with_a_warning`
  (draft / resize at the retry pre-read). Negative control: the split disabled in place (exact
  string swap, restored byte-identical, verified with `cmp`) turns both red; with it, green.
  `shadow_agent.md` item 9 states the first-attempt-only scope of the holds.
- **Files affected:** `.aitask-scripts/monitor/minimonitor_app.py`,
  `tests/test_submit_labels_pinned.py`, `tests/test_minimonitor_concern_action.py`,
  `aidocs/framework/shadow_agent.md`
