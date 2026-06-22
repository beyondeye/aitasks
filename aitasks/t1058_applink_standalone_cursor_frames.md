---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [applink]
created_at: 2026-06-22 16:52
updated_at: 2026-06-22 16:52
---

Emit standalone AppLink `cursor` (0x04) frames for cursor-only motion. content_transport.md defines the cursor frame for REPL-prompt blink / vim normal-mode motion where no cells change.

Current state: applink/pusher.py defers standalone cursor-only frames (module docstring: 'standalone cursor-only frames remain deferred so idle panes cost zero binary bytes (detecting cursor-only motion would need a per-tick cursor fetch per pane)'). The cursor is only ever folded into keyframe/delta today. The mobile decoder already handles 0x04 (aitasks_mobile FrameDecoder.kt:76-81).

Fix (low priority): detect cursor-only motion (cursor changed, content hash unchanged) on a tick and emit encode_cursor instead of skipping, weighing the per-tick cursor-fetch cost noted in the docstring. Idle-pane zero-byte behavior must be preserved when the cursor is also unchanged.

Surfaced by the aitasks_mobile t14_11 AppLink audit (aidocs/applink/implementation_status_2026-06-22.md, server #4).
