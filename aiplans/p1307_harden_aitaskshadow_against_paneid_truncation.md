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
  grep -rnE '%[0-9]\b' "${targets[@]}"; rc=$?
  case $rc in
    1) echo "OK: no single-digit pane-id examples" ;;
    0) echo "FAIL: single-digit pane-id example remains" >&2; exit 1 ;;
    *) echo "FAIL: grep error (rc=$rc)" >&2; exit 1 ;;
  esac
)
# expect: "OK: ..." and status 0. Run it BEFORE the edits too — it must report
# 11 hits and status 1 today, which proves the check can actually fail.

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
  medium · → mitigation: TBD
- The structural elimination (capture helper falling back to its own
  `@aitask_shadow_target` binding when no id is passed, so the id never crosses
  the model's token stream) was considered and deliberately excluded by the
  confirmed scope — it needs a script change, which this task's AC forbids ·
  severity: medium · → mitigation: TBD

## Step 9 (Post-Implementation)

Current-branch mode: no worktree or branch cleanup. After the Step 8 review and
commit, Step 9 runs `./ait gates run 1307` (active gates: `risk_evaluated`) and
then `./.aitask-scripts/aitask_archive.sh 1307`.
