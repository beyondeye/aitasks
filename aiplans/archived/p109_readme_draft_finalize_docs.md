---
Task: t109_readme_draft_finalize_docs.md
Branch: main
Base branch: main
---

## Context

Task t108 introduced a draft/finalize workflow and atomic task ID counter to prevent duplicate task IDs when multiple PCs create tasks against the same repo. The README.md needs to be updated to document these behavioral changes across several commands and the new internal architecture.

## Plan — Update README.md

All changes are in a single file: `README.md`

### 1. Update `ait setup` section (~lines 179-186)

The current setup flow has 6 numbered steps. The actual `main()` in `aitask_setup.sh` runs in this order:
1. OS detection
2. CLI tools
3. Git repo setup
4. **Draft directory** — Creates `aitasks/new/` for local drafts and adds it to `.gitignore` (NEW)
5. **Task ID counter** — Initializes the `aitask-ids` counter branch on the remote for atomic task numbering; prevents duplicate IDs when multiple PCs create tasks (NEW)
6. Python venv
7. Global shim
8. Claude Code permissions
9. Version check

Update the numbered list to insert steps 4 and 5, renumber subsequent steps to match.

### 2. Update `ait create` Interactive mode (~lines 227-240)

The interactive mode now has a draft-first workflow. Update the numbered steps:

- **Insert new step 0 (before step 1):** If drafts exist in `aitasks/new/`, a draft management menu appears: select a draft to continue editing, finalize, or delete — or create a new task
- **Update step 11 text** to mention preview shows "Draft filename: draft_*_<name>.md" (since IDs aren't assigned yet)
- **Replace step 12 (Git commit)** with: Post-creation options: finalize now (claim real ID and commit), show draft, open in editor, or save as draft for later

### 3. Update `ait create` Batch mode section (~lines 242-274)

**Update examples** to show the draft workflow:
```bash
ait create --batch --name "fix_login_bug" --desc "Fix the login issue"    # Creates draft in aitasks/new/
ait create --batch --name "add_feature" --commit                          # Creates and finalizes immediately
ait create --batch --finalize draft_20260213_1423_fix_login.md            # Finalize a specific draft
ait create --batch --finalize-all                                         # Finalize all pending drafts
```

**Add new flags** to the options table:
| `--finalize FILE` | Finalize a specific draft from `aitasks/new/` (claim ID, move to `aitasks/`, commit) |
| `--finalize-all` | Finalize all pending drafts |

**Update `--commit` description** from "Auto-commit to git" to "Claim real ID and commit to git immediately (auto-finalize)"

**Update "Key features" bullets:**
- Replace "Auto-determines next task number from active, archived, and compressed (`old.tar.gz`) tasks" with draft/finalize description
- Add: Drafts use timestamp-based filenames, local-only
- Add: Child task IDs via local scan
- Add: Atomic counter fallback behavior

### 4. Update Usage Examples (~lines 154-169)

Update existing examples and add finalize example.

### 5. Update Development/Architecture section (~lines 862-874)

Add `aitasks/new/` to directory layout table and add Atomic Task ID Counter subsection.

### 6. Update Command Reference table row (~line 144)

### 7. Duplicate ID Detection note

## Verification

1. Read through the updated README to ensure consistent style
2. Verify all new flags match `aitask_create.sh --help` output
3. Check numbered steps are correctly renumbered
4. Verify setup flow order matches actual `main()` in `aitask_setup.sh`

## Final Implementation Notes
- **Actual work done:** All 7 planned sections implemented as described. README.md updated with 48 insertions, 12 deletions.
- **Deviations from plan:** None — all changes matched the plan exactly. Re-read all three scripts (aitask_claim_id.sh, aitask_create.sh, aitask_setup.sh) before implementation to verify current behavior after user flagged that there had been updates and bug fixes.
- **Issues encountered:** Initial plan was based on exploration agent summary; user correctly pointed out that the scripts had been updated since t108 and needed re-verification. The key difference found: `aitask_claim_id.sh` no longer has a silent fallback — it dies on failure in batch mode and requires explicit consent in interactive mode.
- **Key decisions:** Documented the fallback behavior precisely (interactive: warns + asks consent; batch: fails hard). Added duplicate ID detection note to the `ait create` key features rather than creating a separate section.
