---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: [documentation]
created_at: 2026-06-02 16:57
updated_at: 2026-06-02 16:57
boardidx: 80
boardcol: now
---

## Context

Spun out of t914 (command-reference docs audit). `ait migrate-archives` converts
legacy `tar.gz` archives to `tar.zst` and rebuckets legacy archives — a one-time
past concern (archive-format migration) that may no longer be relevant to current
end users. t914 deliberately did NOT document it, pending this evaluation.

## Goal

Decide what to do with `ait migrate-archives` before deciding whether/how to
document it:

- **Keep** — still useful for users upgrading from old archive layouts → then
  add a brief reference entry to the command index.
- **Hide** — keep the script but drop it from the user-facing command list /
  `ait help` (internal/maintenance-only).
- **Remove** — if the legacy `tar.gz` format is no longer in the wild.

Investigate: when was the `tar.gz` → `tar.zst` migration introduced, whether any
supported install path still produces `tar.gz` archives, and whether
`aitask_zip_old.sh`'s legacy fallback (`old.tar.gz`) still needs a migration
command. Record the decision and, if "keep", document accordingly.

## Reference

- `ait` dispatcher: `migrate-archives` → `.aitask-scripts/aitask_migrate_archives.sh`
- `aitask_zip_old.sh` legacy fallback handling (`old.tar.gz` / `old.tar.zst`)
