---
priority: low
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [task_relations]
anchor: 1981
followup_kind: review_finding
created_at: 2026-11-09 17:50
updated_at: 2026-11-09 17:50
---

## Origin
Spawned from t2254 during Step 8 review (finding marked "follow-up", performance, low).

## Finding
`.aitask-scripts/aitask_archive.sh` `parent_archive_decision` (added by t2254) reads bundled sibling records one entry at a time: for each matching member it calls `_extract_from_archive`, and its `_archive_extract_file` callee reopens and fully decompresses the bundle on every call, on top of the initial `_archive_list` listing. A bundle with many dropped siblings is therefore decompressed 1 + N times before the helper can certify `NONE_LANDED`. The stability recheck t2254 added (up to 3 attempts) multiplies that, and its `cksum` fingerprints read each candidate bundle twice per attempt (compressed bytes only, so cheap).

The loose-record path is unaffected, and the code runs only on a `--superseded` / `--obsolete` archive of a parent's last pending child.

## Suggested approach
Read the relevant members in one archive pass per bundle. For example, `_archive_extract_all` the bundle into one tagged temp dir (or stream-extract only the `t<P>/t<P>_*` members), then check every extracted record with `archived_file_landed`. Keep these t2254 contracts unchanged:
- LANDED wins on the first landed record.
- A listing or extraction failure records an UNVERIFIED reason.
- The before/after fingerprint stability loop still brackets the whole scan.
- Extraction dirs stay tagged so the owning shell's EXIT sweep removes them.

## Verification
`bash tests/test_archive_obsolete.sh` stays green: the bundle cases (all-dropped `.tar.zst`, landed `.tar.gz`, unreadable, unpack handoff, churn). Add a case that counts decompressions, e.g. a `zstd` wrapper on PATH that logs invocations, and show it drops from 1+N to 1 per bundle per attempt.
