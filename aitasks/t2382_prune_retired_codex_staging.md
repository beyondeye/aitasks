---
priority: low
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [skills, codex, setup]
gates: [risk_evaluated]
anchor: 2365
followup_kind: risk_mitigation
created_at: 2026-11-27 10:54
updated_at: 2026-11-27 10:54
---

## Origin

Risk-mitigation ("after") follow-up for t2365, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — stale staging dirs (advisory: the exact manifest already stops them being installed)

- `aitasks/metadata/codex_skills/` is never pruned, so a prerender dir a later release retires would still be installed and committed by the sync · severity: low · → mitigation: prune_retired_codex_staging

## Goal

Make `install.sh`'s `install_codex_staging` mirror the release tarball's rendered dirs, so `aitasks/metadata/codex_skills/` does not keep accumulating retired prerender dirs. Today it copies each shipped dir on top of the staging and never removes one the release stopped shipping.

Since t2365 the delivery reads only the paths in the exact release manifest (`seed/headless_prerenders.txt`, stored as `aitasks/metadata/headless_prerenders.txt`), so a stale staging dir is no longer installed. This is now staging hygiene, plus less confusion for anyone reading the staging dir.

Constraints from t2365:
- Never remove a staging path the consumer changed. Staging lives on the data branch and is framework-owned, but follow the same dirty-baseline rules as `commit_installed_data_files`.
- Prune only rendered (`*-`) dirs absent from the tarball's `codex_skills/`, never the `aitask-*` wrapper dirs or other files.
- Consider applying the same rule to `opencode_skills/` together with t2381.
