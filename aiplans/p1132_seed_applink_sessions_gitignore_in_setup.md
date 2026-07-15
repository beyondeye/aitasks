---
Task: t1132_seed_applink_sessions_gitignore_in_setup.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Seed applink_sessions/ gitignore rule in `ait setup`

## Context

`aitask_setup.sh`'s `setup_data_branch` appends data-branch `.gitignore` blocks
for `aitasks/new/`, `userconfig.yaml`, `*.local.json`, `profiles/local/`, and —
since t1120_2 — `aitasks/metadata/chatlink_sessions/`. It never seeds
`aitasks/metadata/applink_sessions/`. That rule exists in **this** repo only as a
one-off manual commit (`9df76f759`, now `.aitask-data/.gitignore:14`). Any fresh
downstream project that bootstraps via `ait setup` and later pairs applink stores
its TLS cert/key + `sessions.json` (live bearer secrets) in an **unignored**
directory; a blanket `git add .` on the data branch (exactly what
`setup_data_branch` Step 4 does) would commit those secrets. The 0700 dir mode
does not protect against self-commits.

Fix: add one gitignore append block mirroring the chatlink one, plus a test.

## Changes

### 1. `.aitask-scripts/aitask_setup.sh` — add applink block in `setup_data_branch`

Insert immediately **after** the chatlink block (currently ends at line 1399,
before the `# --- Step 4: Commit and push ---` comment). Mirror the chatlink
block exactly, using the same guard idiom and the comment wording already present
in this repo's live gitignore:

```bash
    # Add applink_sessions/ to data branch .gitignore (per-PC secrets: TLS cert/key + bearer sessions)
    if ! grep -qxF "aitasks/metadata/applink_sessions/" "$data_gitignore" 2>/dev/null; then
        {
            echo ""
            echo "# applink runtime state (per-PC: TLS cert/key + active bearer sessions)"
            echo "aitasks/metadata/applink_sessions/"
        } >> "$data_gitignore"
    fi
```

`grep -qxF` makes it idempotent (no-op when the rule is already present — e.g. on
this repo). No existing behavior changes.

### 2. New test `tests/test_applink_setup_gitignore.sh`

Self-contained bash test (run individually, prints PASS/FAIL summary) with two
independent assertions:

- **Source guard (fresh-install regression):** assert `aitask_setup.sh` contains
  the applink append block — the guarded path `aitasks/metadata/applink_sessions/`
  under a `setup_data_branch` context. Fails if the block is ever removed/broken,
  which is the exact defect being fixed.
- **Behavioral check-ignore + negative control (independent ground truth):** parse
  the seeded ignore path out of the script (don't re-hardcode it), write it into a
  `.gitignore` in a fresh `git init` temp repo, then assert:
  - `git check-ignore` **matches** `aitasks/metadata/applink_sessions/tls_key.pem`
    and `aitasks/metadata/applink_sessions/sessions.json` (the secret files), and
  - **does NOT match** a sibling negative control such as
    `aitasks/metadata/labels.txt` (rule doesn't over-match).

This proves the rule the script seeds actually ignores the applink secrets and
nothing more — without depending on this repo's already-present manual rule.

## Verification

- `bash tests/test_applink_setup_gitignore.sh` → PASS.
- `bash tests/test_chatlink_config.sh` → still PASS (no regression to the adjacent block).
- `shellcheck .aitask-scripts/aitask_setup.sh` → clean.
- Manual: confirm the new block sits directly after the chatlink block and before
  the Step 4 commit sub-shell.

## Step 9 (Post-Implementation)

Standard: no separate branch (profile 'fast', current branch). Verify via the
tests above, then archive with `./.aitask-scripts/aitask_archive.sh 1132`.

## Risk

### Code-health risk: low
- None identified. Single idempotent append block mirroring the adjacent, proven
  chatlink block; guarded by `grep -qxF`; no change to any existing path or
  behavior; blast radius is one function + one new test file.

### Goal-achievement risk: low
- None identified. The change directly seeds the missing rule and the new test
  verifies both its presence in setup and its actual ignore behavior (with a
  negative control). Follows the established t1120_2 precedent; fully covers the
  task's stated requirement.

## Final Implementation Notes
- **Actual work done:** Added the applink `.gitignore` seeding block to
  `setup_data_branch` in `.aitask-scripts/aitask_setup.sh`, immediately after the
  chatlink block — same `grep -qxF` idempotency guard and `{ echo; echo; } >>`
  idiom, with the comment/path already present in this repo's live data-branch
  gitignore. Added `tests/test_applink_setup_gitignore.sh`: a source-guard
  assertion (block present in setup) plus a behavioral `git check-ignore` test on
  a fresh temp repo (matches `tls_key.pem` + `sessions.json`, negative control
  `labels.txt` not ignored).
- **Deviations from plan:** None.
- **Issues encountered:** None. The behavioral test parses the seeded ignore path
  out of the script rather than re-hardcoding it, so it stays honest to the
  source.
- **Key decisions:** Kept the test independent of this repo's already-present
  manual rule (commit `9df76f759`) by exercising a fresh git repo — the assertion
  proves the *seeding* behavior, not just this repo's current state.
- **Upstream defects identified:** None.
