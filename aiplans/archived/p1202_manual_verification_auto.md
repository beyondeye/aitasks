# Plan: Auto-execution of manual-verification checklist for t1202

- **Task:** t1202 (`aitasks/t1202_manual_verification_shadow_review_flag_omitted_findings_foll.md`)
- **Verifies:** t1200 — "Flag omitted shadow review findings instead of hiding them" (commit `292a8585a`)
- **Mode:** autonomous auto-verification (`auto-verification.md`, strategy = autonomous)
- **Working directory:** `/home/ddt/Work/aitasks` (current branch, profile `fast`)

## Approach

t1200 changed only **agent-facing skill text** — `.claude/skills/aitask-shadow/`
(`SKILL.md`, `impl-challenge.md`, `impl-review-angles.md`) — plus tests and
website docs. Every checklist item therefore asks about **live shadow output**,
which no static assertion can answer: reading the skill text back would only
prove the source agrees with itself.

Verification was driven by **three independent live shadow runs**, each an agent
read-and-following the real procedure files against a real repo diff, plus one
**parser harness** run against minimonitor's own module:

| Run | Skill revision | Tier | Target |
|-----|----------------|------|--------|
| A   | post-t1200 (working tree) | Default (inferred from an unqualified "adversarial review") | t1167 — commit `9d3122eb8`, plan `p1167` |
| B   | pre-t1200 (`292a8585a^`, extracted to scratch) | Default (same unqualified ask) | t1167 — identical diff and plan |
| C   | post-t1200 (working tree) | Advanced (explicitly named) | t635_33 — commit `86d2faa75`, 48 files / ~3000 lines |

Run A vs B is the A/B the checklist demands for the core symptom. Run C exists
solely to fill the Advanced `<=8` cap and force the omission disclosure.

**Target selection.** `p1167` was chosen because its `## Risk` section carries an
*explicitly accepted* residual-limits risk with a stated rationale ("both are
accepted, documented limits rather than latent bugs") — the precondition items 1
and 3 require. `t635_33` was chosen as the largest recent commit, to make the
Advanced cap reachable.

## Execution Log

### Item 1 — accepted risk surfaces as `informational`, rationale named
- **Item text:** Default-tier review against a plan with an explicitly ACCEPTED risk; confirm it appears as `informational` with the acceptance rationale named, instead of vanishing.
- **Approach:** live shadow run (Run A).
- **Action run:** agent read-and-followed `.claude/skills/aitask-shadow/impl-challenge.md` against `git show 9d3122eb8` + `aiplans/archived/p1167_concern_parser_wrap_tolerant_marker.md`.
- **Output (trimmed):** finding 6 of 6 — *"The two residual limits are validly accepted and I am not asking for a change. Severity: low. Disposition: informational."* — naming the plan's rationale (explicitly documented, arithmetically justified ~165-char envelope at 55 columns, pinned by the at-bound / over-bound / spaced-slash test trio, producer-side short-region rule still primary). Concern block carried `- [low | accepted limits] ... Disposition: informational.`
- **Verdict:** pass.
- **Path caveat:** driven by an agent following the skill files directly, **not** spawned through minimonitor's `e` trigger. t1200 changed only the skill text; the minimonitor leg was verified separately against its own parser module (item 4).

### Item 2 — inferred tier announced with the recommended alternative
- **Approach:** live shadow run (Run A), whose user ask was verbatim `adversarial review` with no qualifier.
- **Output (trimmed):** first line — *"**Tier: Default** — an unqualified 'adversarial review' resolves to the legacy three-axis pass, so I inferred it. **Advanced is the recommended tier; say \"advanced review\" for it.**"*
- **Independent control:** Run B (pre-t1200 text, identical ask) opened with *"The user's ask is an unqualified 'adversarial review' → Default (legacy) tier"* — states the tier, names **no** alternative. The announcement is attributable to t1200.
- **Verdict:** pass.

### Item 3 — anti-drop rule; Default no longer returns few/no concerns
- **Approach:** A/B of Run A against Run B on the identical diff, plan and ask.
- **Output (trimmed):**
  - Run B (pre): **4** findings — 2 `blocking`, 2 `follow-up`. No `informational` partition (it did not exist).
  - Run A (post): **6** findings — 2 `blocking`, 3 `follow-up`, 1 `informational`. The informational one is explicitly a half-believed candidate reported rather than dropped: *"Flagging it only so you can judge the 3-row bound yourself."*
- **Verdict:** pass.
- **Honest limitation:** single sample per arm, and the **baseline did not itself reproduce** the reported "I very rarely get concerns" symptom (4 findings is not "few or no"). This establishes that post-t1200 Default behaviour satisfies the stated criterion and that the informational partition is populated; it does **not** longitudinally prove the user's symptom is cured. The user's own accumulated experience remains the stronger judge.

### Item 4 — emitted block parses in minimonitor's picker
- **Approach:** parser harness against minimonitor's real seam, fed the **actual** concern block emitted by Run A (not a synthetic fixture).
- **Action run:** `python3 scratchpad/verify_item4.py post_default_capture.txt`, importing `monitor.concern_parser` from `.aitask-scripts/` — the same `has_concern_block` / `parse_concerns` / `build_clipboard_payload` that `minimonitor_app.py:1480-1488` and `:1442` call.
- **Output (trimmed):**
  - `has_concern_block -> True` (strict auto-offer trigger fires)
  - `parse_concerns -> 6 concerns`, 0 items missing a `Disposition:` trailer
  - disposition sequence `['blocking', 'blocking', 'follow-up', 'follow-up', 'follow-up', 'informational']` — partition order correct
  - `build_clipboard_payload` on the informational item reproduces `- [low | accepted limits] <body>` byte-for-byte, `Disposition: informational.` intact
- **Verdict:** pass.

### Item 5 — no-silent-omission disclosure fires at the cap
- **Approach:** live Advanced review (Run C) on a diff large enough to exceed the `<=8` cap.
- **Output (trimmed):** exactly 8 findings reported, followed by *"**Omission disclosure (cap):** 1 informational finding was cut by the ≤8 cap — [what it was] … I classified it informational because …"*, plus a separate disclosure of its one REFUTED drop with the refuting evidence quoted.
- **Verdict:** pass. Wording differs from the checklist's illustrative `"cap: 3 follow-up and 2 informational findings omitted"` but satisfies the catalog spec ("how many, from which partition, and why").

### Item 6 — `informational` region stays short
- **Approach:** measured on the real regions emitted by Run A (same harness as item 4).
- **Output:** region lengths `19, 21, 21, 23, 23, 15` — max **23**, all within the ~30-char rule. The informational item's region was `accepted limits` (15). No marker-join recovery was needed; all six markers parsed on their own row.
- **Verdict:** pass.

## Upstream defect identified

- `.aitask-scripts/aitask_verification_parse.py:118-121` — `_strip_annotation`
  splits on the **first** occurrence of `SUFFIX_SPLIT` (` — `, space + U+2014 +
  space) anywhere in the item text, not on the annotation boundary. Any checklist
  item whose own prose contains an em-dash therefore loses everything after it on
  the first `set`, permanently. This fired live here: items 2 and 3 of t1202 were
  truncated mid-sentence and had to be restored by hand from commit `8f23b114e`.
  Pre-existing and independent of t1200 — the same corruption would hit any
  manual-verification task with an em-dash in a checklist item, and the checklist
  text is the archived record of what was verified. A boundary-anchored strip
  (e.g. match ` — (PASS|FAIL|SKIP|DEFER) \d{4}-\d{2}-\d{2}` from the right) would
  fix it.

## Cleanup

- Scratch files under `/tmp/claude-1000/.../scratchpad/` (`pre_t1200_shadow/`,
  `t1167_diff.txt`, `post_default_capture.txt`, `verify_item4.py`) — session
  scratchpad, discarded with the session. No tmux sessions were created.
- No repository files were modified by any run: all three shadow agents were
  instructed read-only, and the only writes were the checklist annotations, the
  two hand-restored item texts, and this plan file.
