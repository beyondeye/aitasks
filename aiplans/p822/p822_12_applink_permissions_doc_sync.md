---
Task: t822_12_applink_permissions_doc_sync.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_13_*.md, aitasks/t822/t822_14_*.md
Archived Sibling Plans: aiplans/archived/p822/p822_*_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Sync applink permission docs (t822_12)

## Context

`aidocs/applink/permissions.md` shipped (t822_1) as the **seed** verb-gating
table for the `ait applink` mobile bridge. Sibling t822_3 then produced the
**canonical** verb inventory in `aidocs/applink/monitor_port_design.md`
(§Command verb → applink protocol mapping), deliberately *recording* — not
silently fixing — the discrepancies between the two in its §Permission profile
cross-check. This task pays that debt down: bring permissions.md's gating table
into agreement with the canonical inventory, and confirm the shipped
`applink_profiles/*.yaml` match. Scope is **docs + metadata YAML only — no
listener code** (the listener is t822_7, already landed).

### What exploration found (changes the work vs. the task's expectations)

1. **The three profile YAMLs are already fully aligned.** t822_7 (listener) and
   t822_11 (modal handshakes) shipped `read_only.yaml`, `monitor_control.yaml`,
   and `full.yaml` with `allowed_verbs` that already equal the ✓-set for each
   band in the canonical table (incl. `forward_key`, `task_detail`,
   `pick_next_sibling`, `restart_task`, `subscribe`, `request_keyframe`,
   `focus`). **No YAML edits are needed** — only verification (AC step 2).
   So this task collapses to a **permissions.md-only edit**.

2. **The monitor command surface moved to `monitor_core.py`.** The t822_6
   extraction landed: `capture_all`, `send_enter`, `send_keys`,
   `switch_to_pane`, `cycle_compare_mode`, `kill_pane`, `kill_window`,
   `kill_agent_pane_smart`, `spawn_tui`, `TaskInfoCache`, and `_TEXTUAL_TO_TMUX`
   all now live in `.aitask-scripts/monitor/monitor_core.py`. The UI-bound action
   handlers (`_forward_key_to_tmux`, `action_cycle_compare_mode`,
   `action_pick_next_sibling`, `action_restart_task`) remain in `monitor_app.py`.
   Therefore **every** `tmux_monitor.py:NNN` / `monitor_shared.py:NNN` call-site
   citation in permissions.md is stale, not just the two the task names. Per the
   task's "prefer symbol names over bare line numbers" guidance, the new
   citations use `monitor_core.py (symbol)` / `monitor_app.py (symbol)` form —
   module + symbol, **no line numbers** (they drift, as just demonstrated).

## Files to modify

- `aidocs/applink/permissions.md` — the only file edited.
- `aitasks/metadata/applink_profiles/{read_only,monitor_control,full}.yaml` —
  **verify only** (already aligned); no edits expected.

## Source of truth

`aidocs/applink/monitor_port_design.md` §Command verb → applink protocol mapping
(canonical inventory) and §Permission profile cross-check (the discrepancy list
this task resolves). permissions.md is re-anchored as the *profile-band view* of
that canonical inventory.

## Edits to `aidocs/applink/permissions.md`

### 1. Overview re-anchor (line ~16)
Replace "this document seeds the verb table with the v1 baseline." — permissions.md
is no longer a seed. New wording: this document gives the **profile-band
assignment** for the canonical verb inventory authored in monitor_port_design.md
(§Command verb table), and is kept in sync with it. Keep the existing link to
monitor_port_design.md.

### 2. Verb gating table intro (line ~32)
Current text cites `tmux_monitor.py:585-720` and `monitor_app.py:1489`. Rewrite to:
- Drop the stale line ranges.
- State the command surface now lives in `monitor_core.py` (post-t822_6
  extraction), with UI-bound action handlers in `monitor_app.py`.
- Note the table is synced with monitor_port_design.md §Command verb table
  (the canonical inventory), which carries the full payload/modal detail.

### 3. Verb gating table (lines ~34-43) — sync to canonical
Rebuild the table so its verb set and gates exactly match the canonical table
(AC step 1: no orphans either direction). Final rows (gate bands shown
read_only / monitor_control / full):

| Verb | Call site (symbol) | r_o | m_c | full |
|------|--------------------|:--:|:--:|:--:|
| `snapshot` (server push) | `monitor_core.py` (`capture_all`) | ✓ | ✓ | ✓ |
| `subscribe` / `request_keyframe` (data-plane control) | content_transport.md §Refresh control | ✓ | ✓ | ✓ |
| `task_detail` | `monitor_core.py` (`TaskInfoCache._resolve`) | ✓ | ✓ | ✓ |
| `send_enter` | `monitor_core.py` (`send_enter`) | ✗ | ✓ | ✓ |
| `send_keys` | `monitor_core.py` (`send_keys`) | ✗ | ✓ | ✓ |
| `forward_key` | `monitor_app.py` (`_forward_key_to_tmux`, `_TEXTUAL_TO_TMUX` in `monitor_core.py`) | ✗ | ✓ | ✓ |
| `focus` (= `switch_to_pane`) | `monitor_core.py` (`switch_to_pane`) | ✗ | ✓ | ✓ |
| `cycle_compare_mode` | `monitor_core.py` (`cycle_compare_mode`; handler `monitor_app.py` `action_cycle_compare_mode`) | ✗ | ✓ | ✓ |
| `kill_pane` | `monitor_core.py` (`kill_agent_pane_smart`) | ✗ | ✗ | ✓ |
| `kill_window` | `monitor_core.py` (`kill_window`) | ✗ | ✗ | ✓ |
| `spawn_tui` | `monitor_core.py` (`spawn_tui`) | ✗ | ✗ | ✓ |
| `pick_next_sibling` | `monitor_app.py` (`action_pick_next_sibling`) | ✗ | ✗ | ✓ |
| `restart_task` | `monitor_app.py` (`action_restart_task`) | ✗ | ✗ | ✓ |

Changes vs. the seed table: **add** `subscribe`/`request_keyframe`, `task_detail`,
`forward_key`, `pick_next_sibling`, `restart_task`; **rename** `switch_to_pane` →
`focus` (= `switch_to_pane`) to match canonical; **move** `kill_pane`'s citation
from raw `kill_pane` to `kill_agent_pane_smart`; refresh all call-site citations
to `monitor_core.py`/`monitor_app.py` symbols.

### 4. Notes block (lines ~47-51)
- **Remove the `forward_key` "intentionally absent / send literal escape
  sequences in the interim" note** (line ~49) — the interim is over; `forward_key`
  is now a gated verb. Replace with a one-liner: `forward_key` folds the
  `_TEXTUAL_TO_TMUX` map (`monitor_core.py`) into one verb resolved server-side
  (mobile sends the abstract key name); see monitor_port_design.md note.
- **Update the "Modal-prompted operations" note** to name the destructive verbs
  that carry a modal handshake — `kill_pane`, `kill_window`, `restart_task`,
  `pick_next_sibling` — and point to monitor_port_design.md §Modal-dialog
  handshakes for the round-trip detail (do not duplicate the handshake table
  here; permissions.md stays gating-focused). Keep the "gating applies to the
  underlying verb, not the handshake" sentence.
- **Add a `pick_next_sibling` / `restart_task` mobile-execution-deferred note**:
  both are gated `full` but their mobile execution is still deferred
  (`NOT_IMPLEMENTED`) per monitor_port_design.md — keep that flag.
- **Add a `rename_session` desktop-only note** (not a table row): inventoried in
  monitor_port_design.md §Modal-dialog handshakes, desktop-only in v1, not yet
  gated — add a table row only when it gains a mobile implementation. (Matches
  the task's "add a row only if implemented; otherwise keep desktop-only note.")
- Keep the existing `PERMISSION_DENIED` note.

### Design choice: no "Modal?" column in permissions.md
The canonical table has a Modal? column; permissions.md will **not** duplicate it.
permissions.md's job is the profile-band mapping; payload/modal detail is the
canonical doc's job. Modal nature is covered by the prose note (point 4). This
keeps the two docs' purposes distinct and avoids drift (derive/point, don't copy).

## Scope decision (explicit — no silent AC deviation)

- **YAMLs: verify-only, no edit.** AC step 2 is satisfied by the existing files;
  I will show the verification (each YAML's `allowed_verbs` == its column's ✓-set)
  rather than rewrite them. Editing them would be a no-op churn commit.
- **monitor_port_design.md: left untouched (out of scope).** Two things there are
  now slightly stale and will be recorded in Final Implementation Notes as upstream
  observations for a possible follow-up, **not** fixed here:
  (a) its §Command verb intro calls permissions.md the "seed table … which
  predates forward_key, pick_next_sibling, restart_task" — true historically, but
  after this sync permissions.md no longer lacks them;
  (b) its own call-site line numbers (`tmux_monitor.py:526`, `monitor_shared.py:311`,
  etc.) are stale post-t822_6 (symbols now in `monitor_core.py`).
  Fixing the canonical doc is a separate concern from "sync the seed into agreement
  with the canonical"; pulling it in would widen blast radius beyond the task.

## Verification (AC)

1. **No orphans either direction:** diff the verb set of permissions.md's table
   against monitor_port_design.md §Command verb table — every verb appears in both
   with the same gate. (`forward_key`→m_c, `pick_next_sibling`/`restart_task`→full,
   `task_detail`→r_o, etc.)
2. **YAML ↔ column parity:** for each profile YAML, `allowed_verbs` equals the set
   of ✓ verbs in its column (read_only: snapshot, subscribe, request_keyframe,
   task_detail; monitor_control: + send_enter, send_keys, forward_key, focus,
   cycle_compare_mode; full: + kill_pane, kill_window, spawn_tui, pick_next_sibling,
   restart_task). Confirmed already true in exploration; re-confirm after the edit.
3. **Cross-reference links resolve:** the `monitor_port_design.md`,
   `content_transport.md`, and `protocol.md` links and section anchors in the
   edited regions still point at existing files/sections.
4. **No stale `tmux_monitor.py:`/`monitor_shared.py:` line citations** remain in
   permissions.md (`grep -n 'tmux_monitor.py:\|monitor_shared.py:' permissions.md`
   → empty).

## Post-implementation
Per task-workflow Step 8 (review) → Step 9 (commit on current branch, no merge/worktree
for profile 'fast'; `documentation:` commit type) → archival via
`aitask_archive.sh 822_12`.

## Risk

### Code-health risk: low
- None identified. Single-file edit to a markdown doc (`permissions.md`); no code,
  no behavior change. YAMLs are verify-only. Blast radius is one doc plus a
  read-only YAML cross-check.

### Goal-achievement risk: low
- Mis-mapping a verb's gate or omitting a canonical verb · severity: low · →
  mitigation: verification steps 1–2 diff the verb/gate set against the canonical
  table and the YAML columns, catching any drift before commit.
- User may prefer the canonical doc's now-stale "seed table" prose and stale
  call-site line numbers also be fixed · severity: low · → mitigation: recorded as
  an explicit scope decision + Final Implementation Notes upstream observation;
  trivially revisable at Step 8 review if the user wants it in-scope.

