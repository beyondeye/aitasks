---
Task: t1709_trail_skill_dirty_owner_refusal_note.md
Branch: main
Base branch: main
Output branch: main
---

# t1709 — Document the clean-owner-file precondition in the `aitask-trail` skill

## Context

t1698 made `ait artifact create` / `ait attach` refuse to start when a path they
would stage has uncommitted changes. The refusal comes from
`.aitask-scripts/lib/txn_snapshot.sh:114`:

> `<label>: <path> has uncommitted changes — this operation stages that whole path, so its commit would absorb your edit. Commit it (./ait git commit -- <path>) or revert it, then re-run.`

The `aitask-trail` create flow (Step 2, item 4 of the template) runs
`aitask_artifact.sh create <owner_id> …`, which stages the owner task's file.
Task files are routinely dirty mid-session (`aitask_update.sh --batch` writes
without committing). Right now the skill sends this refusal to the generic
"Any other failure → surface and stop", which doesn't tell the user that the fix
is to commit their own in-flight edit. The website already documents this at
`website/content/docs/skills/aitask-trail.md:85`, and the skill should use the
same wording.

**Verified facts:**
- No "uncommitted" wording exists yet in the template, its goldens, or the
  `.agents` / `.opencode` stubs (grep rc=1).
- **No port tasks are needed** (task Goal item 4). `.agents/skills/aitask-trail/SKILL.md`
  and `.opencode/skills/aitask-trail/SKILL.md` are thin stubs: they run
  `aitask_skill_render.sh aitask-trail --agent codex|opencode`, which renders
  `.claude/skills/aitask-trail/SKILL.md.j2` (`aitask_skill_render.sh:7,36`).
  The edit reaches every agent from the single template.
- The rendered variant dirs (`.claude/skills/aitask-trail-*-/`,
  `.agents/skills/*-codex-/`, `.opencode/skills/*-/`) are gitignored
  (`.gitignore:58-60`). Re-rendering them is local only. The tracked outputs are
  the 3 goldens in `tests/golden/skills/aitask-trail/`.
- Overlap: t1243_13 (not yet landed; blocked on t1243_12) will edit the same
  template at :17 and regenerate the same goldens. This task lands first, so
  t1243_13 regenerates on top of it. No coordination action is needed.

## Implementation

1. **Pre-check that the goldens are currently green**, so that a later diff is
   attributable to this edit alone:
   `bash tests/test_skill_render_aitask_trail.sh`

2. **Edit `.claude/skills/aitask-trail/SKILL.md.j2`**, in Step 2's item 4 (≈ lines
   494-497, after the "handle … already exists" guidance and before
   "Any other failure → surface and stop."). Insert a second named failure case
   that mirrors the website sentence:

   ```markdown
   create flow. If it fails because a path "has uncommitted changes", tell
   the user to commit or revert **the path the error names** (the message
   also prints the commit command), then retry. Usually that path is the
   owner task's file: creating a trail writes it, so `ait artifact create`
   refuses while it has uncommitted changes. Create also checks the trail's
   manifest, though, so the error can name that path instead. Refreshing a
   trail only rewrites the manifest, so the refresh flow (Step 3) is
   unaffected by uncommitted owner-task edits; a dirty manifest still blocks
   it. Any other failure → surface and stop.
   ```

   This is plain prose with no Jinja, so all three profiles render it identically.

   **Why the guidance follows the named path** (review finding, verified):
   `aitask_artifact.sh:290-291` makes `create` call `txn_require_clean` on
   **both** `$task_file` and `$manifest_rel`. A tracked manifest that was
   deleted without being committed, e.g. when a handle is re-created under
   another owner, reaches the second check. `update` checks the manifest at
   `:404`. `tests/test_attach_txn_worktree_isolation.sh` tests both cases: P4a
   (update refuses a dirty manifest) and N1 (update succeeds with a dirty task
   file). So the recovery advice comes from the path in the error. "Owner task
   file" is named only as the usual case, and the refresh statement is limited
   to owner-task edits.

   The website sentence at `aitask-trail.md:85` stays as it is. Its "it is
   unaffected" refers to the owner-file refusal it just described, so it is not
   wrong, only narrower. The skill needs the fuller wording because an agent acts
   on the error text.

3. **Regenerate the goldens** with the canonical loop from
   `aidocs/framework/skill_authoring_conventions.md` ("Regenerate goldens after
   any `.md.j2` or closure edit"), for profiles `default fast remote` into
   `tests/golden/skills/aitask-trail/SKILL-<profile>-claude.md`. **Review the
   golden diff**: it should be exactly the inserted lines in each of the 3 files.

4. **Re-render the local variants** (gitignored, so this is a local freshness step only):
   `./.aitask-scripts/aitask_skill_render.sh aitask-trail --profile <p> --agent claude`
   for default/fast/remote.

5. **Commit** the template and the 3 goldens together, by path:
   `documentation: Document the clean-owner-file precondition in aitask-trail (t1709)`.

## Verification

- `bash tests/test_skill_render_aitask_trail.sh` → all PASS.
- `./.aitask-scripts/aitask_skill_verify.sh` → clean (required before
  committing a `.j2` change).
- `grep -n "has uncommitted changes" tests/golden/skills/aitask-trail/*.md` → one
  hit per golden, and the matched sentence matches the substring printed by
  `txn_snapshot.sh:114`.
- `git diff --stat` shows only the `.j2` plus the 3 goldens.

## Step 9 (Post-Implementation)

Current-branch mode, so there is no merge. Archive with
`./.aitask-scripts/aitask_archive.sh 1709`, then run `./ait git push`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
