---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: chore
status: Done
labels: [applink]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-25 09:35
updated_at: 2026-06-25 10:01
completed_at: 2026-06-25 10:01
---

Organize the open AppLink task backlog so each task's purpose is legible from its
labels and there is a recorded, agreed implementation order — especially which
tasks are best done **before** decomposing/starting the t1061 outside-network
connectivity roadmap.

This is an organizational / triage task (no AppLink feature code). Deliverables:
(1) a consistent label scheme applied across all AppLink tasks, and (2) a
sequencing decision recorded on t1061 (and/or here) as the source of truth.

## Background: state at triage time (2026-06-25)

- **Hard gate t985 (AppLink security review & hardening) is DONE / archived**
  (commits `f4af00339` archive, `2b5554d1a` impl). t1061 declares `depends:[985]`,
  so the umbrella is **unblocked** for its public-exposure phases. Record this —
  the t1061 body still reads as if t985 is pending ("Ready/high").
- t1044 (empty-subscribe pane roster) is also DONE / archived — the baseline
  t1045 builds on.

## Problem 1 — labels are inconsistent and carry no sub-area signal

The same feature is split across **two labels**, and one task has neither:

- `applink`: t1045, t1054, t1055, t1056, t1057, t1058, t1061
- `ait_bridge`: t1007, t1011, t1066, t1067, t1068
- neither (`verification, bug`): t1002

Decide a single canonical top-level label (recommend `applink`; `ait_bridge`
appears to be a legacy synonym — confirm before collapsing) and add **sub-area**
labels so each task says what it improves. Proposed sub-areas:

| Sub-area | Candidate label | Tasks |
|---|---|---|
| Content/data plane (streaming correctness + efficiency) | `applink_dataplane` | t1007, t1045, t1054, t1055, t1056, t1057, t1058 |
| Security lifecycle (t985 anchor-985 follow-ups) | `applink_security` | t1066, t1067, t1068 |
| Command/control plane (verbs, launch policy) | `applink_control` | t1011 |
| Connectivity / remote roadmap | `applink_connectivity` | t1061 |
| Hygiene bug | (keep `bug`) | t1002 |

Adding any NEW label requires appending it to `aitasks/metadata/labels.txt`
(canonical label list). Decide whether to introduce sub-labels at all vs. rely
on the existing `anchor` grouping (t1066/t1067/t1068 already share `anchor: 985`;
t1045 has `anchor: 1044`). Either way, fix the `applink`/`ait_bridge` split and
give t1002 an AppLink label.

## NOT part of this backlog

- **t1065** (brainstorm native artifact storage/share model) is NOT an AppLink
  task — it explicitly decides "Do NOT couple artifact sharing to AppLink" and
  names AppLink only to reject it. Exclude from relabeling.

## Problem 2 — implementation order, especially relative to t1061

t1061 is an **umbrella roadmap** (`xdeprepo: aitasks_mobile`, decompose-later,
not implement-as-one). Its own text: the data-plane tasks "make remote links
*usable* but aren't strict blockers." Since t1061 is about remote/cellular
connectivity, the data-plane correctness + bandwidth tasks are exactly what make
a remote link worth having. Recommended sequence (record on t1061):

### Tier 0 — do before t1061 (correct + usable remote link), cheap-first
1. **t1054** (HIGH, bug) — viewport-only keyframe rows. Server-side root cause of
   a real mobile render bug; fixes the wire row-id scheme everything builds on.
   Do first.
2. **t1055** (bug, low effort) — `pause` flow-control verb. Server/phone currently
   disagree; cheap, isolated.
3. **t1007** (chore, low effort) — data-plane DoS / resource caps. Cheap; matters
   before any beyond-LAN exposure.
4. **t1045** (perf) — roster-vs-focused content split. The key cellular-bandwidth
   win (stream binary only for the focused pane).

### Tier 1 — strongly recommended, larger
5. **t1057** (feature, high) — history RPC scrollback (conceptually follows t1054:
   once live keyframes are viewport-only, scrollback is reached only via this RPC).
6. **t1056** (feature) — `viewport_hint` clipping (more bandwidth savings; paired
   with mobile t14_12, value lands once both ship).

### Tier 2 — pair with t1061's PUBLIC-EXPOSURE phases (Alt B / Phase 3-4), not the cheap Phase-2 tunnel
- **t1068** (request rate limit), **t1066** (cert rotation), **t1067** (bearer
  rotation). These become prerequisites only when exposing beyond a user-owned
  tunnel/mesh VPN; not needed for Phase-2 (Tailscale/cloudflared) which reuses the
  existing LAN trust model.

### Independent of t1061 (any time)
- **t1011** (workflow launch policy) — control plane, orthogonal to connectivity.
- **t1002** (shellcheck on `aitask_applink.sh`) — hygiene bug.
- **t1058** (standalone cursor frames, low priority) — polish; defer.

## Acceptance

- `applink`/`ait_bridge` split resolved to one scheme; t1002 carries an AppLink
  label; any new labels added to `aitasks/metadata/labels.txt`.
- Sequencing decision (the tiers above, adjusted as the user prefers) recorded as
  source-of-truth on t1061 (its "Dependencies & sequencing" section), including
  the "t985 DONE → unblocked" correction.
- Several tasks are cross-repo paired with `aitasks_mobile` (t1045↔#19,
  t1054↔t14_11, t1055/t1056/t1057/t1058 from the t14_11 audit). Per repo
  convention, if sequencing changes a paired task, mirror the note on the mobile
  side. No mobile code changes here.

## Reference

- `aitasks/t1061_applink_outside_network_connectivity_roadmap.md` (umbrella;
  §Dependencies & sequencing, §Suggested decomposition).
- `aidocs/applink/` (protocol.md, content_transport.md, security.md,
  wish_ssh_evaluation.md, implementation_status_2026-06-22.md).
- `aitasks/metadata/labels.txt` (canonical label list).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-25T06:54:49Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-25T06:54:51Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-25T07:00:47Z status=pass attempt=1 type=human
