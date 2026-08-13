---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [shadow, robustness]
gates: [risk_evaluated]
anchor: 1307
followup_kind: risk_mitigation
created_at: 2026-08-04 13:36
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t1319, created at Step 8d after
implementation landed.

## Risk addressed

From t1319's plan `## Risk` → goal-achievement:

> Argument-free markdown may still be ignored by a model that transcribes the id
> anyway — and the **learner-spawn path** (`spawn-learn-skill.md` →
> `aitask_shadow_spawn_learner.py`) has no argument-free form at all, so it keeps
> the full mangle hazard · severity: low

t1319 closed the wrong-pane hazard on the **capture** path only: the shadow's
Step 1 and every `--deep` sub-procedure now run argument-free, resolving the
followed pane from the shadow's own `@aitask_shadow_target` binding, and an
explicit id that contradicts (or cannot be verified against) that binding is
refused with exit 2. t1319's scope notes named `aitask_shadow_capture.sh` only,
so the learner-spawn path was deliberately left out.

## Goal

Close the same hazard on the learner-spawn path.

Today `spawn-learn-skill.md` Step 2 tells the shadow to run:

```bash
./.aitask-scripts/aitask_shadow_spawn_learner.py <followed_pane_id> [<source_task_id>]
```

That id is transcribed by the model, so it carries exactly the truncation risk
t1319 removed elsewhere (`%237` → `%7`). A mangled id that happens to name a
live pane points the spawned learner at the wrong agent's screen, and the
learner then authors a skill from it — with no error anywhere.

Required:

1. Teach `.aitask-scripts/aitask_shadow_spawn_learner.py` to resolve the followed
   pane from its own pane's `@aitask_shadow_target` binding when invoked with no
   pane argument. **Reuse t1319's semantics rather than reinventing them** — see
   `shadow_self_target()` in `.aitask-scripts/aitask_shadow_capture.sh`, which
   returns the four-state classification (`""` / `unbound` / `bound:<id>` /
   `cross-server`) from a single `display-message` fetching `#{socket_path}` and
   the option together. The socket comparison against `$TMUX` is load-bearing:
   pane ids collide across tmux servers, so an unvalidated lookup can resolve a
   foreign server's binding. Consider whether the shared logic belongs in
   `lib/tmux_exec.py` (the spawner is Python; the capture helper is bash) rather
   than being duplicated — a cross-language shim is the established pattern.
2. Keep the explicit-argument path supported, and fail closed (clear error, never
   a guess) when there is no verifiable binding.
3. Make `spawn-learn-skill.md` Step 2 argument-free, mirroring the wording t1319
   used in `.claude/skills/aitask-shadow/SKILL.md.j2` Step 1 — including the
   split recovery ladder: a *conflicting* binding means "drop the argument", a
   *cross-server* caller means "confirm the pane with the user, then re-run with
   the override". Do not collapse those two into one instruction; t1319 shipped
   that bug in review and it livelocks the agent.
4. Decide whether the spawner should also refuse a conflicting explicit id (the
   t1319 mitigation-2 analogue) or only self-resolve. Note the asymmetry: the
   spawner *creates an agent* rather than reading a pane, so a wrong target is
   more expensive to undo, which argues for refusing.

## Verification

```bash
bash tests/test_no_raw_tmux.sh
```

Plus tests for: no-arg with a binding present, no-arg with the option unset,
explicit id matching the binding, explicit id conflicting with the binding, and
a cross-server caller. Prove each guard can fail (t1319's
`tests/test_shadow_capture.sh` binding-resolution section is the model — it uses
two throwaway tmux servers with **colliding pane ids**, which is what makes the
cross-server negative control discriminate).

Read `aidocs/framework/shadow_agent.md` ("Rule: the validated pane binding, not
the argument, is the source of truth") before changing resolution semantics.
