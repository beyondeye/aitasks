---
priority: medium
effort: low
depends: [t1912_5]
issue_type: documentation
status: Ready
labels: [verifiedstats, models]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-11-12 19:43
updated_at: 2026-11-12 19:43
---

## Context

Child 6 of t1912. Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. Depends on
t1912_1-5. After those land, the code-agent usage/verified counters live on
the orphan branch `aitask-stats`, one blob per agent: `<agent>.json` plus the
`migrations/<agent>.json` marker. They no longer live in
`aitasks/metadata/models_<agent>.json`.

What the docs need to say:
- **Readers** read `refs/heads/aitask-stats` via
  `lib/model_stats_store.py`.
- **Refresh** happens on `ait sync` and `pick --sync`, on every stats write,
  and on `aitask_model_stats.py refresh`. TUIs never fetch.
- **`verified`** stays in `models_*.json` as a static prior.
- **Migration** runs from `ait setup` / `ait upgrade`.
- **Config export** no longer carries stats.

## Pages to update (current-state prose only)

Follow `aidocs/framework/documentation_conventions.md` and
`aitasks/metadata/doc_update_guide.md`.

- `website/content/docs/tuis/settings/reference.md` (~L204-258): schema and
  bucket rules. Describe where counters live now; the bucket rules are
  unchanged.
- `website/content/docs/skills/verified-scores.md` (~L43, L60-66)
- `website/content/docs/skills/aitask-add-model.md` (~L37, L86)
- `website/content/docs/installation/updating-model-lists.md` (~L8-12, L59)
- `website/content/docs/commands/codeagent.md` (~L240-262): the
  `list-models` example is outdated; refresh it.
- `aidocs/framework/model_reference_locations.md` (~L22, L199-200, L325)
- `aidocs/framework/adding_a_new_codeagent.md` (~L315-318, L343-356, L422).
  A new agent's counters need no registry keys.
- If t1912_1 added a store section to `aidocs/framework/task_relations.md`
  or a new aidoc, cross-link it. Otherwise consider a short
  `aidocs/framework/model_stats_store.md` covering the layout, refresh
  routes, marker rule and migration protocol, for future maintainers.

## Verification

- `cd website && hugo build --gc --minify` passes.
- `python3 check_links.py --build` passes (mandatory after editing
  `website/content`).
- Offer `python3 check_link_relevance.py` if links were added or retargeted.

Step 9 (Post-Implementation) applies.
