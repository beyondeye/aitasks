---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [git, task_metadata, robustness]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-04 16:56
updated_at: 2026-09-04 16:56
---

## Origin

Risk-mitigation ("after") follow-up for t1704, created at Step 8d after implementation landed.

## Risk addressed

`addresses: goal-achievement — an un-upgraded destination is refused with
dest_commit_unavailable and reads as a broken push`

From p1704's `## Risk`:

> The seam runs the **destination's** copy of `aitask_metadata_commit.sh`
> (`commit_command(root=…)`), so every sibling repo not yet upgraded past t1677
> is refused with `dest_commit_unavailable` — fail-closed and correct, but
> indistinguishable to a user from "the push broke" · severity: medium

## Goal

Name the destination's installed framework version in the
`dest_commit_unavailable` result line, so a refusal reads as "that repo is
behind" rather than "the push is broken".

**Partly landed already — check before starting.** t1704 shipped the second
half: the result line already says "its framework copy cannot commit metadata
(update it from the Versions tab)", and it deliberately suppresses the raw
diagnostic (a `[Errno 2] No such file or directory` string would read as a
crash). What is still missing is the **version**: the line does not say which
version that repo has, nor which one it needs.

Work to do:

- Resolve the destination's installed framework version. The syncer's Versions
  tab already does this for every discovered repo — reuse that seam rather than
  shelling a second probe per destination, and note that `apply_push` runs in a
  worker thread with no session object, so the version may need to be threaded
  in rather than looked up there.
- Distinguish the two shapes that both land in `dest_commit_unavailable` today:
  the helper is **absent** (predates t1677), and the helper **exists but is too
  old** to know `--preflight` (predates t1704). They want different sentences —
  the second is the one a user is most likely to hit as t1704 rolls out.
- Keep the raw diagnostic in `ApplyOutcome.detail` for tests and logs, and keep
  it out of the rendered line.
  `tests/test_cross_repo_push_commit.py::ResultLineRenderingTests::test_a_version_skew_refusal_does_not_leak_a_raw_exception`
  pins that split; extend it rather than relaxing it.

## Verification

- a destination with no `aitask_metadata_commit.sh` reports its version and says
  what it needs
- a destination whose helper predates `--preflight` gets a *different*, equally
  specific line (fixture exists:
  `test_helper_too_old_to_know_preflight_is_refused`)
- neither line contains a Python exception string
- negative control: each assertion fails against today's single generic sentence
