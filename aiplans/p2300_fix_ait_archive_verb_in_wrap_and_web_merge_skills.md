---
Task: t2300_fix_ait_archive_verb_in_wrap_and_web_merge_skills.md
Base branch: main
Output branch: main
---

# Plan: t2300 — replace the non-existent `ait archive` verb in skill sources

## Context

The `ait` dispatcher has no `archive` verb (confirmed: `ait` routes only
`brainstorm archive` and `migrate-archives`). Archival is done by
`./.aitask-scripts/aitask_archive.sh <task_num>` (its `--help`:
`Usage: aitask_archive.sh [options] <task_num>`). t2284 already corrected
the same claim on `website/content/docs/development/task-format.md`. Two skill
sources still tell the user to run the missing verb, and a user who follows
that recovery hint gets an "unknown command" error at exactly the moment
something has already gone wrong.

`git grep -n "ait archive"` across the tree (excluding task data) finds:

| file | line | kind |
|---|---|---|
| `.claude/skills/aitask-wrap/SKILL.md.j2` | 349 | skill source (task scope) |
| `.claude/skills/aitask-web-merge/materialize-gates.md` | 33 | skill source (task scope) |
| `tests/golden/skills/aitask-wrap/SKILL-{default,fast,remote}-{claude,codex}.md` | 349 / 311 | goldens, regenerated |
| `tests/lib/docs_vocabulary_scan.py` | 193 | code comment, same wrong verb (`ait archive --superseded`) |
| `tests/test_docs_vocabulary_coverage.sh` | 329 | code comment, same wrong verb |

Port status:
- **aitask-wrap.** The Codex (`.agents/skills/aitask-wrap-*-codex-/`) and
  OpenCode (`.opencode/skills/aitask-wrap-*-/`) copies are gitignored
  per-profile renders of the same `.claude/skills/aitask-wrap/SKILL.md.j2`.
  The stubs re-render them on next invocation, so editing the template is the
  port. No hand-maintained ported copy carries the text.
- **aitask-web-merge.** `.agents/skills/aitask-web-merge/SKILL.md` and
  `.opencode/skills/aitask-web-merge/SKILL.md` contain no `materialize-gates`
  content, so there is nothing to port. That they lack the procedure is a
  separate existing port gap and is not in this task's scope.

`materialize-gates.md` appears in no golden, so it needs no regeneration.

## Implementation steps

1. **`.claude/skills/aitask-wrap/SKILL.md.j2:349`.** Replace
   `` the user can archive manually later with `ait archive <N>`. ``
   with
   `` the user can archive manually later with `./.aitask-scripts/aitask_archive.sh <N>`. ``

2. **`.claude/skills/aitask-web-merge/materialize-gates.md:33`.** The current
   hint has two defects, and both are fixed here:
   - `ait archive` does not exist.
   - `aitask_gate.sh materialize-active` is incomplete. It requires
     `<task-id> --profile <file>`; run bare it dies with
     `Usage: aitask_gate.sh materialize-active <task-id> --profile <file>`.
     Giving a complete raw invocation is also wrong here: the user would have
     to pick the profile file by hand, which bypasses the marker-provenance
     validation that this procedure exists to enforce ("never guess a
     profile").

   So the manual path goes through the **same validated helper** the
   procedure already runs, `./.aitask-scripts/aitask_web_merge.sh materialize`.
   It reads the marker's recorded `profile` / `profile_filename`, validates
   them, then calls `materialize-active` with exactly that profile. Replace
   the "Abort this branch" description with:

   > `Code merge stays committed; task stays unarchived — re-run aitask-web-merge later (no-op merge), or repair manually: fix the marker/profile, re-run ./.aitask-scripts/aitask_web_merge.sh materialize <task_id> <marker_json_file> until it returns a continue outcome (WEBMAT_OK or WEBMAT_SKIP:no-profile, as listed above), then ./.aitask-scripts/aitask_archive.sh <task_id>`

   The success condition is **the procedure's own continue set**, not
   `WEBMAT_OK` alone. The helper's header contract
   (`.aitask-scripts/aitask_web_merge.sh:20-30`) gives `WEBMAT_SKIP:no-profile`
   exit 0 for a legacy marker that carries no provenance fields, and this
   procedure already treats it as "continue" (the raw `gates:` fallback
   governs; never guess a profile). Requiring `WEBMAT_OK` would strand a user
   who repaired a malformed temp file by restoring a valid **legacy** marker:
   the helper would succeed with `SKIP` while the hint still said to retry.
   Naming both outcomes, with "as listed above" pointing at the procedure's
   own outcome list, keeps the hint tied to that list. Neither outcome picks a
   profile by hand, so the never-guess rule holds.

   `<marker_json_file>` is the same temp file this procedure already tells the
   reader to write from the marker JSON (`git show origin/<branch>:.aitask-data-updated/<marker>`,
   SKILL.md Step 1), so the hint introduces no new concept.

3. **Same-class comment fixes.** These are comments only, with no behaviour
   change:
   - `tests/lib/docs_vocabulary_scan.py:193`: `` `ait archive --superseded` `` →
     `` `aitask_archive.sh --superseded` ``.
   - `tests/test_docs_vocabulary_coverage.sh:329`: `` `ait archive --superseded` `` →
     `` `aitask_archive.sh --superseded` ``.

4. **Regenerate the aitask-wrap goldens.** The skill has per-agent goldens
   because its template has an `{% if agent %}` gate, so regenerate all 6
   (claude + codex × default/fast/remote) with the recipe in
   `aidocs/framework/skill_authoring_conventions.md` ("Regenerate goldens after
   any `.md.j2` or closure edit"):
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for agent in claude codex; do for profile in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       .claude/skills/aitask-wrap/SKILL.md.j2 aitasks/metadata/profiles/$profile.yaml $agent \
       > tests/golden/skills/aitask-wrap/SKILL-${profile}-${agent}.md
   done; done
   git diff --stat tests/golden/skills/aitask-wrap/
   ```
   The diff must be exactly one changed line per golden. Any other diff is a
   regression and must be investigated, not committed.

5. **Commit.** Use one source commit with explicit paths (the worktree has
   unrelated changes from other sessions, so never use `git add -A`). It
   contains the two skill sources, the 6 goldens and the 2 test files:
   `bug: Replace the non-existent ait archive verb in skill sources (t2300)`.

6. **Step 9 (Post-Implementation).** Archive t2300 through the standard
   task-workflow Step 9 flow.

## Verification

- `git grep -n "ait archive" -- . ':!aitasks' ':!aiplans'` returns no hits.
- **Every command the two hints name is complete.** The grep above only proves
  the old wording is gone; it does not prove the new hints work. Check them
  against the helpers' real usage:
  - `./.aitask-scripts/aitask_archive.sh --help` shows `<task_num>` as its only
    required argument.
  - `./.aitask-scripts/aitask_web_merge.sh materialize` with no arguments
    prints `WEBMAT_INVALID:usage (expected: materialize <task_id> <marker_json>)`,
    which matches the two arguments the hint names.
  - `grep -n "materialize-active" .claude/skills/aitask-web-merge/materialize-gates.md`
    finds no remaining bare, argument-less reference.
  - The hint's success set matches the procedure's continue outcomes. The
    `WEBMAT_*` tokens named in the "Abort this branch" description are exactly
    the ones the same file's outcome list marks "Continue": `WEBMAT_OK`,
    `WEBMAT_SKIP:no-profile`. That is the exit-0 set of the helper's header
    contract.
- `bash tests/test_skill_render_aitask_wrap.sh` passes.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `bash tests/test_docs_vocabulary_coverage.sh` still passes (only a comment changed).
- `python3 -m py_compile tests/lib/docs_vocabulary_scan.py` succeeds.

## Risk

### Code-health risk: low
None identified. The change touches only prose and comments; goldens are
regenerated in the same commit and checked by diff.

### Goal-achievement risk: low
None identified. The full-tree grep shows every occurrence; the Codex/OpenCode
wrap variants are renders of the edited template, and the web-merge ports carry
no copy of the text. The web-merge hint is checked for complete invocations,
not only for the absence of the old verb. It routes the user through the
validated `aitask_web_merge.sh materialize` helper rather than a raw
`materialize-active`, so the manual path keeps the marker-provenance check.

## Final Implementation Notes
- **Actual work done:** All six plan steps up to the commit were carried out as written:
  - The wrap `.md.j2` archive-failure hint now names `./.aitask-scripts/aitask_archive.sh <N>`.
  - The web-merge `materialize-gates.md` "Abort this branch" hint now gives a full recovery route: fix the marker/profile, then re-run `./.aitask-scripts/aitask_web_merge.sh materialize <task_id> <marker_json_file>` until it returns a continue outcome (`WEBMAT_OK` or `WEBMAT_SKIP:no-profile`), then run `./.aitask-scripts/aitask_archive.sh <task_id>`.
  - Two test comments that named `ait archive --superseded` were corrected.
  - All 6 aitask-wrap goldens (claude/codex × default/fast/remote) were regenerated.
- **Deviations from plan:** None during implementation. Two plan-review rounds before approval revised Step 2:
  - The bare `aitask_gate.sh materialize-active` reference was replaced with the validated `aitask_web_merge.sh materialize` helper. The bare call dies on its missing `<task-id> --profile <file>` arguments, and a hand-picked profile would bypass the marker-provenance check.
  - The success condition now names the procedure's full continue set rather than `WEBMAT_OK` alone, because `WEBMAT_SKIP:no-profile` also exits 0 for a legacy marker.
- **Issues encountered:** None.
- **Key decisions:**
  - No port edits were needed. The Codex and OpenCode aitask-wrap variants are gitignored renders of the same `.md.j2`. The `.agents/` and `.opencode/` aitask-web-merge ports are thin "Source of Truth" wrappers that read `.claude/skills/aitask-web-merge/SKILL.md` and follow it, so they pick up the `materialize-gates.md` edit directly. The planning note that called this a port gap was wrong: there is no gap.
  - `materialize-gates.md` appears in no golden, so it needed no regeneration.
- **Verification results:**
  - `git grep "ait archive"` (excluding task data) returns no hits.
  - `aitask_archive.sh --help` shows `<task_num>` as its only required argument.
  - `aitask_web_merge.sh materialize` with no arguments prints `WEBMAT_INVALID:usage (expected: materialize <task_id> <marker_json>)`.
  - `materialize-gates.md` has no bare `materialize-active` reference left.
  - `tests/test_skill_render_aitask_wrap.sh` passes 96/96.
  - `tests/test_docs_vocabulary_coverage.sh` passes 32/32.
  - `aitask_skill_verify.sh` reports OK.
  - `py_compile` of `docs_vocabulary_scan.py` succeeds.
- **Upstream defects identified:** None
