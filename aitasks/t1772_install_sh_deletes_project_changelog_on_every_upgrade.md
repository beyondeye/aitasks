---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [install_scripts, data_integrity, auto-update]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-09 19:32
updated_at: 2026-09-09 19:34
---

`install.sh` **deletes the installed project's root `CHANGELOG.md` on every install
and every upgrade**, and before deleting it, overwrites its contents with the
framework's own changelog. The file is tracked in the target project, so the loss
shows up as an unstaged deletion in `git status` and silently blocks anything that
requires a clean tree.

This is the framework destroying a file its **own** tooling creates: the
`aitask-changelog` skill and `.aitask-scripts/aitask_changelog.sh` read and write the
project-root `CHANGELOG.md` (`aitask_changelog.sh:93,96`;
`.claude/skills/aitask-changelog/SKILL.md:147-181`).

## Root cause — two lines in `main()`, both in the common install path

`install.sh:1359` and `:1362` (v0.35.0):

```bash
info "Extracting to $INSTALL_DIR..."
tar -xzf "$tarball_path" -C "$INSTALL_DIR"          # :1359

# Remove CHANGELOG.md from project (only in tarball for upgrade changelog display)
rm -f "$INSTALL_DIR/CHANGELOG.md"                   # :1362
# Clean up legacy VERSION at root (moved to .aitask-scripts/VERSION in v0.3.0+)
rm -f "$INSTALL_DIR/VERSION"                        # :1364
```

- `INSTALL_DIR` is the **target project root** (`install.sh:9,66,89`); `ait upgrade`
  passes it explicitly (`aitask_upgrade.sh:152` runs
  `install.sh --force --dir "$AIT_DIR"`).
- `CHANGELOG.md` is **tracked in this repo** (`git ls-files CHANGELOG.md`), so it is
  in every release tarball at the tarball root. It ships there deliberately, so
  `show_upgrade_changelog` can display the framework changelog before upgrading
  (`install.sh:1003-1045`).
- Therefore `tar -xzf … -C "$INSTALL_DIR"` extracts the framework's `CHANGELOG.md`
  **over the project's own**, and `rm -f` then removes the result.

**These are two independent losses, and the second is not the worse one.** Even if
`:1362` were simply deleted, `:1359` would still replace a project's changelog with
the framework's — silently wrong content rather than an obvious absence. Any fix has
to address the extraction, not only the cleanup.

The comment on `:1361` is accurate about the *framework's* file and wrong about the
*path*: "only in tarball for upgrade changelog display" describes why the tarball
carries it, but the path being removed is the project's, which the installer never
owned.

**`:1364` is the same class** and should be settled in the same change: a project
that keeps a root `VERSION` file loses it too. That one may well be acceptable
(the comment calls it a legacy aitasks artefact) — but it is currently unconditional
and undocumented, so it deserves an explicit decision rather than inheritance.

## Reproduction

1. In any project using aitasks, create a root `CHANGELOG.md` with project content
   (or let the `aitask-changelog` skill generate one).
2. Commit it.
3. Run `ait upgrade` (or `ait upgrade <version>`).
4. `git status` reports ` D CHANGELOG.md` — deleted, unstaged.

## Observed

Hit on 2026-09-09 in a downstream project (`thinking_app`) immediately after
upgrading to **v0.35.0**. The project's `CHANGELOG.md` — 262 lines / 29 KB, tracked,
maintained by the `aitask-changelog` skill across releases v1.2.x — was gone from the
working tree. It surfaced only because the **merge broker refused to merge into a
dirty tree** (`DIRTY_TREE:1`), which blocked an unrelated task's Step-9 merge until a
human worked out where the deletion came from. The user's words: *"i would like to
understand who is constantly deleting the changelog"* — "constantly" because it
recurs on every upgrade.

Recovered with `git checkout -- CHANGELOG.md`; nothing was permanently lost **because
it happened to be committed**. A project that had not yet committed its changelog, or
that ran `git add -A` while the framework's copy was sitting there, would have lost
content or committed the wrong file.

## Suggested directions (not prescriptive)

Any of these fixes the extraction half; the choice is the implementer's:

- extract with `tar --exclude=CHANGELOG.md` (and decide the same for `VERSION`);
- extract to a temp dir and copy only framework-owned paths into `INSTALL_DIR`,
  which also removes the need for post-hoc `rm -f` cleanup of packaging leftovers;
- save the project's `CHANGELOG.md` before extraction and restore it after, deleting
  only when the project had none;
- keep the removal but make it conditional: remove only when the file is
  byte-identical to the tarball's copy, so a project's own changelog is never a
  casualty.

Note `show_upgrade_changelog` (`:1003-1045`) already extracts `CHANGELOG.md` from the
tarball into its **own temp dir** — that is the pattern the main extraction is
missing, and reusing it would make the root-level copy unnecessary in `INSTALL_DIR`
at all.

## Acceptance criteria

- A project with a committed root `CHANGELOG.md` containing project-specific content
  still has it, **byte-identical**, after `ait upgrade` and after a fresh
  `install.sh --force` — verified by comparing checksums before and after, not by
  eyeballing that a file exists.
- The framework's own changelog is still displayed by `show_upgrade_changelog` during
  an upgrade (do not fix this by dropping `CHANGELOG.md` from the tarball without
  re-routing that display).
- An explicit, documented decision is recorded for `rm -f "$INSTALL_DIR/VERSION"` —
  either the same protection, or a comment stating why an unconditional removal is
  correct there.
- A regression test covers it: seed a fixture project with a root `CHANGELOG.md` of
  known content, run the installer against it, assert the content survives. The test
  must **fail** against the current code — a test that passes before the fix proves
  nothing.

## Related

- **t1620** touches the same `install.sh` cleanup region
  (`rm -rf "$INSTALL_DIR/seed"`, `install.sh:1335`) but is a different concern (seed
  resolution fallback for installed projects). Worth reading together — both are
  cases of the installer removing things from a project root it does not own — but
  neither subsumes the other.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T07:51:17Z status=pass attempt=1 type=human
