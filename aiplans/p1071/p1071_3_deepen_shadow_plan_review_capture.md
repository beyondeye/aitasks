---
Task: t1071_3_deepen_shadow_plan_review_capture.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Sibling Tasks: aitasks/t1071/t1071_4_*.md, aitasks/t1071/t1071_5_*.md, aitasks/t1071/t1071_6_*.md, aitasks/t1071/t1071_7_*.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_*_*.md
Worktree: (none — profile 'fast', working on current branch)
Branch: main
Base branch: main
---

# Plan — Deepen shadow plan-review capture depth (t1071_3)

## Context

The shadow agent (`aitask-shadow`) reads a *followed* agent's tmux pane via
`.aitask-scripts/aitask_shadow_capture.sh`, which captures `SHADOW_CAPTURE_LINES`
(default **200**) scrollback lines plus the visible pane. 200 lines is fine for
short prompts and error screens, but the four **plan-review** sub-procedures
(`plan-explain`, `plan-challenge`, `plan-socratic`, `plan-assumptions`) analyze a
*plan*. When the plan is only on screen (e.g. awaiting approval, not yet
externalized to a file), a long plan can be truncated to its tail — so the
analysis misses earlier constraints, decisions, risk notes, or verification
requirements.

Goal: plan-review flows refetch the followed pane with a **deeper** capture
(400 lines) by default, while ordinary shadow reads (explain-output,
help-answer-prompt, diagnose-errors) stay at the cheap 200-line default.

## Approach (single source of truth, no markdown magic-number duplication)

Rather than inline `SHADOW_CAPTURE_LINES=400 …` into four+ markdown files (a
copy-pasted magic number that drifts), add an **opt-in `--deep` flag** to
`aitask_shadow_capture.sh`. The flag selects a script-defined deep depth
(`SHADOW_PLAN_CAPTURE_LINES`, default **400**, env-overridable to mirror the
existing `SHADOW_CAPTURE_LINES` pattern). The plan-review sub-procedures then call
`aitask_shadow_capture.sh --deep <pane>` — the value `400` lives in exactly one
place (the script), the markdown carries only intent (`--deep`).

The **global default stays 200** — no global default change (per the task's
guidance). `--deep` is purely additive and backward-compatible: every existing
caller without the flag is unaffected.

## Files

| File | Change |
|------|--------|
| `.aitask-scripts/aitask_shadow_capture.sh` | Add `SHADOW_PLAN_CAPTURE_LINES` (default 400); add `--deep` flag; thread the resolved depth into `shadow_capture_pane`; document the why in header + `--help`. |
| `.claude/skills/aitask-shadow/plan-explain.md` | Update **Inputs** line: refetch with `--deep` when reading the plan from the pane. |
| `.claude/skills/aitask-shadow/plan-challenge.md` | Same Inputs update. |
| `.claude/skills/aitask-shadow/plan-socratic.md` | Same Inputs update. |
| `.claude/skills/aitask-shadow/plan-assumptions.md` | Same Inputs update. |
| `.claude/skills/aitask-shadow/SKILL.md` | Step 1: one concise note that plan-analysis sub-procedures capture deeper via `--deep` (discoverability; single canonical pointer). |
| `aidocs/framework/shadow_agent.md` | Capture bullet (#1): one sentence — plan-review sub-procedures capture deeper (400) via `--deep`, and *why*. |
| `tests/test_shadow_capture.sh` | Add a live-tmux behavioral test proving `--deep` captures past the 200-line window (skip-guarded when tmux absent, matching the existing `-J` test). |

**Out of scope (explicit, no silent AC deviation):** `plan-diagnose-errors.md`
stays at the default 200 — it scans for error/retry signals on the *visible*
screen, not a long plan. The task AC names plan-review procedures only.

## Step-by-step

### 1. `aitask_shadow_capture.sh` — add the `--deep` opt-in

Near the existing default:
```bash
SHADOW_CAPTURE_LINES="${SHADOW_CAPTURE_LINES:-200}"
# Deeper capture for plan-review flows (plan-explain/-challenge/-socratic/
# -assumptions): plans are long and the 200-line default can truncate earlier
# constraints/decisions/risk notes. Opt in with --deep. Env-overridable.
SHADOW_PLAN_CAPTURE_LINES="${SHADOW_PLAN_CAPTURE_LINES:-400}"
```

Make `shadow_capture_pane` take the depth explicitly (defaulting to the normal
global, so the signature stays backward-compatible):
```bash
shadow_capture_pane() {
    local pane="$1"
    local lines="${2:-$SHADOW_CAPTURE_LINES}"
    ait_tmux capture-pane -p -J -t "$pane" -S "-${lines}"
}
```

In `main`, add a `deep` flag and resolve the effective depth:
```bash
local pane="" deep=0
...
    -)         pane="-"; shift ;;
    --deep)    deep=1; shift ;;
    -*)        die "Unknown option: $1" ;;
...
local capture_lines="$SHADOW_CAPTURE_LINES"
[[ "$deep" -eq 1 ]] && capture_lines="$SHADOW_PLAN_CAPTURE_LINES"
...
    shadow_capture_pane "$pane" "$capture_lines"
```
(`--deep` is a no-op on the `-` stdin path — there is no scrollback to deepen.)

Update the header comment block and `show_help()` to document `--deep` and the
rationale (plan-review deeper capture; default 400; ordinary reads stay 200).
**Also note in `show_help()` that `--deep` has no effect with `-` (stdin has no
scrollback to deepen)** — so the CLI contract is explicit and not silently
misleading.

### 2. Plan-review sub-procedures — use `--deep`

In each of `plan-explain.md`, `plan-challenge.md`, `plan-socratic.md`,
`plan-assumptions.md`, augment the existing **Inputs** paragraph (which already
says "fetch the full plan first if only a fragment is on screen") with a deeper-
capture instruction, e.g.:

> When you (re)capture the followed pane to read the plan, use the deeper
> plan-review capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep <followed_pane_id>`
> — because plans are long and the default 200-line window can truncate earlier
> constraints, decisions, or risk notes.

### 3. `SKILL.md` Step 1 — one canonical pointer

Add a single concise note in Step 1 (the capture step) that the plan-analysis
sub-procedures refetch with `--deep` for a deeper window. Keep it short — the
value/rationale live in the script and `shadow_agent.md`; this is just
discoverability so the convention isn't buried only in the sub-procedures.

### 4. `aidocs/framework/shadow_agent.md` — document the why

Extend the capture bullet (Pipeline #1) with one sentence: plan-review
sub-procedures capture deeper via `--deep` because plans can exceed the 200-line
default; ordinary shadow reads stay at 200 to stay cheap. Phrase the depth as
**"the script's `SHADOW_PLAN_CAPTURE_LINES` (default 400)"** — this is an
intentional, *sourced* mention (it names the script knob), so the doc satisfies
the AC's "make clear why plan review uses a deeper capture" without becoming a
second free-floating definition of the number.

### 5. `tests/test_shadow_capture.sh` — behavioral proof (height-controlled, non-flaky)

`capture-pane -S -N` returns N scrollback lines **plus the visible pane**, so
sentinel inclusion depends on pane height and on rendering having completed.
Make the test deterministic:

- **Fix the geometry.** Start the isolated-socket pane with an explicit height
  (`-y 10`, matching the existing `-J` test); call it `VIS=10`.
- **Size filler relative to both windows.** The default window reaches back
  `200 + VIS` logical lines from the bottom; the deep window reaches `400 + VIS`.
  Emit a unique first-line sentinel (`SHADOW_DEEP_SENTINEL`), then enough filler
  so the **total** line count `T` satisfies `200 + VIS < T < 400 + VIS`
  comfortably — use `T = 320` (sentinel + `seq 2 319` + a final marker
  `SHADOW_DEEP_LASTLINE`). At `T=320, VIS=10`: the sentinel sits ~110 lines above
  the default window's top (safely excluded) and ~100 lines inside the deep
  window (safely included) — wide margins on both sides.
- **Pin both depth env vars on every capture invocation.** The 200/400 line
  math is only guaranteed if the test fixes the depths — `SHADOW_CAPTURE_LINES`
  and `SHADOW_PLAN_CAPTURE_LINES` are both env-overridable, so an ambient value in
  a dev/CI shell would otherwise break the negative-control or the `--deep`
  capture for reasons unrelated to the implementation. Set them explicitly
  (alongside the existing `AITASKS_TMUX_SOCKET`) on each call:
  - Default capture: `SHADOW_CAPTURE_LINES=200 AITASKS_TMUX_SOCKET="$JSOCK" "$CAPTURE" "$jpane"`
  - Deep capture (and the render-poll): `SHADOW_CAPTURE_LINES=200 SHADOW_PLAN_CAPTURE_LINES=400 AITASKS_TMUX_SOCKET="$JSOCK" "$CAPTURE" --deep "$jpane"`
- **Poll until rendered, then assert.** Poll the pinned `--deep` capture until it
  contains `SHADOW_DEEP_LASTLINE` (proves the pane finished printing) before
  asserting:
  - Default (no flag, pinned 200): `assert_not_contains` `SHADOW_DEEP_SENTINEL` —
    it fell outside the 200-line window (negative control).
  - `--deep` (pinned 200/400): `assert_contains` `SHADOW_DEEP_SENTINEL` — the
    deeper window reached it.
  - Sanity: both captures contain `SHADOW_DEEP_LASTLINE`.
- **Skip-guard** exactly like the existing `-J` test (skip when tmux is
  unavailable or the test pane can't start).

This directly demonstrates the AC "the plan-review path can capture more than the
old 200-line scrollback window," with the default capture as its negative
control.

## Verification

- `shellcheck .aitask-scripts/aitask_shadow_capture.sh` — clean.
- `bash tests/test_shadow_capture.sh` — all existing tests still pass (arg
  validation: `--bogus` rejected, extra-arg `%1 %2` rejected, `--help` shows
  usage) **and** the new `--deep` behavioral test passes (or SKIPs cleanly where
  tmux is unavailable).
- `./.aitask-scripts/aitask_skill_verify.sh` — OK (static shadow skill; confirms
  no surface breakage from the SKILL.md / sub-procedure edits).
- **Single-source-of-truth grep (scoped, no contradiction):** the *operative*
  markdown — the four plan-review sub-procedures **and** `SKILL.md` — must contain
  **no bare `400` capture literal** (they reference `--deep`, not the number).
  `aidocs/framework/shadow_agent.md` and the script are **allowed** to mention
  `400` (intentional, sourced documentation — see Step 4). So the check is scoped
  to the operative files, not a repo-wide ban:
  ```bash
  ! grep -nE '\b400\b' .claude/skills/aitask-shadow/plan-{explain,challenge,socratic,assumptions}.md \
                       .claude/skills/aitask-shadow/SKILL.md
  ```
- **`--deep` coupling guard (hidden-coupling check):** each of the four
  plan-review sub-procedures must actually carry the `--deep` recapture
  instruction — so a future edit that drops it (silently regressing that flow to
  shallow capture) is caught:
  ```bash
  for f in plan-explain plan-challenge plan-socratic plan-assumptions; do
    grep -q -- '--deep' ".claude/skills/aitask-shadow/$f.md" || echo "MISSING --deep: $f"
  done
  ```
  Expect no `MISSING` output.

## Cross-agent / goldens

Shadow is a **static, Claude-only** skill (no `.j2`/closure/profile machinery);
its `plan-*.md` sub-procedures live only in the Claude tree (Codex/OpenCode are
thin wrappers). No goldens regeneration and **no cross-agent port** are needed.

## Risk

### Code-health risk: low
- The script change is additive and backward-compatible (`--deep` opt-in; the
  global 200 default and existing `shadow_capture_pane` call site are unchanged
  via the defaulted 2nd arg). Blast radius is one helper + its callers (markdown)
  + one test. · severity: low · → mitigation: none needed (covered by shellcheck
  + the existing/new unit tests).

### Goal-achievement risk: low
- The deep-capture path is exercised by a real live-tmux behavioral test that
  proves capture beyond the 200-line window, and the markdown carries the
  `--deep` intent with the value single-sourced in the script. · severity: low ·
  → mitigation: none needed.

## Post-implementation

Follow shared workflow **Step 9 (Post-Implementation)**: this is risk-gated
(`risk_evaluated`) under profile 'fast' — gate recording fires; archival via
`aitask_archive.sh 1071_3` (archives the parent too once it is the last child).
