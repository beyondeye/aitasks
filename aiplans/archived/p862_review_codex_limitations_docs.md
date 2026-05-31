---
Task: t862_review_codex_limitations_docs.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t862 — Update website Codex caveats after `default_mode_request_user_input`

## Context

t861 (archived) added the Codex CLI feature flag `default_mode_request_user_input = true`
to the `ait setup`-generated Codex config (`seed/codex_config.seed.toml` →
`.codex/config.toml`). This flag makes Codex's `request_user_input` available in
**default mode**, not only in plan/Suggest mode. The website still documents the old
caveat — that interactive checkpoints only work in plan mode, that task locking is
skipped, and that the user must manually nudge Codex to finalize after implementation.
Those caveats are largely resolved by the flag, so the docs need updating.

t861 deliberately **did not verify** the flag end-to-end and left the framework's forced
plan-mode handling in place (the `ait codeagent invoke` wrapper still types `/plan` to
enter plan mode; Codex skills still enforce plan mode via `codex_interactive_prereqs.md`).
So the docs are rewritten **positively but with one brief hedge** (chosen by the user):
state that prompts work in default mode, while noting once, on the caveats page, that the
wrapper still launches interactive Codex skills through plan mode pending review.

This task is **documentation-only plus the creation of one follow-up task**. It does **not**
touch any code, skill definition, `.j2` template, or golden file — all edits are under
`website/content/`. The follow-up task captures the code investigation (smoke test +
research + possible removal of the forced plan-mode handling).

## Doc edits (all under `website/content/`)

### 1. `docs/installation/known-issues.md` — rewrite the Codex "Interactive checkpoints" caveat
Replace the `#### Interactive checkpoints depend on Suggest mode` subsection (current
lines ~21-32) with a positive subsection `#### Interactive checkpoints`:
- State that `ait setup` enables `default_mode_request_user_input` in the generated
  `.codex/config.toml`, making `request_user_input` available in default mode, so
  interactive checkpoints (task confirmation, plan approval, commit review) work
  throughout the workflow, including post-implementation finalization (commit, archive).
- Add the **one hedge** as a blockquote: `ait codeagent invoke` still launches interactive
  Codex skill operations (`pick`, `explain`, `qa`, `explore`) through plan mode; whether
  that remains necessary is under review.
- **Remove** the two "related problems" bullets (task-locking-skipped, post-impl-stall)
  and the "Workaround" paragraph — both are resolved by the flag.
- Keep `#### Model self-identification is unreliable` unchanged (unrelated to plan mode).
- Keep the `## OpenCode` section and `## References` unchanged.
- Because the heading text changes, grep the repo for links to the old anchor
  `#interactive-checkpoints-depend-on-suggest-mode` and fix any (expected: none).

### 2. `docs/getting-started.md` (line ~83) — flip the intro blockquote
Replace `> Interactive Codex skill flows require **plan mode** because ...` with a positive
one-liner: Codex CLI interactive skill flows work in default mode because `ait setup`
enables the `default_mode_request_user_input` feature. (No hedge here — keep the intro
clean; the hedge lives once on the caveats page.)

### 3. `docs/skills/_index.md` (line ~14) — Multi-agent support blockquote
Drop the clause "Interactive Codex skills require **plan mode** because `request_user_input`
is only available there"; replace with a note that `ait setup` enables
`default_mode_request_user_input` for Codex so interactive prompts work in default mode.
**Keep** the OpenCode plan-mode/task-locking sentence and the Known Issues relref.

### 4. Seven skill docs — *soften* (not remove) the "Codex CLI note" blockquote
Files: `docs/skills/aitask-pick/_index.md`, `docs/skills/aitask-explore.md`,
`docs/skills/aitask-fold.md`, `docs/skills/aitask-review.md`,
`docs/skills/aitask-pr-import.md`, `docs/skills/aitask-pickrem.md`,
`docs/skills/aitask-pickweb.md`.
Current note says you "will need to explicitly tell the agent to continue ... because
`request_user_input` is only available in plan mode." Replace each with a softened version
that frames continuation as automatic now, keeping the nudge prompts as a fallback, e.g.:
> **Codex CLI note:** With `ait setup`'s `default_mode_request_user_input` feature enabled,
> Codex carries the workflow through implementation and finalization (commit, archive) on its
> own. If it ever stops short, prompt it to continue — e.g., `Good, now finish the workflow`
> or `Good, now continue`.
Use one consistent softened wording across all seven for uniformity.

### 5. `docs/commands/codeagent.md` (line ~155) — brief forward note
The paragraph documenting the `/plan` PTY helper stays (it accurately describes current
`ait codeagent invoke` behavior and matches the hedge in #1). Append one sentence: now that
`ait setup` enables `default_mode_request_user_input`, whether this plan-mode launch is still
required is under review.

## Follow-up task (created post-approval, during Step 7 — NOT in plan mode)

Create one **standalone** task via the Batch Task Creation Procedure
(`./.aitask-scripts/aitask_create.sh --batch`), `--commit`:
- name: `investigate_codex_forced_plan_mode`
- issue_type: `chore`, priority: `medium`, effort: `medium`, labels: `codexcli`, depends: `[862]`
- Description covers:
  1. **Smoke test** — launch Codex (via `ait codeagent invoke` and directly), attempt a
     `request_user_input` prompt in default mode (not plan mode), confirm it works with
     `default_mode_request_user_input = true`.
  2. **Research** — Codex CLI docs + GitHub issues on `default_mode_request_user_input` /
     `request_user_input` availability/stability (under-development flag).
  3. If verified, evaluate removing/relaxing the forced plan-mode handling:
     `.aitask-scripts/aitask_codeagent.sh`, `.aitask-scripts/aitask_skillrun.sh`,
     `.aitask-scripts/aitask_codex_plan_invoke.py`, `.agents/skills/codex_interactive_prereqs.md`.
  4. Consider keeping forced plan mode only for genuine-planning skills (`aitask-pick`,
     `aitask-explore`); drop it for others (`qa`, `explain`).
  5. On final decision, update `docs/commands/codeagent.md` + `docs/installation/known-issues.md`
     to remove the "under review" hedge this task adds.

## Verification

- `cd website && hugo build --gc --minify` — confirm the site builds (no broken relrefs/shortcodes/anchors).
- `grep -rn -i "only available in plan mode\|depend on Suggest mode" website/content/docs/` — confirm no
  stale Codex plan-mode caveat phrasing remains (OpenCode plan-mode mentions are expected to stay).
- Confirm the follow-up task file exists (`./.aitask-scripts/aitask_ls.sh` / `aitask_query_files.sh resolve <newid>`).

## Post-Implementation (Step 9)

Profile 'fast', current branch — no worktree/branch cleanup. Commit code (website docs) with
`documentation: ... (t862)`, commit plan file with `./ait git`, then archive via
`./.aitask-scripts/aitask_archive.sh 862` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Updated 11 website doc files under `website/content/` to
  reflect that `ait setup` now enables the Codex `default_mode_request_user_input`
  feature (added by t861), so `request_user_input` works in default mode:
  - `installation/known-issues.md` — replaced the "Interactive checkpoints depend on
    Suggest mode" subsection with a positive "Interactive checkpoints" subsection;
    removed the task-locking/post-impl-stall bullets and workaround; added one
    "under review" blockquote hedge about the wrapper still launching via plan mode.
  - `getting-started.md` and `skills/_index.md` — flipped the plan-mode caveat to the
    default-mode framing (kept the OpenCode plan-mode/task-locking note in `_index.md`).
  - 7 skill docs (`aitask-pick/_index`, `aitask-explore`, `aitask-fold`, `aitask-review`,
    `aitask-pr-import`, `aitask-pickrem`, `aitask-pickweb`) — softened the "Codex CLI note"
    blockquote to one consistent wording (continuation is automatic; nudge prompts kept
    as a fallback).
  - `commands/codeagent.md` — appended one "under review" sentence to the `/plan` PTY-helper
    paragraph (the paragraph itself stays, as it accurately documents current behavior).
  - Created follow-up task **t866** (`investigate_codex_forced_plan_mode`, chore, depends [862])
    covering the smoke test + research + possible removal of the forced plan-mode handling.
- **Deviations from plan:** None. The user chose the "Resolved + brief hedge" framing during
  planning; per that option's preview the per-skill notes were *softened* (not removed).
- **Issues encountered:** Plan externalization returned `MULTIPLE_CANDIDATES` (parallel
  sessions had recent internal plan files); resolved by re-running with `--internal` pointing
  at this session's authoritative plan (`functional-prancing-flamingo.md`).
- **Key decisions:** Kept `codeagent.md`'s `/plan` PTY-helper paragraph (still accurate
  current behavior, consistent with the known-issues hedge) rather than deleting it; the
  follow-up t866 will remove both "under review" hedges once the forced plan mode is decided.
  No code/skill/`.j2`/golden changes — docs-only, so no `aitask_skill_verify.sh` or goldens needed.
- **Upstream defects identified:** None.
