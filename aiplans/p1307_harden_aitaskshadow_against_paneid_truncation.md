---
Task: t1307_harden_aitaskshadow_against_paneid_truncation.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1307 — Harden `aitask-shadow` against pane-id truncation

## Context

On 2026-07-28 a shadow companion was launched by minimonitor for a codeagent on
`thinking_app` task `t57_5`. Everything on the framework side was correct — the
pane verbatim showed `› $aitask-shadow %237 57_5` and the lifecycle stamp read
`@aitask_shadow_target=%237` — but the shadow agent (Codex CLI, `gpt-5.6-terra`)
transcribed `%237` down to `%7` when composing its first tool call and ran
`aitask_shadow_capture.sh %7` → `can't find pane: %7`. It self-recovered by
listing panes and re-running against `%237`, so no harm resulted, but the
recovery was improvised, not specified. A truncated id that happens to collide
with a *live but wrong* pane would silently shadow the wrong agent — and the
shadow's whole value depends on it reading the right screen.

This is model-side argument mangling, not a wiring bug. A likely contributing
factor is that every pane-id example in the shadow/learn surfaces is a
**single digit** (`%5`), anchoring the model toward a short shape.

Intended outcome: (a) no single-digit pane-id example survives anywhere an agent
copies a pane id, (b) the "pass it verbatim" contract rides *inside* the command
block the agent copies, not in nearby prose, and (c) the recovery the model
improvised is codified — and made safer, by preferring the launcher's
`@aitask_shadow_target` binding over pane-list guessing.

Scope was confirmed with the user during planning: the shadow SKILL **plus** the
adjacent pane-id surfaces (the learn-skill the shadow spawns with that same id,
and the two helpers' `--help` text). Still documentation-only — comments, prose,
and usage strings; no logic path is touched.

## Edits

### A. `.claude/skills/aitask-shadow/SKILL.md` — the primary surface

1. **Arguments (line 26)** — replace the single-digit example and state the rule:

   ```markdown
   - `<followed_pane_id>` (required) — the tmux pane id (e.g. `%237`) of the agent
     you are shadowing. You capture this pane to see its current screen. **Use it
     exactly as given** — pane ids are commonly two or three digits, and dropping
     digits (`%237` → `%7`) can silently resolve to a *different live pane*.
   ```

2. **Step 1 capture block (line 67-69)** — move the contract *into* the fenced
   block, so it travels with the command the agent copies:

   ```bash
   # Pass <followed_pane_id> EXACTLY as you received it — copy every character.
   # Pane ids are often 2-3 digits (e.g. %237). Never abbreviate, reformat, or
   # re-derive it: a shortened id can match a DIFFERENT live pane and you would
   # silently shadow the wrong agent.
   ./.aitask-scripts/aitask_shadow_capture.sh <followed_pane_id>
   ```

3. **New recovery paragraph** immediately after that block (before the existing
   "For **plan analysis**…" paragraph):

   > **If the capture fails with `can't find pane: <id>`** — do not guess, and do
   > not retry a shortened or lengthened id. Re-resolve in this order:
   >
   > 1. Read your own pane's binding. The launcher stamps the followed pane id on
   >    the shadow's pane, so this is ground truth. Only run it when you actually
   >    have a pane — with `TMUX_PANE` unset, `-t ""` is an error, not an empty
   >    answer:
   >    ```bash
   >    [ -n "${TMUX_PANE:-}" ] && tmux show-options -pqv -t "$TMUX_PANE" @aitask_shadow_target
   >    ```
   >    Non-empty output **is** the pane to capture — use it verbatim. This is the
   >    only step that can *recover* a mangled id.
   > 2. If there is no binding (invoked manually, not running in a pane, or the
   >    stamp had not landed yet), list the live panes:
   >    ```bash
   >    tmux list-panes -a -F '#{pane_id} #{window_name} #{pane_current_command}'
   >    ```
   >    Accept **only an exact match** for the id you were given.
   > 3. **If nothing matches exactly, stop and ask the user which pane to shadow.**
   >    This is the deliberate safe fallback, not a gap in the procedure: once an
   >    id has been mangled (`%237` → `%7`) the pane list cannot invert it — a
   >    truncation is not a relation you can reverse, and every "closest match"
   >    heuristic is exactly the wrong-pane hazard this section exists to prevent.
   >    Never expand, contract, or fuzzy-match a pane id.
   >
   > Re-run the capture with the resolved id and tell the user you corrected it.

   Honest limit of the exact-match rule: it rejects *near* misses, but a mangled
   id that happens to name a live pane produces a successful capture of the wrong
   agent and never reaches this recovery at all. That is precisely why step 1
   (the binding) comes first and why the in-block verbatim contract in edit A.2
   — not the recovery — is the primary defense.

   Rationale for preferring the binding over `list-panes`: `@aitask_shadow_target`
   is the authoritative lifecycle binding written by the spawner
   (`minimonitor_app.py::_spawn_shadow`, `monitor_core.SHADOW_TARGET_OPTION`) and
   already read by `aitask_shadow_capture.sh::shadow_stamp_analyzed_at` — it
   resolves the *right* pane rather than the *plausible* one. It is step 1, not
   the only step, because the stamp lands just **after** launch, so a very early
   capture can race it.

   Raw `tmux` in agent-executed skill prose is fine here: `tests/test_no_raw_tmux.sh`
   scans `.aitask-scripts/` (framework code), and `task-workflow/auto-verification.md`
   already instructs agents to call `tmux capture-pane` / `send-keys` directly.

### B. `.claude/skills/aitask-shadow/spawn-learn-skill.md` — the second handoff

The shadow passes the same id on to the learner. Add the same in-block comment
to the Step 2 spawn command, and a verbatim clause to the **Inputs** paragraph:

```bash
# Pass <followed_pane_id> EXACTLY as received — never abbreviate or re-derive it.
./.aitask-scripts/aitask_shadow_spawn_learner.py <followed_pane_id> [<source_task_id>]
```

### C. `aitask-learn-skill` — kill the `%5` anchor at the receiving end

Mechanical `%5` → `%237` in the pane-id examples, plus the same in-block verbatim
comment on the Step 2A capture command:

- `.claude/skills/aitask-learn-skill/SKILL.md` — lines 21, 29, 37 (`%5` → `%237`);
  Step 2A block (line 61) gains the verbatim comment.
- `.claude/skills/aitask-learn-skill/generate.md` — line 13 (`pane %5` → `pane %237`).
- `.agents/skills/aitask-learn-skill/SKILL.md` — line 22.
- `.opencode/skills/aitask-learn-skill/SKILL.md` — line 18.

The two wrappers are hand-maintained and carry the example inline, so they are
edited in the same commit. **No cross-agent port task is warranted**: the change
is a verbatim one-token example with no agent-specific semantics, and the shadow
wrappers (`.agents/`, `.opencode/`) are pure redirects to the Claude SKILL —
they contain no pane-id example to fix.

### D. Helper `--help` / header text (comments and usage strings only)

- `.aitask-scripts/aitask_shadow_capture.sh` — lines 15 and 72 (`e.g. %5` → `e.g. %237`).
- `.aitask-scripts/aitask_shadow_spawn_learner.py` — line 25 (`%5`) and line 65
  (argparse help, `%%5` → `%%237`; the doubled `%` is required by argparse).

No executable statement changes in either file.

### E. Test-fixture strengthening (1 line, optional but free)

`tests/test_shadow_spawn_learner.sh:37,40` drives the dry-run with `%5` and
asserts the id is passed through. Switching the fixture to `%237` makes that
pass-through assertion cover a multi-digit id, so a future truncation *in the
script* would fail the suite. (It cannot guard the model-side defect — nothing
can — but the fixture may as well be realistic.)

## Verification

```bash
# 1. NO single-digit pane-id example survives on any declared surface.
#    Searches %[0-9]\b (not just %5) so an overlooked %1/%7 cannot pass, and
#    fails loudly on a missing target instead of silently grepping nothing.
#    Verified to discriminate: matches %7; ignores %237, the literal regex
#    ^%[0-9]+$, and argparse's doubled %%237.
#    Branches on grep's exit code explicitly: 0 = match (FAIL), 1 = clean,
#    anything else = grep error (FAIL). Verified: grep here is ugrep, which
#    exits 2 with only a *warning* on a bad path — so `grep … && FAIL || OK`
#    would print OK for a typo'd target. Wrapped in a subshell so the `exit`s
#    are safe to paste into an interactive shell.
(
  set -u
  targets=(
    .claude/skills/aitask-shadow
    .claude/skills/aitask-learn-skill
    .agents/skills/aitask-learn-skill
    .opencode/skills/aitask-learn-skill
    .aitask-scripts/aitask_shadow_capture.sh
    .aitask-scripts/aitask_shadow_spawn_learner.py   # .py, NOT .sh — no such .sh exists
  )
  for t in "${targets[@]}"; do
    [ -e "$t" ] || { echo "MISSING VERIFICATION TARGET: $t" >&2; exit 1; }
  done
  raw=$(grep -rnE '%[0-9]\b' "${targets[@]}"); rc=$?
  case $rc in
    0|1) ;;
    *) echo "FAIL: grep error (rc=$rc)" >&2; exit 1 ;;
  esac
  # AMENDED AT IMPLEMENTATION TIME (Change Requests 1 and 2 below). The new docs
  # deliberately spell out the anti-example `%237` → `%7`, so an unqualified
  # `%[0-9]\b` scan flags the very text this task exists to add. The exception is
  # TOKEN-level, not line-level: strip only the exact documented anti-example
  # token, then re-scan the remainder. A line-level `grep -v '%237'` was tried
  # first and rejected — it silently passes a mixed line such as
  # `Example: %237 is valid; %9 is also shown` (reproduced; negative control C).
  bad=$(printf '%s' "$raw" | sed 's/`%237` → `%7`//g' | grep -E '%[0-9]\b' || true)
  if [ -n "$bad" ]; then
    printf '%s\n' "$bad"
    echo "FAIL: single-digit pane-id anchor remains" >&2
    exit 1
  fi
  echo "OK: no single-digit pane-id anchors (documented anti-example token excluded)"
)
# expect: "OK: ..." and status 0. Run it BEFORE the edits too — it must report
# 11 hits and status 1 today, which proves the check can actually fail. THREE
# negative controls are required, each restored by undoing ONLY the mutation
# (never `git checkout`, which would wipe the task's uncommitted edits):
#   A. append a bare `%9` example to a target file      → must exit 1
#   B. point one target at a non-existent path          → must exit 1 before grep
#   C. append `Example: %237 is valid; %9 is also shown` → must exit 1
#      (C is the case the rejected line-level exception passed.)

# 2. Behavior of the touched helpers is unchanged.
bash tests/test_shadow_capture.sh
bash tests/test_shadow_spawn_learner.sh
bash tests/test_shadow_context.sh
shellcheck .aitask-scripts/aitask_shadow_capture.sh

# 3. The new raw-tmux prose lives in a skill, not framework code — prove the
#    centralization guard still passes.
bash tests/test_no_raw_tmux.sh

# 4. Skill surfaces still verify (no stub/j2 surface was touched, but confirm).
./.aitask-scripts/aitask_skill_verify.sh

# 5. Eyeball the rendered contract: the verbatim rule must be INSIDE the fenced
#    block, not only in surrounding prose.
sed -n '20,40p;60,100p' .claude/skills/aitask-shadow/SKILL.md
```

## Risk

### Code-health risk: low
- The recovery instructs the shadow agent to call `tmux` directly, which sits
  outside the `lib/tmux_exec.sh` gateway convention. Bounded: the gateway rule
  (`aidocs/framework/tmux_gateway.md`, enforced by `tests/test_no_raw_tmux.sh`)
  governs framework code under `.aitask-scripts/`, not agent-executed skill
  prose, and `task-workflow/auto-verification.md` sets the precedent ·
  severity: low · → mitigation: TBD
- Two script files are touched (`aitask_shadow_capture.sh`,
  `aitask_shadow_spawn_learner.py`) even though the change is comment/usage text
  only, so the diff looks wider than the behavior change · severity: low ·
  → mitigation: TBD

### Goal-achievement risk: medium
- The fix steers a model with prose and a better-anchored example. It reduces the
  probability of a mis-copy but cannot eliminate it — the defect is model-side
  transcription, and the recovery only fires *after* a capture already failed. A
  truncated id that collides with a live pane succeeds, so it never reaches the
  recovery at all; nothing in a doc-only change guards that case · severity:
  medium · → mitigation: **t1319** (wrong-pane collision warning)
- The structural elimination (capture helper falling back to its own
  `@aitask_shadow_target` binding when no id is passed, so the id never crosses
  the model's token stream) was considered and deliberately excluded by the
  confirmed scope — it needs a script change, which this task's AC forbids ·
  severity: medium · → mitigation: **t1319** (binding-based self-resolution)

**Deferred-risk tracking (added at review):** both goal-achievement risks were
accepted at planning time with no mitigation task, which left the residual
wrong-pane hazard untracked and free to recur. They are now carried by
**t1319 — shadow pane id structural binding resolution**, which specifies both
candidate mitigations, the stamp-race constraint on the no-argument path, and
the four-case test matrix.

## Post-Review Changes

### Change Request 1 (2026-07-29 00:05)

- **Requested by user:** Two CONFIRMED review concerns, both dispositioned
  *follow-up*: (1) `tests/test_shadow_spawn_learner.sh:67` still asserts the
  pre-t1241 default `claudecode/opus4_8`, so the test this task edits cannot
  give a clean regression signal (17/18); (2) the documented recovery cannot
  detect a mangled pane id that resolves to a live *wrong* pane, and no task
  recorded that deferred structural work.
- **Changes made:** No source edits. Created two follow-up tasks and wired the
  plan to them:
  - **t1318** — fix the stale `defaults.learn` assertion (and its stale comment
    on line 36), decide deliberately whether to pin a literal or read the
    configured default, and sweep the test tree for the same t1241/t1242
    staleness elsewhere.
  - **t1319** — close the residual wrong-pane hazard via binding-based
    self-resolution and/or a wrong-pane collision warning in
    `aitask_shadow_capture.sh`; records the `_spawn_shadow` stamp race that
    forces the explicit-argument path to remain the fallback.
  - The `## Risk` goal-achievement bullets now name t1319 instead of `TBD`, with
    a note on why the risks were left untracked.
  - The verification block was amended (documented inline at the check) to
    exempt lines carrying the correct multi-digit id: the unamended check
    flagged the two deliberate `%237 → %7` anti-example lines, i.e. the very
    text this task adds.
- **Files affected:** `aiplans/p1307_*.md` only; plus the two new task files
  `aitasks/t1318_*.md`, `aitasks/t1319_*.md` (committed by `aitask_create.sh`).

### Change Request 2 (2026-07-29 00:20)

- **Requested by user:** CONFIRMED — the Change-Request-1 anchor check excluded
  every *line* containing `%237`, not only the intended `%237` → `%7`
  anti-examples, so a mixed line like `Example: %237 is valid; %9 is also shown`
  falsely passed (the user reproduced it). Narrow the exception to the documented
  anti-example pattern and add the mixed-line case as a negative control.
- **Changes made:** Reproduced the false negative, then replaced the line-level
  exclusion with a **token-level** one: strip the exact `` `%237` → `%7` ``
  token, then re-scan the remainder for `%[0-9]\b`. Re-ran all three negative
  controls against the narrowed check — A (bare `%9`), B (missing target), and
  the new C (mixed line) all exit 1; the restored tree exits 0. Documented the
  rejected line-level variant inline at the check so it is not re-attempted.
- **Disposition note (deliberate deviation):** the concern was dispositioned
  *follow-up*, but the defect lives in **this plan's own verification command** —
  a task to fix a grep inside an archived plan would carry no value once the plan
  is written correctly, and shipping a knowingly-weak check would be worse. It is
  fixed and re-verified in-task instead. No follow-up task was created.
- **Files affected:** `aiplans/p1307_*.md` only. No source files changed; the
  nine implementation paths are byte-identical to the Change-Request-1 state.

## Final Implementation Notes

- **Actual work done:** All five planned edit groups landed, across nine files.
  (A) `.claude/skills/aitask-shadow/SKILL.md` — `%5` → `%237` plus an explicit
  "use it exactly as given" clause in **Arguments**; the verbatim contract moved
  *inside* the Step-1 capture fence as shell comments so it travels with the
  copied command; a new three-step recovery (own-pane `@aitask_shadow_target`
  binding → exact-match pane list → ask the user) with an honest note on what
  the exact-match rule cannot catch. (B) `spawn-learn-skill.md` — verbatim clause
  in **Inputs** + in-block comment on the spawn command. (C) `aitask-learn-skill`
  — four `%5` → `%237` in the Claude tree (`SKILL.md` ×3, `generate.md` ×1), one
  each in the `.agents/` and `.opencode/` wrappers, plus a verbatim comment in
  the Step 2A capture fence. (D) `aitask_shadow_capture.sh` and
  `aitask_shadow_spawn_learner.py` — header/usage text only. (E)
  `tests/test_shadow_spawn_learner.sh` — every pane-id fixture made multi-digit
  (`%237`/`%314`/`%142`), so the pass-through assertions can now detect
  digit-dropping; a single-digit fixture could not.

- **Deviations from plan:** Two, both in the *verification command*, neither in
  the shipped edits. (1) The plan's `%[0-9]\b` scan flagged the two deliberate
  `%237` → `%7` anti-example lines — the very text this task adds — so an
  exception was added. (2) The first exception was line-level (`grep -v '%237'`)
  and was rejected: it silently passed a mixed line carrying both the
  anti-example and a bare short id. The shipped check strips the exact
  `` `%237` → `%7` `` **token** and re-scans the remainder. See Change Requests
  1 and 2. One further deviation of process: CR2 was dispositioned *follow-up*
  but fixed in-task, because the defect was in this plan's own check.

- **Issues encountered:** `tests/test_shadow_spawn_learner.sh` fails 17/18 on a
  clean tree for a reason predating this task (see Upstream defects). Confirmed
  unrelated: the failing assertion (line 67) was never touched here — only the
  pane-id fixture on the same command was. Ordering was also adjusted in the
  shadow SKILL: the recovery block initially sat between the capture fence and
  "This is your primary input", which read as a non-sequitur; the failure-path
  text now follows the primary-input paragraph while the in-fence comments —
  the actual primary defense — stay adjacent to the command.

- **Key decisions:** (1) The verbatim contract lives *inside* the fenced command,
  not in surrounding prose, because agents copy the command and not the prose.
  (2) The recovery prefers the launcher's `@aitask_shadow_target` binding over a
  `tmux list-panes` search: the binding resolves the *right* pane, a pane list
  only the *plausible* one. It is step 1 rather than the only step because
  `minimonitor_app.py::_spawn_shadow` stamps the option just **after** launch, so
  a very early capture can race it. (3) Never fuzzy-match a pane id — asking the
  user is the deliberate terminal fallback, since a truncation cannot be
  inverted. (4) Raw `tmux` in agent-executed skill prose is acceptable:
  `tests/test_no_raw_tmux.sh` governs framework code under `.aitask-scripts/`
  (verified still passing, 5/5), and `task-workflow/auto-verification.md` sets
  the precedent. (5) Scope was widened past the task's literal edit surface to
  the `aitask-learn-skill` tree, confirmed with the user before implementing:
  the shadow hands that skill the *same* pane id, so leaving the `%5` anchor
  there would have defeated the change at the receiving end.

- **Upstream defects identified:**
  `tests/test_shadow_spawn_learner.sh:67 — asserts AGENT_STRING:claudecode/opus4_8 but codeagent_config.json defaults.learn is now claudecode/opus5 (promoted by t1241), so the suite fails 17/18 on a clean tree; the stale comment on line 36 repeats the same value` — tracked as **t1318**.

- **Deferred structural work:** the residual wrong-pane hazard (a mangled id that
  happens to name a live pane captures the wrong agent with no error, so the
  recovery never fires) is tracked as **t1319**, covering binding-based
  self-resolution and/or a wrong-pane collision warning in the capture helper.

## Step 9 (Post-Implementation)

Current-branch mode: no worktree or branch cleanup. After the Step 8 review and
commit, Step 9 runs `./ait gates run 1307` (active gates: `risk_evaluated`) and
then `./.aitask-scripts/aitask_archive.sh 1307`.
