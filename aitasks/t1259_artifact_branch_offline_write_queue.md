---
priority: low
effort: medium
depends: [1231]
issue_type: enhancement
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-26 22:59
updated_at: 2026-07-26 23:00
boardidx: 44032
---

## Origin

Risk-mitigation ("after") follow-up for t1231, created at decomposition time.
t1231 was split into children, so its Step 8d never runs — the mitigation is
created here instead, with `depends: [1231]` preserving the "after" ordering.

## Risk addressed

Goal-achievement risk (severity: medium) from `p1231`:

> Push-gated publish (R1) makes a reachable remote a hard requirement for
> `gitbranch` writes, so an offline user cannot create artifacts on this backend.

t1231_1's rule **R1** makes `put` return success only after a successful push:

> A push that fails or is lease-rejected does not return success — a lease
> rejection re-enters the CAS loop; exhaustion or a hard failure `die`s.

That rule is correct and must not be weakened: the next step of the artifact
transaction commits a manifest on `aitask-data`, so a locally-only blob would
publish a handle a second clone can resolve but cannot `get`. The cost is that
`ait artifact create --backend gitbranch` simply **fails** on a plane, on a train,
or behind a flaky VPN — where the `local` and `dir` backends keep working.

## Goal

Let a `gitbranch` write commit locally while offline and defer publication,
without ever publishing a manifest that points at unreachable bytes.

Design questions to settle in planning (this is genuinely a design task, not just
an implementation):

1. **Where the pending state lives.** Candidates: a marker on the local
   `refs/heads/<branch>` ahead of `refs/remotes/origin/<branch>` (derivable, no
   new ledger), or an explicit entry beside
   `artifacts/gitbranch_store.json`. Prefer the derivable option — an unpushed
   local ref *is* the pending state.
2. **What the manifest says meanwhile.** The manifest must not claim a
   published artifact. Either the whole artifact transaction defers (nothing is
   committed on `aitask-data` until the push lands), or the manifest carries an
   explicit unpublished marker that resolution on another clone reads as "not
   yet available here" rather than as corruption.
3. **The re-push path.** A verb (`ait artifact push-store`, or folding into
   `ait sync` / the syncer TUI) that publishes everything pending and reports
   what was published. The syncer already has a ref registry
   (`lib/desync_state.py:144-156`, `syncer/syncer_app.py:83`) whose
   `missing_worktree` status shows how an optional ref degrades gracefully.
4. **Visibility.** An unpushed store must be *loud* — a silent local-only store
   is exactly the failure R1 exists to prevent. Surface it in `ait artifact ls`
   and/or the syncer row.

## Verification

- Offline (`origin` unreachable): `ait artifact create --backend gitbranch`
  succeeds, and the artifact is readable **locally**.
- A second clone at that moment does **not** see a manifest promising bytes it
  cannot fetch — assert the exact behavior chosen in design (either no manifest,
  or an explicitly-unpublished one that fails with an actionable message rather
  than a corruption error).
- After connectivity returns, the re-push path publishes the pending blobs and
  the second clone resolves them.
- Negative control: with the feature disabled/absent, the same offline create
  still fails closed (R1 is not weakened by default).
