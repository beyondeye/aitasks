---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [skills, claudecode, tmp_cleanup]
gates: [risk_evaluated]
created_at: 2026-11-13 00:43
updated_at: 2026-11-13 00:43
---

## Goal

Add a Claude Code skill in this repo, for local use only and **not shipped** in
releases for now. It diagnoses `/tmp` pressure and reclaims space safely when
the tmpfs fills up.

## Why

`/tmp` here is a tmpfs: 32G, `nr_inodes=1048576`, RAM/zram-backed. It ran out
twice in a few days, most likely on inodes. The `systemd-tmpfiles` policy is
`q /tmp 1777 root root 10d`, which is too slow for how fast things accumulate
(~25G and ~900k inodes in the 11 days since boot). Snapshot on 2026-11-13:

| source | bytes | inodes | why it stays |
|---|---|---|---|
| Claude Code scratchpads `/tmp/claude-<uid>/<project-slug>/<session-uuid>/` | 8.3G | ~600k (≈67% of cap) | Claude Code never deletes a session's scratchpad (166 session dirs). Worst: aitasks_go sessions that copied full aitasks checkouts (~815MB / 86k files each) |
| headless-Chrome `--user-data-dir` profiles (`geo-*`, `wb-smoke-*`) | ~13G | ~150k | animeless `smoke.js` never removes them (own task in animeless) |
| aitasks test leftovers (`tmp.*`, `roadmap_run_*`, `ait_*`…) | ~1.5G | ~60k | see t2290 |

Also: `/tmp/claude-<uid>/` has entries that are not session dirs
(`bash-edit-diff/`, `cache-break-state-*.json`) and one root-owned project dir.
Gotcha: project-slug dirs begin with `-`, so any `du`/`rm` over them needs `--`
or `./`. A plain `du -sh */` silently reports nothing.

## Required behaviour

1. **Report:** bytes *and* inodes (`df -h`, `df -i`) with the mount's caps,
   grouped by source/prefix. Group by **inode count** as well as size, because
   inodes are the usual binding limit. Include zram/swap usage, since tmpfs pages
   take up RAM.
2. **Liveness:** never propose deleting
   - a Claude session dir whose session is still running. Work out how to map
     running `claude` processes to session UUIDs, and fall back to a recent-mtime
     window when that isn't possible. Its own session included.
   - a Chrome profile still in use by a running browser (`--user-data-dir=` in
     the process list)
   - anything not owned by the user, or anything open by a process (`/proc/*/fd`)
3. **Delete only after explicit confirmation**, per category, showing the
   expected bytes and inodes freed. Use `find … -user "$USER" … -exec rm -rf {} +`
   with `--`-safe paths. Afterwards, re-measure and report what was actually
   freed.
4. **Prevention advice** (printed, never applied automatically): a
   `/etc/tmpfiles.d/tmp.conf` override with a shorter age, and pointers to the
   per-repo leak tasks.

Keep the measuring and liveness logic in a helper script so it can be tested.
The skill reads the evidence and makes the judgement calls.

## Not distributed

`.github/workflows/release.yml` ("Build skills directory from .claude/skills")
copies **every** `.claude/skills/*/` into the release, and
`tests/test_release_tarball.sh` emulates that loop. So a plain skill directory
*will* ship. The plan needs to pick a no-ship mechanism, for example a
denylist/marker honoured by `release.yml` + `install.sh` with a tarball-test
assertion that the skill is absent. Also check the other skill enumerators
(`aitask_skill_verify.sh`, `aitask-audit-wrappers`, the codex/opencode
wrapper-parity checks, seed manifests) so a deliberately unported, local-only
skill doesn't trip them. Porting to other agents is explicitly **not** wanted
for now.
