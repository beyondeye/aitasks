---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [shadow, skills, codex]
gates: [risk_evaluated]
anchor: 2179
followup_kind: risk_mitigation
created_at: 2026-11-27 08:26
updated_at: 2026-11-27 08:26
---

## Origin

Risk-mitigation ("after") follow-up for t2368, created at Step 8d after implementation landed.

## Risk addressed

one answer per wording and model on replay fixtures; real answers could still mix pros and cons or >q could drift long

- The live check has one answer per wording and model on replay fixtures. Real answers could still mix pros and cons in one sentence, or `>q` could drift long · severity: medium · → mitigation: rescan_shadow_q_pd_real_use

## Goal

t2368 (commit `eec4dee54`) changed the shadow's decision help: `>q` is a short answer, `>qd` is the full comparison with a Pros list and a Cons list per option, and `>pd` asks for the same two lists per design decision. It was checked on 8 replay cells only. This task measures real use.

Some days after t2368 landed, once real shadow sessions have run under the new skill text:

1. Run `python3 aidocs/benchmarks/shadow_q/scan_sessions.py --exclude-task 2368` (add `--months` for the months since the change). It prints counts only and never answer text. Keep it that way: aitasks is public and the sessions quote private projects.
2. Record, for `>q`, `>qd` and `>pd` on gpt-6.2-sol, the two samples the scan separates by the skill text each session read (`old` / `new`), with n for each, from the same matcher:
   - `>qd` and `>pd`, `new`: the share of answers with a Pros block and a Cons block. This is the number that says whether the fix holds.
   - `>q`, `new`: the median length (the old median was about 930 characters) and the share with blocks, which should be near zero.
3. State the `unknown` count beside each sample. About half of the `>pd` answers measured for t2368 were `unknown`, because the shadow usually reads `plan-decisions.md` in the same call as a screen capture and the scan refuses to attribute such a read. If that leaves the `new` `>pd` sample too small to read, say so, and propose how to attribute a batched read safely as a separate task. Do not loosen the rule inside this task.
4. Read, without copying them into the repository, a handful of real `>q` answers given on routine workflow menus and a handful of `>qd` answers. Check that `>q` says what is being decided before it recommends, that `>qd` points are about the task and not about the menu, and that the menu's free-text and chat entries are not listed as options. Also look at `>q` / `>qd` with no question on screen, which the replay check did not run.
5. Report the `>px` and `>t` counts and the Claude Code counts (`--agent claude`). At t2368 there was one `>px` answer and one Claude shadow `>q` answer in total, so neither question could be answered. `>px` asks for a labelled "Introduction" / "Motivation" pair, which may meet the same gpt-6.2-sol writing rule that affected `>pd`.

Before numbers to compare with (2026-10 and 2026-11, t2368's own sessions excluded, 17 replay-harness sessions skipped): gpt-6.2-sol `>pd` 7 answers, 0 with labelled `Pros:` / `Cons:` lines, 1 with separate lists; gpt-6.1-sol `>pd` 50 answers, 48 labelled; gpt-6.2-sol `>q` 45 answers, none with lists. The full record is in the archived plan of t2368 ("Final Implementation Notes").

If the new samples show the format is not followed in real use, create a bug task with the numbers. Do not change the skill wording in this task.
