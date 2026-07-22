---
Task: t1187_fix_failed_verification_t1170_item2.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t1187 — Fix the failed live shadow concern auto-offer (t1170 item #2)

## Context

t1167 made `concern_parser.py` tolerant of a `[priority | region]` bracket
hard-wrapped by an agent TUI. Its manual-verification task t1170 then ran five
items. Four passed. **Item #2 failed**:

> Spawn a Codex shadow via minimonitor `e` on a plan review at a narrow pane
> width (~55 cols), with a concern whose region is a long full path — confirm
> the auto-offer FIRES (pre-fix it silently reported no concerns)

The follow-up template (`aitask_verification_followup.sh`) records no failure
reason, and the user does not recall the specifics — so **there is no live
ground truth for this task**. The plan therefore targets the defects that
inspection proves are present on that exact path, and the acceptance signal is a
re-run of the live scenario.

Crucially, item #1 *passed* by capturing a **disposable 55-column pane holding
only the known split marker** and parsing it. So the pure capture→parse pair is
proven; everything item #2 exercises **beyond** that is unproven. Three real
defects live in exactly that gap.

### D1 — the short-region producer rule is missing from all three plan-review producers

`concern-format.md:52-58` calls the ≤ ~30-char region rule ("never a full repo
path") the **primary defense** against the split-marker hazard. Grep says it
exists in exactly one producer:

| Producer (`.claude/skills/aitask-shadow/`) | states the short-region rule |
|---|---|
| `impl-challenge.md:319-325` | **yes** |
| `plan-challenge.md:77` | no — "names the plan section / axis" |
| `plan-assumptions.md:80` | no — "names the assumption category" |
| `plan-diagnose-errors.md:70` | no — "names the offending skill / helper (a script name…)" |

The failing item is a **plan review** whose **region is a long full path**. On
the plan-review path the primary defense was never stated to the agent, so the
producer was free to emit precisely the input t1167 can only *partially*
recover. (All four files are identifiable by the marker phrase `load-bearing
for minimonitor's parser`.)

### D2 — minimonitor reads the shadow pane at the shallow depth

`minimonitor_app.py:1298-1302` runs `aitask_shadow_capture.sh <pane>` with **no
`--deep`** → `SHADOW_CAPTURE_LINES` = 200. Every plan-review flow uses `--deep`
(400) *because plan-review-sized output truncates at 200*
(`aidocs/framework/shadow_agent.md:29-35`). What minimonitor must find here **is**
plan-review output: the human-readable list plus a machine block whose bodies
carry the "full framing" mandated at `plan-challenge.md:80-87`.

Measured against `plan-challenge.md`'s own two example concerns rendered at 55
columns: 10 and 8 rows → **~45 rows for a 5-concern block**, on top of a prose
list of the same substance, the shadow's greeting/menu, and Codex's tool-call
echoes. The narrow width in the failing item is the amplifier — it is what turns
a comfortable window into a marginal one. `_capture_shadow_text`'s docstring
claims it "reuses the shadow skill's own capture path", but it does not reuse
the depth that path uses for this content.

### D3 — a clipped opening fence is a *silent* false negative

`_last_block_region` keys off `text.rfind(_OPEN)` and returns `None` when
absent. Verified in this environment:

```
input:  items… + "===END-CONCERNS===" (opening fence clipped by the window)
parse_concerns    -> []
has_concern_block -> False
```

So a capture window that starts *inside* a block is indistinguishable from "the
shadow raised nothing" — the auto-offer stays silent **and** the `c` hotkey says
"No concerns detected on the shadow pane". That is exactly the pre-t1167 symptom
the item was written to catch, reachable by a completely different mechanism, and
undiagnosable by the user.

D1 and D2 make the failure *reachable*; D3 makes it *invisible*. The fix
addresses all three: remove the producer-side cause, remove the capture-side
cause, and make any residual occurrence self-reporting and recoverable.

## Implementation

### 1. `concern_parser.py` — detect a clipped block head

Add one pure predicate next to `has_concern_block`:

```python
def block_head_truncated(text: str) -> bool:
    """True when the capture window clipped the opening fence of the block.

    A closing fence with **no opening fence anywhere in the capture** means the
    window starts inside a block: the shadow did emit concerns, but the capture
    is too shallow to see where they began. Both runtime entry points key off
    the last opening fence, so this is otherwise indistinguishable from "no
    concerns at all" — a silent false negative (t1187).

    Scoped to the **newest** block, matching the runtime's last-block-wins
    semantics: if any opening fence is present, the newest block's head is by
    definition intact and the runtime can parse it, so an *older* clipped
    block is not the user's problem and must not raise a capture-window
    warning. (A `find`-ordering variant — "the first closing fence has no
    opening fence before it" — is wrong: it fires when an older block was
    clipped and a newer review is simply still streaming.)

    Deliberately a *detector*, not a recovery: the text above an orphan closing
    fence is untrusted (a shadow doc read into the pane can contain literal
    ``- [priority | region]`` example lines — the t1123 hazard), so it is never
    parsed into forwardable concerns. Callers re-capture deeper instead.

    Known blind spot: a block clipped at the head that is *also* still
    streaming (no closing fence captured yet) is indistinguishable from a pane
    with no block at all, and reads ``False``. Accepted — the deeper window in
    the caller is the defense there.
    """
    return _CLOSE in text and _OPEN not in text
```

`parse_concerns` / `has_concern_block` are **unchanged** — no head-recovery.

### 2. `minimonitor_app.py` — plan-review depth + a bounded deeper retry

- Add `_SHADOW_DEEP_RETRY_LINES = 1500` beside `_SHADOW_CAPTURE_TIMEOUT` (line 86).
- `_capture_shadow_text(self, shadow_pane, *, lines=None)`: always pass
  `--deep`; when `lines` is given, run with `SHADOW_PLAN_CAPTURE_LINES=<lines>`
  in a copy of `os.environ` (`env=` on `create_subprocess_exec`). Update the
  docstring: it now reuses the plan-review depth as well as the path.
- `action_pick_concerns` (the `c` hotkey, explicit user action — extra cost is
  fine): when `parse_concerns` is empty **and** `block_head_truncated(text)`,
  re-capture **once** with `lines=_SHADOW_DEEP_RETRY_LINES` and re-parse. If it
  now yields concerns, open the picker as normal. If it still does not, notify
  (severity `warning`): `"Shadow's concern block is cut off above the capture
  window — increase SHADOW_PLAN_CAPTURE_LINES"`. Genuine absence keeps the
  existing plain `"No concerns detected on the shadow pane"`.
- `_maybe_offer_concerns` (per-tick — **no** retry): when `has_concern_block` is
  false and `block_head_truncated(text)`, notify the same warning **once per
  shadow pane**, deduped via a new `self._truncation_warned: set[str]`
  (initialised beside `_last_concern_block_payload`, line 266). Discard the pane
  from the set whenever `has_concern_block(text)` is true, so a later complete
  block re-arms the warning.

### 3. The three plan-review producers — state the primary defense

In `plan-challenge.md`, `plan-assumptions.md` and `plan-diagnose-errors.md`,
extend the existing `` `region` `` bullet (keeping each file's own region
vocabulary) with the constraint already carried by `impl-challenge.md:319-325`:
region MUST stay short (≤ ~30 chars) — a `basename.ext:LINE` locus or an axis
label, **never a full repo path** (full paths go in the body) — because the
whole `[priority | region]` marker must survive on one rendered row.

Inline rather than a pointer to `concern-format.md`: these are prompt files read
at runtime, and an extra file read is a rule the agent may skip. The duplication
is made safe by the drift guard in §5.

### 4. Docs

- `concern-format.md` — under the region bullet, note that **every** producer
  states the rule and that the guard enforces it; add a short **Capture-window
  contract**: minimonitor captures the shadow pane at plan-review depth, and a
  block whose opening fence falls outside the window is reported as *truncated*,
  never as "no concerns".
- `aidocs/framework/shadow_agent.md:29-35` — the `--deep` sentence currently
  scopes the deep window to the shadow's own plan sub-procedures; add that
  minimonitor's concern capture uses it too, and why.
- `aitask_shadow_capture.sh` header + `show_help` — describe `--deep` as the
  plan-review depth used by the plan sub-procedures **and** minimonitor's
  concern capture.

No cross-agent port task: the shadow sub-procedures are Claude-only and the
`.agents/` / `.opencode/` trees carry redirect wrappers (`concern-format.md:120-124`).

### 5. Tests

`tests/test_concern_parser.py` — `TestBlockHeadTruncated`:
- orphan close + items → `True`, **and** `parse_concerns == []` /
  `has_concern_block is False` (pins that detection did not become recovery);
- complete block → `False`;
- no fences at all → `False` (negative control: genuine absence is not truncation);
- open-with-no-close (still streaming) → `False`;
- older **complete** block + newer streaming block → `False`;
- **clipped older block + newer still-streaming block → `False`** — the
  false-positive the `find`-ordering variant produces; pins that a mid-stream
  review never triggers a "capture window" warning;
- **clipped older block + newer complete block → `False`** — same family, and
  the newest block parses fine, so no warning is warranted.

`tests/test_concern_parser.py` — `TestProducerShortRegionRule` (drift guard, in
the style of `TestShadowDocsNotParserLive:238`):
- enumerate `.claude/skills/aitask-shadow/*.md` containing `load-bearing for
  minimonitor's parser`; assert the set is exactly the four known producers (so
  a new producer cannot slip past the guard);
- assert each states the short-region constraint, via a module-level
  `_states_short_region_rule(text)` helper;
- **negative control:** call that helper on synthetic producer text with the
  rule removed and assert it is flagged — proving the guard can fail without
  mutating repo files.

`tests/test_minimonitor_concern_action.py`:
- `test_capture_uses_plan_review_depth` — **prod-argv smoke**: monkeypatch
  `asyncio.create_subprocess_exec`, call the *real* `_capture_shadow_text`, and
  assert argv is `[<…/aitask_shadow_capture.sh>, "--deep", "%5"]`. (Today every
  test stubs this method out, so no test sees the real CLI invocation.)
- `test_deep_retry_overrides_capture_lines` — with `lines=` set, argv is
  unchanged and `env["SHADOW_PLAN_CAPTURE_LINES"] == "1500"`.
- `test_pick_retries_deeper_on_truncated_head` — first capture head-truncated,
  second (deeper) capture complete → picker opens with the recovered concerns.
- `test_pick_warns_when_deeper_retry_still_truncated` — both captures truncated
  → exactly one `warning` notify mentioning the capture window; no modal.
- `test_pick_plain_message_when_genuinely_no_block` — negative control: the
  message stays `"No concerns detected on the shadow pane"`.
- `test_auto_offer_warns_once_per_pane` — truncated capture warns on the first
  tick, is silent on the second, and re-arms after a complete block is seen.

**`tests/test_minimonitor_concern_smoke.py` — disposable-tmux capture→notify
integration smoke (new file).** Everything above feeds *synthetic strings* into
a stubbed `_capture_shadow_text`, so it can all pass while the real pipeline
still produces no auto-offer. This smoke closes that gap for the segment that
can be automated: **real tmux pane → real `aitask_shadow_capture.sh` → real
`_capture_shadow_text` → real `has_concern_block` → `notify`**. Only the two
tmux *lookups* are stubbed (`_find_own_agent_snapshot`, `_find_shadow_pane_for`
return the live pane id); `_capture_shadow_text` is **not** stubbed. `_FakeMon`
needs no `get_pane_option`, so `_update_shadow_freshness` no-ops cleanly, and
`_set_shadow_stale_banner` already swallows the missing widget.

Fixture pane (mirrors `tests/test_shadow_capture.sh:120-166`, including its
`SKIP` when tmux is unavailable): a detached session on a private socket
(`AITASKS_TMUX_SOCKET`) sized **55×10** — narrow, like the failing scenario, and
a pinned height so the capture-window arithmetic is deterministic. It prints
filler, then an opening fence, ~60 item rows (including a Codex-style
mid-bracket split of a long full-path region), a closing fence, then a short
tail. Both depth env vars are pinned per invocation.

- `test_deep_window_reaches_the_block_and_notifies` — with
  `SHADOW_PLAN_CAPTURE_LINES=400`, `_maybe_offer_concerns` emits the
  `"Shadow raised concerns"` notify.
- `test_shallow_window_reports_truncation_not_silence` — **negative control /
  proof the smoke can fail**: same pane, window pinned just below the opening
  fence, and first assert the *intermediate* state (the captured text contains
  the closing fence and lacks the opening fence — so a drift in the row
  arithmetic fails loudly instead of passing vacuously), then assert the
  capture-window warning fires and no `"Shadow raised concerns"` notify does.

Together these prove the depth is load-bearing end-to-end rather than asserting
a flag string.

**Explicitly NOT covered by any automated test** — these stay live-only and are
the acceptance signal below: the `e` launch and `@aitask_shadow_target` binding,
the Codex CLI renderer's actual wrapping at ~55 columns, and refresh-tick
timing. The smoke substitutes a hand-built pane for the renderer, so it proves
the *plumbing*, not that Codex's output survives it.

## Risk

### Code-health risk: low
- `--deep` doubles the per-tick capture window (200 → 400 lines) on a ~3s timer
  · severity: low · → mitigation: covered in-task — the cost is dominated by the
  subprocess spawn, not the line count, and `_SHADOW_CAPTURE_TIMEOUT` (3.0s)
  already bounds it; the deeper 1500-line window is confined to the explicit `c`
  hotkey and capped at one retry.
- Inlining the short-region rule into three more prompt files creates a
  four-copy duplication · severity: low · → mitigation: covered in-task by the
  §5 drift guard (enumeration assertion + per-file assertion + negative
  control).
- `block_head_truncated` is a new public parser entry point that could drift
  from the two existing predicates, and a mis-scoped version would nag the user
  with a bogus "increase the capture window" warning on a normal mid-stream
  review · severity: low · → mitigation: covered in-task — it is pure, shares
  the module's fence constants and the runtime's last-block-wins scoping, and is
  pinned by seven cases of which **five must stay `False`**, including the two
  clipped-older-block false positives that the `find`-ordering variant produces.

### Goal-achievement risk: medium
- **No live ground truth exists for the original failure**, so the fixes address
  the defect *classes* that make the reported symptom reachable rather than a
  confirmed root cause; the true cause could be something else entirely (e.g. a
  Codex renderer artifact never observed here) · severity: medium · →
  mitigation: partly covered in-task by the disposable-tmux capture→notify smoke
  (§5), which proves the real capture path end-to-end instead of asserting a
  flag; the residue — the `e` launch, the Codex renderer, refresh timing — is
  **explicitly live-only** and its acceptance signal is the re-run in
  Verification, not the test suite. D3 is the hedge: if the failure recurs from
  a different cause, the UI now names the capture window instead of saying
  nothing, so the next report carries a diagnosis.
- The producer rule (D1) is a prompt-level instruction and cannot be enforced at
  runtime · severity: low · → mitigation: accepted and already documented as
  such in `concern-format.md`; t1167's bounded rejoin remains the structural
  backstop beneath it.

Before/after mitigation tasks were proposed (a "before" spike to capture a real
Codex shadow pane as ground truth, and an "after" live re-run) and the user
declined both: every code-health risk is mitigated inside this task by the §5
tests, and the goal-achievement risk is discharged by the live re-run in
Verification plus the Step 8c manual-verification offer, rather than by a
separate follow-up task.

## Verification

Automated:

```bash
python3 -m unittest tests.test_concern_parser -v
python3 -m unittest tests.test_minimonitor_concern_action -v
python3 -m unittest tests.test_minimonitor_concern_smoke -v   # needs tmux; SKIPs without
bash tests/test_shadow_capture.sh
bash tests/run_all_python_tests.sh
shellcheck .aitask-scripts/aitask_shadow_capture.sh
./.aitask-scripts/aitask_skill_verify.sh
```

(`pytest` is unavailable in this venv — use `unittest`, per p1167's notes. The
aggregate runner has known pre-existing `test_tui_switcher_agent_launch`
failures unrelated to this diff.)

The smoke must be shown to **fail** on the shallow window before it is trusted:
confirm `test_shallow_window_reports_truncation_not_silence` exits non-zero if
its intermediate assertion is inverted, so a drift in the row arithmetic cannot
let it pass vacuously.

**Live acceptance — the automated suite CANNOT establish this, so it is the sole
acceptance signal for the `e` launch, the Codex renderer at ~55 columns, and
refresh timing. It re-runs t1170 item #2:** in
a tmux window, start an agent, press `e` in minimonitor to spawn the Codex
shadow (`shadow` already defaults to `codex/gpt5_6_terra` in
`codeagent_config.json`), run a plan review at ~55 columns, and confirm the
`"Shadow raised concerns — press 'c' to pick"` auto-offer fires and `c` forwards
the canonical `- [priority | region] body` payload. Then force the D3 path with
`SHADOW_PLAN_CAPTURE_LINES=40` and confirm `c` reports the capture window
explicitly instead of "No concerns detected".

## Step 9 (Post-Implementation)

Current-branch profile — no worktree/branch cleanup. Run the gate orchestrator
(`risk_evaluated` is the materialized active gate), then archive via
`./.aitask-scripts/aitask_archive.sh 1187`.
