---
priority: medium
effort: high
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

`addresses: goal-achievement — the compare-and-commit guard detects and refuses
but does not exclude, so a concurrent edit in the target makes the push fail
rather than succeed`

From p1704's `## Risk`:

> The compare-and-commit guard detects and refuses but does not exclude: the
> destination's own writers take no lock, so a residual same-process window
> remains in which a concurrent edit is neither published nor overwritten but
> the push simply fails · severity: medium

## Goal

Upgrade the cross-repo push from **detect-and-refuse** to real **mutual
exclusion**, by making every metadata writer in a destination repo take a shared
`lib/stale_lock.sh` lock around write-and-commit.

t1704 closed the outcome that matters — the framework never publishes bytes it
did not write, and never silently discards an edit it found — but it cannot
*prevent* the collision, only detect it. The residual is a real user-visible
cost: a concurrent edit makes the push **fail** rather than succeed, and the
user has to notice and retry.

**Read p1704's "What this does not buy, stated plainly" section before
planning** — it states the reasoning this task exists to overturn, including why
a lock taken *only* by the push would be worse than none (it would serialize
push-against-push while leaving push-against-local-edit exactly as it is).

The writers that must all participate — a lock only some of them take is not a
mutex — at minimum:

- that repo's own Settings TUI (`settings/settings_app.py` — `save_codeagent`,
  `save_board`, `save_project_settings`, `save_profile`, `delete_profile`,
  `_handle_import`)
- board column CRUD (`board/aitask_board.py::save_metadata`,
  `aitask_board_column.sh`)
- the chatlink wizard (`chatlink/wizard.py::_do_save`)
- `ait setup`'s populate-missing / backfill passes
- `cross_repo_settings.py::apply_push` itself

Derive that list from `tests/test_metadata_writer_inventory.py`'s `WIRED` set
rather than from this bullet, which will drift.

## Hard parts (name them in the plan)

- **The lock lifecycle straddles a Python/shell boundary.** The write happens in
  Python; the commit happens in a shell helper. The lock must span both, and
  must survive a killed process — `lib/stale_lock.sh` already has the fail-safe
  owner-token model, so reuse it rather than inventing a second.
- **It is a lock in ANOTHER repo**, taken by a session that repo does not know
  about. Decide what a stale lock there means and who may break it.
- **It is framework-wide**, so it is a behaviour change for every metadata
  writer, not just the push. Every one of them is a TUI event handler, so a
  blocking acquisition on the UI thread is not acceptable — measure the
  availability, do not assume it.
- **Do not remove the compare-and-commit guard.** A mutex makes the race rare,
  not impossible (an unlocked writer, a broken lock, a repo mid-upgrade), and
  the guard is what keeps the failure fail-safe. It stays as defence in depth.

## Verification

- two concurrent pushes into the same destination serialize rather than one
  refusing
- a push and a local Settings-TUI save in the destination serialize
- a killed lock holder does not wedge the destination permanently
- the existing t1704 race tests still pass unchanged — the guard is still there
- negative control: with the lock removed, the concurrent cases return to
  `commit_raced`
