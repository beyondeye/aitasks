---
Task: t822_new_ait_bridge_tui.md
Base branch: main
plan_verified: []
---

# Plan: t822 — New `ait applink` TUI (parent task; splits into 3 children)

## Context

This task introduces a brand-new framework TUI named **`applink`** that will eventually let a mobile companion app (developed in the sibling repo `../aitasks_mobile`, Kotlin Multiplatform) connect to a local `ait ide` tmux session and interact with framework TUIs (starting with `ait monitor`) from the phone.

The first end-to-end goal is **device pairing via QR code** + a permission-gated control surface. Concrete code for the mobile side and full protocol implementation are out of scope for this parent task — this PR delivers (1) the architecture/protocol design, (2) the bare-bones `applink` TUI with a working QR-pairing screen, and (3) the design doc for porting `ait monitor` features through `applink`.

**Decisions locked in pre-plan (do not re-prompt):**

- TUI name: **`applink`** (NOT "bridge"). Command: `ait applink`. Python module: `.aitask-scripts/applink/`.
- Split into **3 children**, one per deliverable in the parent description.
- Transport choice (LAN WebSocket vs. WebRTC vs. relay) is **deferred to child 1** — it must survey options and choose with a rationale.
- Mobile-repo coordination is **document-only** in this PR — child 1 produces a versioned protocol-contract aidoc; the user will mirror a task into `../aitasks_mobile` manually afterward.

**Architecture seam (from Explore findings):** the existing `ait monitor` already has a natural split — `.aitask-scripts/monitor/tmux_monitor.py` and `tmux_control.py` are pure-data/control modules, only `monitor_app.py` (Textual) is UI-bound. Child 3 leverages this: it does **design only**, no refactor yet.

## Approach: create 3 child tasks + 3 child plans, then stop

Because the parent is high-effort and explicitly slated for splitting, this parent task itself produces no production code. After Step 8 (review + commit of the task + plan files), the parent's "Stop here" path is taken — children are picked individually later in fresh contexts.

### Child 1 — `applink` protocol & architecture design (aidocs)

**Filename:** `aitasks/t822/t822_1_applink_protocol_design.md`
**Plan:** `aiplans/p822/p822_1_applink_protocol_design.md`
**issue_type:** `documentation`, **effort:** medium, **priority:** high

Deliverables:
- `aidocs/applink/protocol.md` — wire protocol design covering: transport choice + rationale (LAN WebSocket recommended as default, with notes on relay/WebRTC fallbacks); message envelope (JSON over WS, request/response + server-push frames); auth & session lifecycle (QR-encoded one-time pairing token → exchanged for a per-session bearer that is scoped to a permission profile); versioning header.
- `aidocs/applink/permissions.md` — permission-profile model (default profiles: `read_only`, `monitor_control`, `full`); how a profile gates verbs (e.g. `send_enter` allowed in `monitor_control`; `kill_window` only in `full`); how profiles are stored and selected at pairing time.
- Cross-reference: add a one-line pointer in root `CLAUDE.md` under a new short "## Mobile Companion" subsection pointing to `aidocs/applink/`.

Reference style: `aidocs/gitremoteproviderintegration.md` (architecture + extension checklist + tables).

### Child 2 — basic `applink` TUI + QR pairing screen

**Filename:** `aitasks/t822/t822_2_applink_tui_qr.md`
**Plan:** `aiplans/p822/p822_2_applink_tui_qr.md`
**issue_type:** `feature`, **effort:** medium, **priority:** high
**depends:** [822_1] (needs the auth/pairing-token shape decided in child 1)

Deliverables:
- New module dir `.aitask-scripts/applink/` with `__init__.py` and `applink_app.py` (Textual App, mimic `brainstorm/brainstorm_app.py` boilerplate at line ~2110; `TuiSwitcherMixin` for `j` switching).
- New launcher `.aitask-scripts/aitask_applink.sh` (mimic `.aitask-scripts/aitask_brainstorm_tui.sh` lines 1–32: use `require_ait_python_fast` from `lib/python_resolve.sh`, dependency-check block, exec the Python app).
- Dispatcher: add `applink) shift; exec "$SCRIPTS_DIR/aitask_applink.sh" "$@" ;;` to `/home/ddt/Work/aitasks/ait` (case statement near line 187) plus help text near line 31.
- TUI registry: add `("applink", "App Linker", "ait applink", True)` to `TUI_REGISTRY` in `.aitask-scripts/lib/tui_registry.py` (line 17–27).
- Python dep: add `segno` (pure-Python, no compiled deps) to both `pip install` lines in `.aitask-scripts/aitask_setup.sh` (lines 574, 655). Justify in the plan: pure-Python keeps install path identical to today; `segno` has a `terminal()` renderer suitable for Textual `Static` widget.
- Screens in the TUI (minimum viable):
  - **Pairing screen**: generates a one-time pairing token per child 1's design, renders the QR via `segno` ASCII into a Textual `Static`, shows the encoded URL/token below for debugging. Refresh button regenerates token.
  - **Status screen**: placeholder showing "No client connected" (no real socket yet — wiring is child 2's stretch goal; if cut, mark as TODO routed to a follow-up task).
- Website docs: new `website/content/docs/tuis/applink/_index.md`, `how-to.md`, `reference.md` (mirror `website/content/docs/tuis/board/`). Add `applink` to `website/content/docs/tuis/_index.md` Available TUIs list (line 23).
- Smoke test: scripted `python .aitask-scripts/applink/applink_app.py --smoke` flag (or equivalent) that renders one frame and exits non-interactively, callable from CI.

### Child 3 — design doc: porting `ait monitor` through `applink`

**Filename:** `aitasks/t822/t822_3_monitor_port_design.md`
**Plan:** `aiplans/p822/p822_3_monitor_port_design.md`
**issue_type:** `documentation`, **effort:** medium, **priority:** high
**depends:** [822_1] (uses the protocol envelope decided there)

Deliverables:
- `aidocs/applink/monitor_port_design.md` — refactor plan covering:
  - **Headless-core extraction**: identify which functions in `tmux_monitor.py:390–675` and `tmux_control.py:69–548` become the public API of a `.aitask-scripts/monitor/monitor_core.py`, and which Textual-bound code in `monitor_app.py` stays put. (Tables of file:line refs already gathered during Explore.)
  - **Command-verb surface**: document the 7 verbs (`send_enter`, `forward_key`, `switch_to_pane`, `kill_pane`, `kill_window`, `spawn_tui`, `cycle_compare_mode`) and map each to a `applink` protocol message + the permission profile that gates it.
  - **Snapshot data model**: spec the JSON shape of `PaneSnapshot` (tmux_monitor.py:150–171) as sent over the wire, including scroll-anchor strategy (substring-anchor, not pixel offset) and the two-tier refresh cadence (3s default, 0.3s when focused — `monitor_app.py:1268–1274`).
  - **Modal-dialog handshake**: spec how modal confirmations (`KillConfirmDialog`, `SessionRenameDialog`) become request/response RPCs over the wire.
  - **Task-detail RPC**: spec how `TaskInfoCache` (`monitor_shared.py:217–321`) is served to the mobile client (which has no filesystem access).
  - **Out of scope (deferred to follow-up tasks):** the actual refactor + a `monitor → applink` glue layer. Each deferral is a clearly-labeled bullet at the end so future tasks can be created cleanly.
- This doc explicitly does **NOT** modify any code under `.aitask-scripts/monitor/` — it is a design artifact only.

## Parent-task work itself (this PR)

1. Run the **Batch Task Creation Procedure** (`.claude/skills/task-workflow-fast-/task-creation-batch.md`) three times to create child tasks 822_1, 822_2, 822_3 with the descriptions above embedded in their files (per child documentation requirements).
2. Revert parent `t822` status to `Ready` and clear `assigned_to` (per `planning.md` §6.1 — only the child being worked on should be `Implementing`).
3. Release the parent task lock (`./.aitask-scripts/aitask_lock.sh --unlock 822 || true`).
4. Write the three child plan files under `aiplans/p822/` using the metadata header convention from `planning.md` (`Parent Task:`, `Sibling Tasks:`, `Branch: aitask/t822_<n>_<name>`, `Base branch: main`).
5. Commit child plans together: `./ait git add aiplans/p822/ && ./ait git commit -m "ait: Add t822 child implementation plans"`.
6. **Manual-verification sibling check** — N=3 children, so the post-child-creation prompt fires. The QR pairing screen (child 2) clearly produces TUI behavior only a human can validate (does the QR scan? does the token rotate?). Recommend offering an aggregate sibling covering children 2 and 3 (child 1 is pure docs, no manual verify needed).
7. Take the **"Stop here"** child checkpoint option so children are picked individually later in fresh contexts (each is itself non-trivial; bundling them in one context risks stale planning).

## Verification (parent PR)

The parent PR itself does not change runtime behavior. Verification is:

- `git ls-files aitasks/t822/` lists three child task files.
- `git ls-files aiplans/p822/` lists three child plan files.
- `cat aitasks/t822_new_ait_bridge_tui.md` shows `status: Ready`, empty `assigned_to`, and `children_to_implement: [822_1, 822_2, 822_3]` (auto-populated by `aitask_create.sh --parent`).
- `./.aitask-scripts/aitask_ls.sh -v --children 822 99` lists all three children.
- (Conditional) If the manual-verification sibling is created, `aitasks/t822/` will contain a fourth child (e.g., `t822_4_manual_verification_*.md`).

End-to-end verification of the actual applink TUI is performed during child 2's own task workflow — not here.

## Step 9 reminder

Standard post-implementation: commit child task files (handled by Batch Task Creation), commit child plans, revert parent status. The "Stop here" path skips Step 7 (no implementation) but still runs Step 8 (review + plan commit), Step 8b/8c follow-ups, and Step 9 (post-impl: no merge needed since work is on current branch per profile `fast`).
