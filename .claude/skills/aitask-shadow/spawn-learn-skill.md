# Spawn a learner to learn a skill from the followed agent's workflow

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user asks
you — while shadowing — to **learn a skill** from what the followed agent just
did (e.g. "learn a skill from this", "capture this workflow as a skill", "turn
what this agent is doing into a reusable skill").

You do **not** run the learn yourself. The shadow is advisory/read-only and a
learn run would occupy it. Instead you **spawn a dedicated learner agent** —
`/aitask-learn-skill <followed_pane_id>` — in its own new tmux window. The learn
engine (a standalone skill) then captures the followed pane **read-only** and
walks the user through multi-part selection + generalization to author a static
`SKILL.md`. You stay free to keep advising.

**Advisory-only (load-bearing):** you spawn a learner in a NEW window; you NEVER
send keystrokes to the followed pane. The learner, too, only *reads* the followed
pane (via `aitask_shadow_capture.sh` inside the learn skill). Both sides are
read-only against the followed agent.

**Inputs:** the followed pane id (the shadow's `<followed_pane_id>` argument) and,
if known, the `<source_task_id>` (used only to label the learner's window). No
screen capture is needed here — the spawned learner does its own capture.

## Procedure

1. **Confirm with the user.** This action creates a new agent, so confirm before
   spawning. Use `AskUserQuestion`:
   - Question: "Spawn a learner agent to learn a skill from the followed agent's
     workflow? It opens in its own window and captures that pane read-only — you
     stay here with me."
   - Header: "Spawn learner"
   - Options:
     - "Yes, spawn the learner" (description: "Open a new window running
       /aitask-learn-skill pointed at the followed pane")
     - "No, not now" (description: "Don't spawn anything")
   - On "No", stop — spawn nothing.

2. **Spawn the learner.** On confirmation, run (pass the source task id only if
   you have it):

   ```bash
   ./.aitask-scripts/aitask_shadow_spawn_learner.py <followed_pane_id> [<source_task_id>]
   ```

   Parse the single structured output line:
   - `LEARNER_SPAWNED:<pane_id> WINDOW:<window>` — success. Tell the user the
     learner is now running in window `<window>` (visible in `ait monitor`); it
     will capture the followed pane and walk them through which part(s) to learn
     and how to generalize, then generate the skill. Remind them you remain
     available to keep advising, and that they close the learner's window when it
     finishes.
   - `SPAWN_FAILED:<reason>` — report the failure plainly (e.g. `no_session` = the
     followed pane could not be resolved to a tmux session; `resolve` = the learn
     command could not be resolved — check the code-agent model config). Do not
     retry blindly; surface the reason and let the user decide.

This capability is **on-request only** — never spawn a learner proactively, and
never drive the followed pane.
