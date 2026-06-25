---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [applink, applink_dataplane]
created_at: 2026-06-22 16:51
updated_at: 2026-06-25 09:55
---

AppLink live keyframes must carry viewport-only positive row_ids; today the server bundles ~200 scrollback rows into a viewport-sized keyframe, violating content_transport.md §Row schema (row_id 0 = top of visible viewport; scrollback uses NEGATIVE ids, history RPC only).

Root cause (confirmed end-to-end):
- monitor/monitor_core.py:1178-1181 captures `tmux capture-pane -p -e -t <pane> -S -<capture_lines>` with capture_lines=200 (monitor_core.py:798,808,1447), so PaneSnapshot.content is viewport (~24) + ~200 scrollback rows.
- applink/pusher.py:202-208 calls encode_keyframe(..., dims[1], cursor, full_rows, ...): the wire `rows` field is dims[1] (pane height ~24) but full_rows is ALL parsed rows (~224), with row_id 0 = top of the captured buffer (oldest scrollback), not the viewport.
- delta/append inherit the same row-id basis.

Impact: this is the server-side root cause of the mobile rendering bug fixed defensively in aitasks_mobile t14_10 (the client now renders correctly against both buggy and spec-compliant servers, but the server is the real fix).

Fix direction: emit only the live viewport rows (row_id 0..rows-1 = visible area) in keyframe/delta/append; route scrollback through the (unimplemented) history RPC with negative ids. Decide whether to keep capturing scrollback for history while only streaming the viewport live.

Cross-repo: paired with aitasks_mobile t14_11 audit (aidocs/applink/implementation_status_2026-06-22.md) and the defensive client fix t14_10.
