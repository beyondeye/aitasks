# Real-repository disagreement: thinking_backend

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 269 | 0 |
| python | 317 | 0 |
| go | 0 | 0 |
| kotlin | 0 | 0 |
| typescript | 0 | unsupported |
| tsx | 0 | unsupported |
| javascript | 0 | unsupported |
| java | 0 | unsupported |
| rust | 0 | unsupported |
| swift | 0 | unsupported |

## Candidate vs baseline

| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |
|---|---|---|---|---|---|---|---|---|
| gotreesitter | bash | 269 | 0 | 0 | 0 / 0 | 0 | 0 | 20 |
| gotreesitter | python | 317 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 269 | 0 | 0 | 0 / 0 | 0 | 0 | 16 |
| tscgo | python | 317 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 269 | 0 | 0 | 0 / 0 | 0 | 0 | 16 |
| tswasm | python | 317 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- gotreesitter / bash / uncertain-gotreesitter-only:
  - `.aitask-scripts/aitask_attach.sh`
  - `.aitask-scripts/aitask_contribution_review.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
  - `.aitask-scripts/aitask_revert_analyze.sh`
  - `.aitask-scripts/aitask_review_commits.sh`
  - `.aitask-scripts/aitask_shadow_rejected.sh`
  - `.aitask-scripts/aitask_stats_legacy.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/github_release.sh`
  - `.aitask-scripts/lib/ledger_block.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `.aitask-scripts/lib/yaml_utils.sh`
  - `scripts/prod/migrate_legacy_db.sh`
  - `scripts/prod/mirror_legacy_media.sh`
  - `scripts/prod/place_media_mirror.sh`
  - `scripts/server/provision_hetzner.sh`
  - `scripts/server/setup_backup_remote.sh`
  - `scripts/tests/test_caddy_indirection.sh`
  - `scripts/tests/test_restore_rehearsal.sh`
- tscgo / bash / uncertain-tscgo-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `.aitask-scripts/aitask_shadow_rejected.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/github_release.sh`
  - `.aitask-scripts/lib/ledger_block.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `.aitask-scripts/lib/yaml_utils.sh`
  - `scripts/prod/migrate_legacy_db.sh`
  - `scripts/prod/mirror_legacy_media.sh`
  - `scripts/server/check_origin_certificate.sh`
  - `scripts/tests/test_caddy_indirection.sh`
  - `scripts/tests/test_restore_rehearsal.sh`
- tswasm / bash / uncertain-tswasm-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `.aitask-scripts/aitask_shadow_rejected.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/github_release.sh`
  - `.aitask-scripts/lib/ledger_block.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `.aitask-scripts/lib/yaml_utils.sh`
  - `scripts/prod/migrate_legacy_db.sh`
  - `scripts/prod/mirror_legacy_media.sh`
  - `scripts/server/check_origin_certificate.sh`
  - `scripts/tests/test_caddy_indirection.sh`
  - `scripts/tests/test_restore_rehearsal.sh`
