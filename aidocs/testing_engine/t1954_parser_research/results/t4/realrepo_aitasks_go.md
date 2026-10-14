# Real-repository disagreement: aitasks_go

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Input: `aitasks_go@e0e3862be98a`, the walked checkout at that commit.

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 162 | 0 |
| python | 245 | 0 |
| go | 161 | 0 |
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
| chroma | bash | 162 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | python | 245 | 0 | 0 | 21 / 25 | 0 | 0 | 0 |
| chroma | go | 161 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| goscanner | go | 161 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | bash | 162 | 0 | 0 | 0 / 0 | 0 | 0 | 8 |
| gotreesitter | python | 245 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | go | 161 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | bash | 162 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | python | 245 | 0 | 0 | 21 / 25 | 0 | 0 | 0 |
| pygments | go | 161 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pytokenize | python | 245 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| shfmt | bash | 162 | 0 | 0 | 0 / 0 | 0 | 0 | 1 |
| textmate | bash | 162 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | python | 245 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | go | 161 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 162 | 0 | 0 | 0 / 0 | 0 | 0 | 4 |
| tscgo | python | 245 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | go | 161 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 162 | 0 | 0 | 0 / 0 | 0 | 0 | 4 |
| tswasm | python | 245 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | go | 161 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- chroma / python / comment-class-differs:
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/applink/pairing.py`
  - `.aitask-scripts/board/aitask_board.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/chatlink/config.py`
  - `.aitask-scripts/chatlink/relay.py`
  - `.aitask-scripts/chatlink/sessions_store.py`
  - `.aitask-scripts/lib/agent_marks.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/cross_repo_settings.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/gate_registry_sync.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/lib/trail_gather.py`
  - `.aitask-scripts/lib/work_report_gather.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
  - `.aitask-scripts/syncer/syncer_app.py`
  - `parity/theme_dump.py`
- gotreesitter / bash / uncertain-gotreesitter-only:
  - `.aitask-scripts/aitask_attach.sh`
  - `.aitask-scripts/aitask_contribution_review.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_revert_analyze.sh`
  - `.aitask-scripts/aitask_review_commits.sh`
  - `.aitask-scripts/aitask_stats_legacy.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/task_utils.sh`
- pygments / python / comment-class-differs:
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/applink/pairing.py`
  - `.aitask-scripts/board/aitask_board.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/chatlink/config.py`
  - `.aitask-scripts/chatlink/relay.py`
  - `.aitask-scripts/chatlink/sessions_store.py`
  - `.aitask-scripts/lib/agent_marks.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/cross_repo_settings.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/gate_registry_sync.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/lib/trail_gather.py`
  - `.aitask-scripts/lib/work_report_gather.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
  - `.aitask-scripts/syncer/syncer_app.py`
  - `parity/theme_dump.py`
- shfmt / bash / uncertain-shfmt-only:
  - `.aitask-scripts/aitask_fold_mark.sh`
- tscgo / bash / uncertain-tscgo-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/task_utils.sh`
- tswasm / bash / uncertain-tswasm-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/task_utils.sh`
