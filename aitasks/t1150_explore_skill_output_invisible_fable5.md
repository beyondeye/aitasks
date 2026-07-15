---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_explore, claudecode]
gates: [risk_evaluated]
created_at: 2026-07-15 10:36
updated_at: 2026-07-15 10:36
---

## Symptom

When running the `aitask-explore` skill in Claude Code with the **Fable 5** model (`claude-fable-5`), the user does not see the exploration-result summaries the skill emits — the exploration appears to produce no output on screen. The same skill with other Claude models, or with Codex, renders the summaries normally.

Observed live on 2026-07-15 during an explore session (this task was created from it): three consecutive attempts to present the exploration summary as assistant text were invisible to the user; only the `AskUserQuestion` prompts appeared.

## Hypotheses to investigate

1. **Text emitted in the same assistant turn as an `AskUserQuestion` tool call is not rendered** by the Claude Code client when the model is Fable 5 (turn-layout/rendering difference — Fable 5 may interleave text and tool_use blocks differently than other models, or the client collapses pre-tool text for it).
2. Fable 5 may place the summary in **visible-thinking blocks** rather than plain assistant text, which the client renders differently or hides.
3. A skill-structure interaction: `aitask-explore` Step 2 instructs "present a brief summary of findings, then AskUserQuestion" — models that fuse these into one turn may trigger the issue; models that emit them as separate messages do not.

## Investigation plan

- Reproduce minimally: a trivial prompt that emits a markdown paragraph followed by an `AskUserQuestion` call in the same turn, run under fable5 vs opus/sonnet, compare what the client displays.
- Check the session transcript (`~/.claude/projects/.../*.jsonl`) from the affected session to see whether the summary text was actually emitted as assistant text blocks (and in what order relative to tool_use) — this distinguishes model behavior from client rendering.
- Determine whether this is an upstream Claude Code client bug (if so: file/report upstream, label `upstream_defect_followup`) or something the skill can mitigate.

## Possible skill-side mitigation (if upstream fix is slow)

Harden the explore/fold/pick skill wording where a summary precedes an `AskUserQuestion`: require the summary to be presented and the question asked such that the text is reliably visible (e.g., instruct that findings summaries must be emitted as a standalone response before the question turn). Verify any wording change against `aidocs/framework/skill_authoring_conventions.md` and regenerate per-profile goldens if `.md.j2` sources change.

## Acceptance criteria

- Root cause identified (model turn-shape vs client rendering vs skill structure) with transcript evidence.
- Either an upstream report filed with a repro, or a skill-side mitigation landed (or both).
- Explore-skill summaries confirmed visible under fable5 in a live session.
