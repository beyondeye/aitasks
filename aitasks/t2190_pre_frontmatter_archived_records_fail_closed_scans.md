---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [sitrep]
gates: [risk_evaluated]
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-03 23:18
updated_at: 2026-11-03 23:18
---

## Origin

Spawned from t2175_3 during Step 8b review.

## Upstream defect

- `aitasks/archived/_b0/old0.tar.zst` (t20, t21, t22) — pre-frontmatter archived task records that `archive_iter.iter_archived_frontmatter(errors=…)` reports as unparseable, so any fail-closed archive scan in this repo reports itself incomplete

## Diagnostic context

The sitrep refresh's fold scan (`.aitask-scripts/lib/sitrep_refresh.py`, `TaskIndex._build_folds`) reads every task's authoritative record and treats an unparseable task record as a scan error, so that a deleted folded task is never declared done from an incomplete scan. On this repository the scan failed closed every time on three records inside `_b0/old0.tar.zst`:

- `t20_skill_creating_aitask.md` — plain prose, no frontmatter at all (it contains a later `---` markdown rule);
- `t21_rewrite_aitask_create_as_script.md`, `t22_task_attributes_in_task_create.md` — the pre-YAML inline header `--- effort:med pri:med` on line 1, then a closing `---` further down.

t2175_3 resolved its own case with a narrow, user-approved exemption: ARCHIVED records in exactly those two shapes declare no fold relationships (decided by `task_yaml.FRONTMATTER_RE` = `\A---\n`); the tasks themselves still read as unknown. Any OTHER consumer that scans the archive with `errors=` enabled (for example `archive_iter.iter_archived_frontmatter`, `parse_archived_frontmatter`) still reports these three as parse failures — verify which consumers are affected before choosing a fix.

## Suggested fix

Either give t20–t22 valid YAML frontmatter inside the bundle (a one-time data migration of `_b0/old0.tar.zst`, which needs the archive tooling), or teach `archive_iter.parse_archived_frontmatter` to recognise the two pre-frontmatter shapes as "no metadata" rather than a failure — then t2175_3's local exemption can be dropped in favour of the shared rule.
