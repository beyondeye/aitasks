---
priority: medium
effort: medium
depends: [1200]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1200]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-21 12:24
updated_at: 2026-07-21 17:47
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1200

## Verification Checklist

- [x] [t1200] Run a Default-tier shadow implementation review from minimonitor against a task whose plan has an explicitly ACCEPTED risk. Confirm the accepted risk appears as an `informational` finding with the plan's acceptance rationale named, instead of vanishing from the output entirely (the reported t1200 symptom). — PASS 2026-07-21 17:47 auto: live Default review of t1167 (plan p1167 carries an explicitly accepted residual-limits risk) emitted finding 6 as '[low | accepted limits] ... Disposition: informational.', naming the plan's acceptance rationale (documented, arithmetically justified ~165-char envelope, pinned by the at-bound/over-bound/spaced-slash trio). Not omitted. PATH CAVEAT: driven by an agent read-and-following .claude/skills/aitask-shadow/impl-challenge.md directly, not spawned through minimonitor's 'e' trigger - t1200 changed only the skill text, and the parser leg was checked against minimonitor's own module (item 4).
- [x] [t1200] Ask the shadow for an unqualified "adversarial review". Confirm it announces the inferred tier before starting, e.g. "Running Default (the legacy three-axis review) — Advanced is the recommended tier; say 'advanced review' for it." A user must never have to infer the tier from the output. — PASS 2026-07-21 17:43 auto: unqualified 'adversarial review' ask; first output line was 'Tier: Default — an unqualified adversarial review resolves to the legacy three-axis pass, so I inferred it. Advanced is the recommended tier; say "advanced review" for it.' Inferred tier + alternative announced before starting. Pre-t1200 baseline run on the same ask stated the tier but named no alternative.
- [x] [t1200] Confirm a Default-tier review now surfaces candidates it is unsure about (the anti-drop rule) rather than returning few or no concerns. Compare against pre-t1200 behavior on a comparable diff — this is the core "I very rarely get concerns" symptom and can only be judged on live output. — PASS 2026-07-21 17:43 auto: A/B on the identical diff (t1167 commit 9d3122eb8 + plan p1167). Pre-t1200 skill text: 4 findings, all blocking/follow-up. Post-t1200: 6 findings incl. an explicitly unsure-but-reported informational one ('flagging it only so you can judge the 3-row bound yourself'). Anti-drop honored; no 'few or no concerns' outcome. Caveat: single sample, and the baseline did not itself reproduce the 'very rarely get concerns' symptom, so this shows post-behavior is good rather than proving the symptom is cured longitudinally.
- [x] [t1200] Confirm the emitted concern block still parses in minimonitor's picker: the auto-offer fires, items appear in blocking -> follow-up -> informational order, and forwarding an informational item to the followed agent preserves its "Disposition: informational." trailer verbatim. — PASS 2026-07-21 17:43 auto: fed the live-emitted block through minimonitor's own seam (monitor.concern_parser). has_concern_block=True (auto-offer fires), parse_concerns=6, disposition sequence blocking,blocking,follow-up,follow-up,follow-up,informational (partition order correct, 0 items missing a trailer), and build_clipboard_payload on the informational item reproduces its body byte-for-byte including 'Disposition: informational.'
- [x] [t1200] Confirm the no-silent-omission disclosure actually fires: run an Advanced or Deep review on a diff large enough to hit the findings cap and check for an explicit trailing line such as "cap: 3 follow-up and 2 informational findings omitted". — PASS 2026-07-21 17:47 auto: live Advanced review of t635_33 (commit 86d2faa75, 48 files/~3000 lines) filled the <=8 cap and emitted a trailing 'Omission disclosure (cap): 1 informational finding was cut by the <=8 cap - <what it was and why classified informational>'. Names the count and the partition as the catalog requires; also disclosed its single REFUTED drop with the refuting evidence. Wording differs from the checklist's illustrative example but matches the spec ('how many, from which partition, and why').
- [x] [t1200] Confirm an `informational` concern region stays short (<= ~30 chars, e.g. `accepted risk` or `basename.ext:LINE`) in real output, so the `[priority | region]` marker never wraps and stays parseable. — PASS 2026-07-21 17:43 auto: regions in live output were 19/21/21/23/23/15 chars (max 23, all <= 30); informational item's region was 'accepted limits' (15). No marker-join recovery needed - all six parsed on their own row.
