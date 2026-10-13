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
| javascript | 0 | unsupported |
| java | 0 | unsupported |
| rust | 0 | unsupported |
| swift | 0 | unsupported |

## Candidate vs baseline

| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |
|---|---|---|---|---|---|---|---|---|
| pytokenize | python | 317 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| shfmt | bash | 269 | 0 | 0 | 1 / 1 | 0 | 0 | 2 |

## Paths per disagreement kind

- shfmt / bash / comment-class-differs:
  - `scripts/tests/test_deploy.sh`
- shfmt / bash / uncertain-shfmt-only:
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
