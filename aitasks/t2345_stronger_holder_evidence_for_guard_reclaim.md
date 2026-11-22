---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tests, test_infrastructure, tmp_cleanup]
gates: [risk_evaluated]
anchor: 2290
followup_kind: risk_mitigation
created_at: 2026-11-22 11:43
updated_at: 2026-11-22 16:57
artifacts:
  - handle: art:trail-tmp-cleanup
    kind: implementation_trail
    name: /tmp cleanup — after killed-run reclaim
---

## Origin
Risk-mitigation ("after") follow-up for t2301, created at Step 8d after implementation landed.

## Risk addressed
Goal-achievement — reclaim practically inert on non-root systemd hosts under the strict uninspectable rule.

From t2301's `## Risk`: "Under the user-chosen strict rule for uninspectable processes, reclaim practically never fires on a non-root systemd dev host (`sd-pam`), so the "reclaim automatically" goal is realized mainly for root/CI runs. The user accepted this knowingly, and it is documented. · severity: medium"

## Goal
Research and prototype stronger evidence that would let a NON-ROOT host prove a
killed run's guard dir unused, without trusting process start time (the t2301
user decision: start time does not rule out later file access or a passed
descriptor). Candidates:
- per-run cgroup membership: run each guarded phase in its own
  `systemd-run --user --scope` (or a cgroup v2 subtree the user owns); a dir is
  provably unused when its scope's `cgroup.procs` is empty — this covers every
  descendant, even ones that left the process group or re-execed;
- a narrowly privileged inspector (a setuid/capability helper limited to
  reading cwd/fd/environ of processes) — weigh against its own attack surface.

Context from t2301 (archived plan `aiplans/archived/p2301_*.md`): the reaper's
ladder is in `tests/lib/tmpdir_guard.sh` (KILLED RUNS header). On this
development host a full holder scan finds ~440 of ~670 processes uninspectable
(other uids, non-dumpable), so every candidate is kept as
`holder-unverified:<n>`. Sockets are no longer part of the holder scan (t2301
round 6: a per-candidate `find -type s` instead of the host-wide net/unix
table), so process visibility is the remaining blocker. A design must keep
the "unknown is never rounded up to dead" rule and must not weaken any other
step of the ladder.
