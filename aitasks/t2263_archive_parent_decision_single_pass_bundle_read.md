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
Spawned from t2254 during Step 8 review: two findings, both marked "follow-up", performance, low.

## Findings
The code runs only on a `--superseded` / `--obsolete` archive of a parent's last pending child. Within that run, both findings apply to `.aitask-scripts/aitask_archive.sh` `parent_archive_decision` (added by t2254).

1. **Per-entry decompression on the bundle path.** The helper reads bundled sibling records one entry at a time. For each matching member it calls `_extract_from_archive`, and the `_archive_extract_file` callee reopens and fully decompresses the bundle on every call, on top of the initial `_archive_list` listing. A bundle with many dropped siblings is therefore decompressed 1 + N times before the helper can certify `NONE_LANDED`. The stability recheck (up to 3 attempts) multiplies that.

2. **Whole-bundle checksums on the loose-positive path.** The loose-record path is **not** unaffected (an earlier version of this task said it was). The `before` fingerprint (`_child_evidence_fingerprint`) runs at the top of every attempt, **before** the loose scan, and `cksum`s every existing candidate bundle: the numbered bundle, its `.tar.gz` twin, and the legacy `old.tar.zst` / `old.tar.gz`. When a loose completed sibling immediately proves `LANDED`, those whole-bundle reads were wasted.
   - Confirmed in review with an isolated probe: one loose completed sibling plus an unrelated legacy bundle. Both files were checksummed before the helper returned `LANDED|t60_1`.
   - The legacy `old.tar.*` can be large, and an unrelated one is read even though it holds nothing for this parent.

## Suggested approach
- **Positive loose evidence before any bundle hashing.** Run a loose scan first and return `LANDED` on a loose completed sibling with no fingerprint at all; positive evidence never needs a stable view. Take the fingerprints only once the loose pass found no landed record. They must still bracket a *full* re-scan (loose + bundles) before a negative verdict, because the unpack handoff t2254 guards against moves a record into the loose directory mid-scan. Alternatively, make the fingerprint lazy, hashing loose records first and bundles only when the bundle phase is reached, as long as it still covers every source the negative verdict relies on.
- **Single pass per bundle.** For example, run `_archive_extract_all` on the bundle into one tagged temp dir (or stream-extract only the `t<P>/t<P>_*` members), then check every extracted record with `archived_file_landed`.
- Keep these t2254 contracts unchanged:
  - LANDED wins on the first landed record.
  - A listing or extraction failure records an UNVERIFIED reason.
  - `NONE_LANDED` is certified only after a scan bracketed by matching before/after fingerprints of every evidence source, with the bounded retry and the `kept changing` UNVERIFIED exit.
  - Extraction dirs stay tagged so the owning shell's EXIT sweep removes them.
  - The `AIT_ARCHIVE_PARENT_SCAN_HOOK` seam still runs between the loose and bundle scans.

## Verification
- `bash tests/test_archive_obsolete.sh` stays green: the bundle cases (all-dropped `.tar.zst`, landed `.tar.gz`, unreadable), the unpack handoff, and the churn case. Re-run t2254's mutant c (stability check forced true): it must still fail exactly the handoff and churn cases.
- Count reads with wrappers on `PATH` that log their invocations, e.g. `zstd` / `tar` / `cksum`:
  - with a loose completed sibling plus an unrelated legacy bundle, the helper performs **zero** bundle reads (no `cksum`, `zstd` or `tar` on the bundle);
  - on the bundle path, decompressions drop from 1 + N to 1 per bundle per attempt.
