---
priority: low
effort: medium
depends: [966]
issue_type: chore
status: Ready
labels: [codeagent, research]
created_at: 2026-06-10 17:21
updated_at: 2026-06-10 17:21
boardidx: 360
---

Investigate why a `claudecode/fable5` session (e.g. launched by `/aitask-pick` as `claude --model claude-fable-5`) starts on the **Fable 5** promo but ends up with **Opus 4.8** selected — and whether anything in this repo can be changed to keep it on Fable 5 from launch.

Depends on t966 (which registered `claudecode/fable5` → `claude-fable-5`). The model ID is confirmed correct; this task is purely about the launch-time model behavior, not the registry entry.

## Background / what's known
- Per the Claude help center, Fable 5 runs content-safety classifiers (cybersecurity / biology). When a request is flagged, Claude Code **auto-switches that request to the default Opus model (Opus 4.8)**. The fallback can fire on the **first request of a session**, because that request carries workspace context (CLAUDE.md, git status). >95% of Fable sessions reportedly have no fallback.
  - https://support.claude.com/en/articles/15363606-why-claude-switched-models-in-your-conversation-with-fable-5
  - https://code.claude.com/docs/en/model-config
- Hypothesis: this repo's `CLAUDE.md` opens with a security-testing / defensive-security section, and aitasks is a security-tooling-adjacent framework, which may trip the classifier on the first turn → auto-switch to Opus 4.8.
- **Counter-evidence (important):** the user reports that after `/aitask-pick` starts, manually running `/model fable` inside Claude Code switches to Fable 5 and it stays. So Fable 5 is fully available — the symptom is specifically the launch/first-turn auto-switch, and CLAUDE.md is NOT confirmed as the cause.

## Investigate
1. **Reproduce & characterize:** launch with `--model claude-fable-5` (or via aitask-pick) and observe whether/when the switch to Opus 4.8 happens (at launch, on first turn, or only on specific content). Note whether `/model fable` reliably recovers it.
2. **Test the CLAUDE.md hypothesis:** temporarily trim / relocate the security-testing section of `CLAUDE.md` (and check other security/bio-adjacent loaded docs and the git status surface) and see whether a fresh launch stays on Fable 5. Determine the actual trigger (CLAUDE.md content vs git status vs first-prompt content vs something else).
3. **Test the config toggle:** evaluate `/config` → "switch models when a message is flagged" (off) as a workaround, and `ANTHROPIC_DEFAULT_OPUS_MODEL` / model-config behavior.
4. **Decide the recommendation:** the security section in CLAUDE.md is load-bearing/intentional — do NOT remove it just to dodge the classifier unless the trade-off is clearly worth it. Likely outputs: a documented workaround (e.g. the `/config` toggle, or `/model fable` after start), and/or a note in framework docs about the expected Fable 5 fallback behavior. Removing the security guidance is probably the wrong fix; weigh trade-offs explicitly.

## Deliverable
Findings (what actually triggers the launch-time switch) + a recommendation. No source change is committed unless the investigation shows a clean, low-blast-radius improvement that doesn't weaken the intentional security guidance.
