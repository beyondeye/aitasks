---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [geminicli]
children_to_implement: [t812_2, t812_3, t812_4, t812_5]
created_at: 2026-05-20 08:01
updated_at: 2026-05-27 14:55
boardidx: 20
---

google is phasing out geminicli, and substituting it with antigravitycli that is different product: need to clarifiy (integrated with antigravity2.0): in any case geminicli support should be completely removed, and evaluate if to add support for antigravity cli or not. also remove all references to geminicli from documentation. this is complex task that need to be split in child tasks
for more information on antigravitycli and how to migrate from geminicli to antigravitycli, see https://antigravity.google/docs/gcli-migration. see also https://antigravity.google/docs/cli-features.
and also https://antigravity.google/docs/cli-using
I have generated also aidocs/geminicli_to_agy.md with more detailed guidance on how to migrate from geminicli to antigravitycli. so basically the scope of this task is to migrate current support for geminicli in aitasks framework to support instead for agy
