---
Task: t1864_fix_stale_attach_help_and_design_doc.md
Base branch: main
Output branch: main
---

# t1864 — Fix stale `ait attach` help line and design-doc decomposition

## Context

While writing the `ait attach` website reference (t1687_2), two stale upstream
statements turned up:

1. `ait:51` — the dispatcher help says `(ls; add/get/rm/move/gc pending)`,
   implying only `ls` works. In fact `ls/add/get/rm/gc` all work
   (`.aitask-scripts/aitask_attach.sh:9` STATE comment). Only `move` is a stub:
   `cmd_stub move` at line 748 exits with "not yet available".
2. `aidocs/task_attachments_design.md:396` — §11's decomposition item 3 says
   "decref on archive". That contradicts §8, which settled (t1030_3) that
   archiving never decrefs; a blob becomes reclaimable only once it is fully
   orphaned, and `orphaned_at` plus `attachments_gc_grace` then control `gc`.

Grep confirms each string exists only at these two sites. No test, seed copy or
website page pins either one.

## Changes

### 1. `ait:51`
```
-  attach         Manage task file attachments (ls; add/get/rm/move/gc pending)
+  attach         Manage task file attachments (ls/add/get/rm/gc; move pending)
```
The column alignment stays unchanged.

### 2. `aidocs/task_attachments_design.md` §11 item 3
Replace
```
3. **Archive integration** — decref on archive, `ait attach gc`, grace
   knob.
```
with
```
3. **Archive integration** — `ait attach gc` over fully-orphaned blobs
   (`orphaned_at` grace clock, `attachments_gc_grace` knob); archiving
   keeps an archived task's refs (see §8 — resolved in t1030_3, archiving
   never decrefs).
```
§11 stays a decomposition list; the item is simply corrected to match what
shipped.

## Verification
- `./ait help 2>&1 | grep attach` shows the new parenthetical.
- `grep -n 'decref on archive' aidocs/task_attachments_design.md` returns nothing.
- `bash -n ait`. The change is a single string edit inside a heredoc/echo block,
  so there is no shellcheck delta.

## Step 9
Commit the code with `bug: ... (t1864)`, then archive through the standard Step 9
post-implementation flow on the current branch (main).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
