---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini, codex, opencode]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-13 14:34
updated_at: 2026-08-14 13:11
---

Extend the auto-recheck loop's shadow-readiness detection beyond Claude so the loop can arm when the SHADOW pane runs Codex or OpenCode. Today `SHADOW_READY_DETECTORS` (`.aitask-scripts/monitor/review_loop.py:382`) is `{"claude": _claude_ready}`, and `action_toggle_review_loop` (`minimonitor_app.py`) refuses to arm when the resolved shadow agent key is not in it.

## Why this matters — the shipped loop refuses the project's own preferred pairing

t1159_2 shipped the loop with claude-only readiness. The pairing that the framework actually uses and that its live positive control verified is a **Codex shadow of a Claude followed pane** — archived t1498 recorded a PASS with "Codex gpt-5.6-terra shadow of a Claude Code (opus5) followed pane -- the preferred reproduction pairing", and t1493's coordination note recorded the same configuration from a live session. So the manual recheck path is live-proven in exactly the configuration in which the AUTOMATIC loop cannot arm at all.

Net effect today: the loop works only Claude-followed + Claude-shadow. This task closes the shadow half.

## Scope

- Add a per-agent readiness detector for `codex` (and `opencode` if its surfaces are observable) to `SHADOW_READY_DETECTORS`, honoring the existing three-part contract in `shadow_prompt_ready` (`review_loop.py:387`): (a) POSITIVE — the tail shows that agent's **empty** input composer; (b) NEGATIVE — no dialog/prompt pattern for that agent matches the tail; (c) `hash_stable`. Anything indeterminate must stay not-ready (`False`/`None`), never `True`. Hash stability alone is never sufficient.
- Patterns are version-sensitive LLM-UI text: pin them from **live captures** taken through the monitor's own capture path (`capture-pane -p -e` + `strip_ansi`), as inline string literals in `tests/test_review_loop.py` — the practice established by t1420/t1474 and followed by t1159_2's shadow-readiness fixtures. Capture at least: shadow at rest (empty composer), streaming output, parked at a dialog, and holding typed-but-unsubmitted composer text.
- Keep the arm-time refusal working and its message accurate for any agent still lacking a detector (t1159_2 test-pinned that the refusal names the shadow's agent).

## Decide explicitly: is the negative half safe for a non-Claude shadow?

`shadow_prompt_ready`'s negative half consults `prompt_patterns.PROMPT_PATTERNS_BY_AGENT[agent]`. Measured on the current tree: `claude` has 5 patterns, **`codex` has 1 (an explicit placeholder)**, `opencode` has 0. A weak negative half is a SAFETY question, not a cosmetic one: the loop delivers a prompt plus Enter, so injecting into a shadow parked at a dialog would ANSWER that dialog.

Resolve this at planning time rather than assuming:
- Determine empirically whether a Codex pane parked at a dialog can ever satisfy the POSITIVE empty-composer half. If a dialog always replaces/obscures the composer, the positive half already excludes it and the thin pattern list is tolerable — document that reasoning with the capture that supports it.
- If it can, this task needs richer codex dialog patterns before it is safe to ship, and should then take a `depends:` on t1467 (which owns per-agent prompt-pattern coverage) or add the needed patterns itself in coordination with it.

**Deliberately NOT declared `depends: [1467]` at creation.** t1467 extends detection for the **followed** agent (workflow-phase / native prompt classification); this task is the **shadow** side. A Codex-shadow-of-Claude-pane setup — the one that is blocked today — needs only this task, so a blocking edge would defer the fix that most directly unblocks the feature. Add the edge only if the safety question above resolves the other way.

## Key files

- `.aitask-scripts/monitor/review_loop.py` — `SHADOW_READY_DETECTORS` (:382), `shadow_prompt_ready` (:387), the `_claude_ready` detector as the shape to mirror.
- `.aitask-scripts/monitor/minimonitor_app.py` — `action_toggle_review_loop` arm refusals (the shadow-agent branch); no signature change expected.
- `.aitask-scripts/monitor/prompt_patterns.py` — only if the negative-half decision requires codex dialog patterns here.
- `tests/test_review_loop.py` — readiness fixtures and cases.

## Verification

- Per new agent: at-rest capture → ready True; streaming / at-dialog / typed-text / failed capture / hash-unstable → NOT True. Unknown agent still → not ready.
- The arm refusal still fires (and names the agent) for an agent with no detector — do not let the refusal become unreachable.
- Live: arm the loop in a real minimonitor with the new shadow agent and observe one automatic recheck fire, and confirm nothing is injected while that shadow is mid-output or at a dialog.
- `bash tests/run_all_python_tests.sh` — final stderr verdict line only.

## Coordination

- **t1467** (cross-agent phase prompt detection, `depends: [1420]`) — owns the FOLLOWED side and the per-agent prompt-pattern inventory. See the negative-half question above; the two tasks touch adjacent surfaces and t1467's pattern work is what would harden this task's dialog exclusion.
- **t1159_5** (aggregate manual verification of the review loop) — its checklist assumes a loop that can arm; if this task lands first, verify with the Codex-shadow pairing rather than substituting a Claude shadow.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-14T10:11:37Z status=pass attempt=1 type=human
