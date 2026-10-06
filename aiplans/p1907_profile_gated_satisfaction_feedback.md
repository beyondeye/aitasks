---
Task: t1907_profile_gated_satisfaction_feedback.md
Base branch: main
Output branch: main
---

# t1907 — Profile-gated satisfaction feedback (render away when disabled; `fast` → off)

## Context

`enableFeedbackQuestions` already exists, but `satisfaction-feedback.md` gates only
Step 1 substep 1 ("skip the remainder"). A `false` profile (today `remote`) still
renders the NON-SKIPPABLE banner, the rating `AskUserQuestion` and the
`aitask_verified_update.sh` call — the agent is told to skip text that is still
there. Goal: a disabled profile renders **no** banner, prompt or score update,
**keeps** the Step 0 usage bump (`aitask_usage_update.sh` — the only usagestats
data path), and the shipped `fast` profile defaults to disabled.

## Approach (refines the task's suggested split)

Gate **inside the procedure**, not at the call sites. This is the existing
`parallel-assessment.md` precedent (the procedure renders its own disabled form),
adapted because usage must survive: every call site keeps calling the procedure,
and the rendered procedure for a disabled profile *is* just the usage step.

Why not split into two files / gate each call site: ~10 call sites (task-workflow
SKILL.md 9b + child stop, planning.md, cross-repo-child-assignment.md, wrap, qa,
qa/test-plan-proposal, the `_auto_continue_block.j2` macro for explore/revert)
plus 10 static skills that read the raw source. A split forces a new closure file
into every one of them and duplicates the guard semantics; procedure-level gating
changes one file, keeps `usage_collected` / `feedback_collected` /
`detected_agent_string` untouched, keeps the raw key-absent branch valid for the
static skills, and leaves the Step 0 `aitask_usage_update.sh` call where it is
(so t1357_3's planned `--task-id` edit target does not move).

## Steps

### 1. `.claude/skills/task-workflow/satisfaction-feedback.md` — restructure
Let `OFF` = `profile.enableFeedbackQuestions is defined and not profile.enableFeedbackQuestions`
(Jinja section separators per the `{# ---------- key ---------- #}` convention).

- **Intro paragraph**: `OFF` → "records skill usage for the current code
  agent/model; Profile '<name>' sets `enableFeedbackQuestions: false`, so there is
  no satisfaction question and no verified-score update." Else → existing text.
- **Move the NON-SKIPPABLE banner** from before Step 0 to immediately before
  Step 1 (it only concerns Step 1 substep 3), inside the else branch.
- **Step 0** stays unconditional (still the only `aitask_usage_update.sh`) and its
  behaviour is unchanged, but **reword its explanatory sentence** (:28), which
  today names `AskUserQuestion` and "the score prompt below" — both wrong in a
  disabled render, and the `AskUserQuestion` token would defeat the step-5
  absence check. New text (true for every profile): "Bumps `usagestats[skill]`
  for the current model/skill regardless of `enableFeedbackQuestions`. This is
  the only data path that records runs which never reach a rating — code agents
  that skip every interactive prompt after `ExitPlanMode` (e.g., Codex CLI), and
  profiles that disable feedback questions."
- **Step 1**:
  - `OFF` → `## Step 1 — Satisfaction question (disabled by profile)`: one
    paragraph: "Profile '<name>' sets `enableFeedbackQuestions: false` — there is
    no satisfaction question and no verified-score update; the procedure ends
    after Step 0. Display: `Profile '<name>': feedback questions disabled`."
  - else → banner + existing Step 1 verbatim, with the inner conditional reduced
    to two arms: key defined (=true) → "Profile '<name>' sets
    `enableFeedbackQuestions: true`. Continue with step 2 (no skip)."; key absent
    → the existing runtime **Profile check** (static skills read this arm).
- Result: `fast`/`remote` renders contain no `AskUserQuestion`, no `How well did
  this skill work?`, no `aitask_verified_update.sh`, no `NON-SKIPPABLE`; `default`
  and the raw source keep everything.

### 2. Profiles
`aitasks/metadata/profiles/fast.yaml` and `seed/profiles/fast.yaml`:
`enableFeedbackQuestions: false`, with a short comment ("usage is still recorded;
only the rating prompt and verified-score update are rendered away").

### 3. Framework docs (no Jinja, neutral wording)
- `.claude/skills/task-workflow/profiles.md`: schema row (:42) → "`false` = render
  the rating prompt and verified-score update away (usage is still recorded);
  omit or `true` = ask"; note (:283) likewise; mention the shipped `fast` and
  `remote` both set `false`.
- `.claude/skills/task-workflow/SKILL.md` Procedures index (:1088): "Record skill
  usage and, when the profile enables it, collect a rating and update verified
  model scores." (true for every profile — no gating needed).

- `.aitask-scripts/lib/profile_editor.py:249-254` (`ait settings` help for
  `enableFeedbackQuestions`): replace "When false, the Satisfaction Feedback
  Procedure is skipped." with "When false, only the rating question and the
  verified-score update are skipped — skill usage is still recorded." (title
  string unchanged; no test pins this text).

### 4. Website docs
- `website/content/docs/skills/aitask-pick/execution-profiles.md:16` (fast bullet:
  "…and skip feedback questions") and `:116` ("both shipped `fast` and `remote`
  disable it; usage is still counted").
- `website/content/docs/skills/verified-scores.md:21`: add that disabling skips
  only the rating — the run is still counted in usage stats; shipped `fast` and
  `remote` disable it.
- Run `python3 check_links.py --build` in `website/`.

### 5. Tests
- `tests/test_skill_parity_runtime_vs_rendered.sh:146`: fast row → PRESENT
  "Profile 'fast' sets \`enableFeedbackQuestions: false\`", ABSENT "Profile 'fast'
  sets \`enableFeedbackQuestions: true\`". remote/default rows unchanged.
- `tests/test_skill_render_task_workflow.sh` (next to :334): new block —
  - for `fast` and `remote`: contains `aitask_usage_update.sh`; not contains
    `aitask_verified_update.sh`, `How well did this skill work?`,
    `NON-SKIPPABLE`, and the prompt instruction ``Use `AskUserQuestion` `` (the
    instruction itself, not every mention of the tool — the step-1 rewording
    removes the Step 0 mention too, so a bare `AskUserQuestion` absence also
    holds, but the assertion targets the instruction so a future harmless
    mention cannot fail it for the wrong reason);
  - `default`: contains all of usage, verified_update, rating question, banner;
  - synthetic profile `enableFeedbackQuestions: true` (Test-4 synthetic-profile
    pattern, own tmp file + trap): contains "sets `enableFeedbackQuestions: true`.
    Continue with step 2", rating question, both scripts — the true arm now has no
    committed profile, so this is its only coverage.

### 6. Goldens & committed headless prerenders (same commit as the template)
- Regenerate `tests/golden/procs/task-workflow/satisfaction-feedback-{default,fast,remote}.md`
  and `SKILL-{default,fast,remote}.md` (index wording) with `skill_template.py
  <file> aitasks/metadata/profiles/<p>.yaml claude`. Review the diffs: only the
  intended hunks.
- `./.aitask-scripts/aitask_skill_rerender.sh remote` → commit the changed files
  under `.claude/skills/task-workflow-remote-/`, `.agents/skills/task-workflow-remote-codex-/`,
  `.opencode/skills/task-workflow-remote-/` (satisfaction-feedback.md, SKILL.md,
  profiles.md) — commit only those paths (shared dirty worktree).
- `./.aitask-scripts/aitask_skill_verify.sh` must pass (catches any other golden
  or prerender that embeds the changed text).

### 7. Commits
- Code: `enhancement: Render satisfaction feedback away when the profile disables it (t1907)`
  — named paths only (source, seed profile, docs, tests, goldens, prerenders).
- `aitasks/metadata/profiles/fast.yaml` is task-data: commit via
  `./.aitask-scripts/aitask_task_commit.sh -m "ait: Disable feedback questions in fast profile (t1907 data)" aitasks/metadata/profiles/fast.yaml`.

## Verification
- `bash tests/test_skill_render_task_workflow.sh`
- `bash tests/test_skill_parity_runtime_vs_rendered.sh`
- `bash tests/test_skill_render_aitask_qa.sh`, `tests/test_skill_render_aitask_wrap.sh`,
  `tests/test_skill_render_aitask_explore.sh`, `tests/test_skill_render_aitask_revert.sh`,
  `tests/test_skill_render_aitask_pickrem.sh`, `tests/test_skill_render_aitask_pickweb.sh`
  (call-site goldens should be unchanged)
- `./.aitask-scripts/aitask_skill_verify.sh`
- Manual: render `satisfaction-feedback.md` for fast → only Step 0 + the disabled
  note; `grep -c aitask_usage_update` = 1; `grep -c AskUserQuestion` = 0.
- `python3 -c "import ast,sys; ast.parse(open('.aitask-scripts/lib/profile_editor.py').read())"`
  plus any `tests/test_profile_editor*` / settings test that exists.
- `cd website && python3 check_links.py --build`

## Follow-ups (suggest, do not create unasked)
- Codex/OpenCode: no hand-maintained copies exist — their task-workflow variants
  are rendered from the `.claude` source (committed remote prerenders regenerated
  in step 6), so no port task is needed; confirm at Step 8.
- Offer a `/aitask-note` to t1357_3: the `aitask_usage_update.sh` call lives in
  `satisfaction-feedback.md` Step 0 (not SKILL.md ~:782) and stays rendered for
  every profile.

Step 9 (Post-Implementation): current-branch mode — archive via
`aitask_archive.sh 1907`, push with `./ait git push`.

## Risk

### Code-health risk: low
- Nested Jinja in a raw source that 10 static skills read verbatim could make the key-absent branch harder to follow · severity: low · → mitigation: already in plan (step 5 `default` render assertions pin the key-absent arm; separator-comment convention)
- Committed remote prerenders / goldens drift if the rerender is skipped · severity: low · → mitigation: already in plan (step 6 rerender + `aitask_skill_verify.sh` walk-verify)

### Goal-achievement risk: low
- Call-site headings ("Step 9b: Satisfaction Feedback") still read "feedback" in the fast render, although the procedure they call renders only usage · severity: low · → mitigation: accepted by design (the procedure is the single point of truth; the index wording is made profile-neutral in step 3)
