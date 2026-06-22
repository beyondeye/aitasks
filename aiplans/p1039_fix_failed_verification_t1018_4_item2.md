---
Task: t1039_fix_failed_verification_t1018_4_item2.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# p1039 — Fix retry-apply footer leak (Textual None-vs-False check_action semantics)

## Context

t1018_1 scoped the brainstorm `ctrl+r` "Retry initializer apply" binding to the
(R)unning tab via `BrainstormApp.check_action`, which returns `None` for the
"hide" path. The t1018_4 manual-verification item #2 — *"No retry-apply binding
leaks into the footer on tabs/screens where it is irrelevant; each shows only on
its owning surface"* — **failed** anyway, spawning this task (t1039).

**Root cause (empirically reproduced against Textual 8.2.7):** the t1018_1
author's assumption that *"returning `None` hides the binding from the footer"*
is wrong for this Textual version. In `Screen.active_bindings`
(`textual/screen.py:474-481`):

- `check_action` → **`False`** → the binding is `continue`d (skipped) → **removed
  from the footer entirely**.
- `check_action` → **`None`** → `enabled = bool(None) = False` → the binding is
  **kept** in `active_bindings`, and `Footer.compose` (`textual/widgets/_footer.py:248-289`)
  renders it **dimmed** (`-disabled` class → `text-style: dim`).
- `check_action` → **`True`** → shown, enabled.

So on Browse/Session tabs `ctrl+r Retry initializer apply` appears in the footer
*greyed out* rather than absent — exactly the "leak" the verifier saw. (The
existing unit test passed because it asserted `check_action`'s return value, not
the rendered footer — see Reproduction below.)

**Firing is unaffected by the fix.** `App.run_action` (`textual/app.py:4245`)
and `_check_bindings` gate dispatch on `if check_action(...)` — both `None` and
`False` are falsy, so the action already does not fire on the wrong surface. The
fix changes **footer display only** (removes the dimmed entry); no key that fired
before stops firing.

## Reproduction (already run)

Booted a real `BrainstormApp` over a temp session and inspected the footer:

| Surface | Current (`None`) | After fix (`False`) |
|---------|------------------|---------------------|
| Browse tab | `ctrl+r` **present, dimmed** ← leak | `ctrl+r` **absent** ✓ |
| Session tab | `ctrl+r` present, dimmed ← leak | `ctrl+r` absent ✓ |
| Running tab | `ctrl+r` present, enabled ✓ | `ctrl+r` present, enabled ✓ |

`app.check_action("retry_initializer_apply")` already returns `None` on
Browse/Session and `True` on Running — the gating logic is correct; only the
`None` return value is wrong for footer suppression.

## Files to modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — `BrainstormApp.check_action`
  (currently `:2171-2209`) and its `_TAB_SCOPED_ACTIONS` doc comment (`:2076-2078`).
- `tests/test_brainstorm_binding_scope.py` — upgrade the regression guard to
  assert the **rendered footer** (the surface that actually leaked), not just
  `check_action`'s return value.

## Implementation steps

### Step 1 — Replace every hide-intent `return None` with `return False`

In `BrainstormApp.check_action` (`:2171-2209`), all seven `return None` statements
are "hide this binding" intents. Change each to `return False` so the binding is
removed from the footer (not dimmed) on non-owning surfaces:

- `:2180` — non-modal pushed-screen guard (the pushed screen owns the footer).
- `:2187` / `:2189` / `:2191` — `node_action`/`toggle_deferred` when `TabbedContent`
  is missing / wrong tab / no primary selection.
- `:2201` / `:2203` — tab-scoped action when `TabbedContent` is missing / wrong tab.
- `:2208` — `open_node_detail` not currently visible.

The trailing `return True` paths (owning surface) are unchanged.

### Step 2 — Fix the now-wrong comments

- Rewrite the method's top comment (`:2172-2175`) to state the correct Textual
  8.2.7 rule: *return `False` to remove a binding from the footer (and disable it);
  `None` would leave it visible-but-dimmed. `True` = active on its owning surface.*
- Update the `_TAB_SCOPED_ACTIONS` comment (`:2076-2078`) — "returns None when the
  active tab does not match" → "returns False …".

These are the only two stale comments referencing the old `None` behavior
(grep-confirmed). The `bool | None` return annotation is left as-is (it matches
the `DOMNode.check_action` base signature and the sibling
`ActionsWizardScreen.check_action`); the corrected comment documents intent.

### Step 3 — Scope note (sibling actions fixed in the same method)

The failing item names only retry-apply, but `node_action` (`A`),
`toggle_deferred` (`f`), and `open_node_detail` (`enter`) share the **identical
defect** (same method, same `None`-to-hide pattern → dimmed footer leak on
non-owning surfaces). Fixing the whole method in one pass is the structural
root-cause fix and prevents the same verification from re-failing on those keys.
This is an explicit, intentional scope choice (not silent AC drift); the AC
covers retry-apply, and the sibling fixes are a no-risk superset on the same code
path. **Rejected alternative:** change only the two `_TAB_SCOPED_ACTIONS` returns
(retry-apply + open_node_detail) — rejected because it would leave `node_action`/
`toggle_deferred` leaking dimmed, inviting a repeat failure and an inconsistent
method (some hides `None`, some `False`).

**Out of scope (unchanged):** app-level bindings appearing in *modal* footers
(e.g. the wizard) — modals deliberately fall through the non-modal guard; that is
a separate surface not covered by this item. The non-modal pushed-screen guard
(Step 1, `:2180`) *is* fixed since it is the same dimmed-leak class and is
display-only.

### Step 4 — Upgrade the regression test (`tests/test_brainstorm_binding_scope.py`)

The current test asserts `app.check_action(...) is None` off Running — which is
exactly why the bug shipped: `check_action` returned `None` (the test passed)
while the footer still showed the dimmed key. Re-point the guard at the **real
ground truth** the verifier looked at: membership in `screen.active_bindings`
(what `Footer.compose` iterates — present ⟺ visible in footer).

- Replace the `assertIsNone`/`assertTrue` check_action assertions with footer-level
  assertions per tab:
  - Running tab: `"ctrl+r" in app.screen.active_bindings` **and** the
    `ActiveBinding.enabled` is `True` (active on its owning surface).
  - Browse / Session tabs: `"ctrl+r" not in app.screen.active_bindings` (truly
    absent from the footer — this assertion **fails on the old `None` code**,
    making it a real regression guard for this bug).
- Keep a secondary `assertFalse(app.check_action("retry_initializer_apply", None))`
  / `assertTrue(... on running)` to pin the corrected `False`/`True` contract.
- `active_bindings` is recomputed live on access (calls `check_action` per binding),
  so the existing `_activate_tab` helper (sets `TabbedContent.active` + settle) is
  sufficient — no footer-recompose timing needed. Update the module docstring to
  note the guard is now footer-membership based.

## Verification

- `python -m pytest tests/test_brainstorm_binding_scope.py -q` (or
  `python -m unittest`) — green, and the new Browse/Session "absent" assertions
  fail when reverted to `return None` (confirmed via a monkeypatched probe).
- Full brainstorm suite: `python -m pytest tests/test_brainstorm*.py -q` green
  (catch any test that asserted the old dimmed-but-present behavior — none expected).
- `shellcheck` not applicable (Python-only change).
- Live re-verification of the original t1018_4 item #2 (footer on each tab through
  the real ghostty→tmux→Textual stack) — offered as a standalone
  manual-verification follow-up at Step 8c (the failing item was live-observed; a
  headless `active_bindings` assertion is the automated guard, real-terminal
  footer rendering is the human check).

## Risk

### Code-health risk: low
- Change is display-only (footer membership) on a single, well-understood method;
  firing semantics are provably unchanged (`run_action` already treats `None` and
  `False` as falsy). · severity: low · → mitigation: footer-level regression test
  (in-task, Step 4).
- Touching the sibling actions (`node_action`/`toggle_deferred`/`open_node_detail`)
  widens the blast radius slightly, but only by removing already-disabled dimmed
  entries from the footer. · severity: low · → mitigation: full brainstorm suite
  run (in-task).

### Goal-achievement risk: low
- Headless `active_bindings` cannot prove real-terminal footer rendering (same
  class as the original chord-delivery gap). · severity: low · → mitigation:
  standalone manual-verification follow-up (Step 8c) re-checks item #2 live.

## Step 9 — Post-implementation
Single-task parent. Commit code + plan separately, review at Step 8 (non-skippable),
then archive via `./.aitask-scripts/aitask_archive.sh 1039`.

## Final Implementation Notes
- **Actual work done:**
  - `.aitask-scripts/brainstorm/brainstorm_app.py` — replaced all 7 hide-intent
    `return None` in `BrainstormApp.check_action` with `return False`, and
    rewrote the method's top comment + the `_TAB_SCOPED_ACTIONS` doc comment to
    state the correct Textual 8.2.7 footer rule (`False` removes from the footer;
    `None` only dims). Covers `retry_initializer_apply` (the failing item) plus
    the same-defect siblings `node_action` / `toggle_deferred` / `open_node_detail`
    and the non-modal pushed-screen guard.
  - `tests/test_brainstorm_binding_scope.py` — rewrote the guard to assert
    **footer membership** (`screen.active_bindings`) rather than `check_action`'s
    raw return value (the gap that let t1018_1 ship the leak). Asserts `ctrl+r`
    present+enabled on Running and absent on Browse/Session; pins the corrected
    `False`/`True` contract. Removed the now-unused module-level `RETRY_ACTIONS`.
- **Deviations from plan:** None. Implemented exactly as designed.
- **Issues encountered:** None. Root cause (Textual `None`-vs-`False`
  `active_bindings` semantics) was confirmed empirically before planning and the
  fix matched the predicted footer behavior.
- **Key decisions:** Kept the `-> bool | None` annotation (matches the
  `DOMNode.check_action` base + the sibling `ActionsWizardScreen.check_action`);
  the corrected comment documents that `None` is intentionally never returned.
- **Upstream defects identified:** None. (The misunderstanding lived in
  brainstorm's own `check_action`, not in a separate upstream helper.)
- **Verification results:** `tests.test_brainstorm_binding_scope` ✓; full
  brainstorm suite (646 tests) ✓; shortcut-scopes guard (6 tests) ✓; live-booted
  `BrainstormApp` footer check — `ctrl+r` absent on Browse/Session, present on
  Running ✓.
