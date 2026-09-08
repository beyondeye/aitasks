---
Task: t1738_extract_freeze_store_helpers.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1738 — Extract the freeze engine's store/tmux plumbing into a shared module

## Context

`lib/agent_freeze.py` (shipped in t1705_4) keeps the frozen-agent **store wire
protocol** and its **tmux plumbing** in private module-level helpers: `_store`,
`_store_show`, `_nonce_from`, `_pane_facts`, `_pane_location`, `_set_option`,
`_unset_option`, `_respawn`, the failure-injection seams (`_test_mode`,
`_fail_at`, `_pause_at`), the `_StageFailure` exception and the wrapper exit
codes.

t1705_5 adds a **second** engine — `lib/agent_restore.py`, a ~400-line restore
coordinator — that needs the same surface. Its approved plan
(`aiplans/p1705/p1705_5_restore_and_repick_flows.md`) records the resulting
code-health risk and defers it to *this* task as a blocking "before":

> `agent_restore.py` … duplicates several private helpers from
> `agent_freeze.py` … Copying them forks two engines that must stay in agreement
> about the store wire protocol; importing them couples the coordinator to a
> module deliberately written to work without it.

Neither obvious option is acceptable: copying forks the protocol (verb names,
argument shapes, the `NONCE_MISMATCH` / `TRANSITION_REFUSED` / `LEASE_HELD` exit
codes, the seam names) and the drift is silent; importing `agent_freeze`'s
privates couples the coordinator to the repair module, which
`agent_freeze.py`'s own docstring says must keep settling abandoned restores
with **no coordinator present**.

**Outcome:** a third module both engines import, so t1705_5 *shares* the wire
protocol instead of forking it. Behaviour-preserving — the freeze engine ships
today and must be invisible in this change.

## Design

### New module: `.aitask-scripts/lib/agent_frozen_ops.py`

Named for the `frozen` domain (`aitask_frozen.sh`), not for either engine.
Dependency arrow runs **one way**: it imports `tmux_exec` and
`monitor.monitor_core` only — never `agent_freeze`, never `agent_restore`, and
(deliberately) not even `agent_sessions`. That keeps it thin and keeps
reconcile's independence from the coordinator intact.

Contents, in the order the current file has them:

| Member | From `agent_freeze.py` |
|---|---|
| `SESSIONS_SH` | same |
| `EXIT_LOCK_BUSY` / `EXIT_TRANSITION_REFUSED` / `EXIT_NONCE_MISMATCH` / `EXIT_LEASE_HELD` | same |
| `StageFailure` | `_StageFailure` |
| `test_mode()`, `make_fail_at(env_var)`, `pause_at(stage)` | `_test_mode` / `_fail_at` / `_pause_at` |
| `_TMUX`, `run(args, timeout=…)` | `_TMUX` + the direct `.run` calls |
| `store(*argv, timeout=20.0)`, `store_show(id)`, `nonce_from(line)` | same |
| `PANE_FACT_FORMAT`, `PANE_FACT_KEYS`, `pane_facts(id)`, `pane_location(id)` | `_PANE_FACT_*` / `_pane_facts` / `_pane_location` |
| `set_option`, `unset_option`, `respawn` | same |
| `int_or_zero(value)` | `_int` |

Bodies are moved **verbatim** (docstrings included) — only the leading
underscore is dropped and `_TMUX.run(...)` becomes `run(...)`.

**`make_fail_at(env_var)` is the one shape change.** `_fail_at` hard-codes
`AITASKS_FREEZE_FAIL_AT`; t1705_5 needs `AITASKS_RESTORE_FAIL_AT` at the same
seam. A factory keeps every existing call site (`_fail_at("capture")`,
7 of them) byte-identical:

```python
_fail_at = frozen_ops.make_fail_at("AITASKS_FREEZE_FAIL_AT")
```

`AITASKS_FROZEN_PAUSE_AT` is already shared, so `pause_at` stays a plain
function.

### The seam rule (this is the load-bearing part)

`tests/test_agent_freeze.py` swaps two names to run without tmux or a store
file: `agent_freeze._TMUX` and `agent_freeze._store`. Those swaps must keep
working, and must now cover **both** engines from one place. So:

> **State and behaviour through the module object; pure names by import.**

- `store` and `_TMUX` live in `agent_frozen_ops` and are looked up as that
  module's globals at call time. Swapping `agent_frozen_ops.store` therefore
  also redirects `store_show` (which calls `store(...)`), and swapping
  `agent_frozen_ops._TMUX` redirects every `run(...)` caller — including
  `agent_restore`'s, for free.
- `agent_freeze` calls every moved **function** as `frozen_ops.<name>(...)`.
  An import-time alias (`from agent_frozen_ops import store as _store`) would
  bind the original object and silently miss the swap — that is exactly the
  two-seam problem this task removes, so it is banned in the module docstring.
- Constants and `StageFailure` are never swapped, so they are import-aliased
  (`from agent_frozen_ops import StageFailure as _StageFailure`, the `EXIT_*`
  names). Re-exporting `EXIT_*` into `agent_freeze` keeps the existing
  `agent_freeze.EXIT_NONCE_MISMATCH` test references working unchanged.

### `.aitask-scripts/lib/agent_freeze.py` — edits

- Replace the moved definitions with `import agent_frozen_ops as frozen_ops`
  plus the import-aliases above; drop the now-unused `signal` and `subprocess`
  imports (`tempfile` stays — `_write_observation` uses it).
- Rewrite ~60 call sites mechanically: `_store(` → `frozen_ops.store(`,
  `_store_show(` → `frozen_ops.store_show(`, `_nonce_from(` →
  `frozen_ops.nonce_from(`, `_pane_facts(` → `frozen_ops.pane_facts(`,
  `_pane_location(` → `frozen_ops.pane_location(`, `_set_option(` →
  `frozen_ops.set_option(`, `_unset_option(` → `frozen_ops.unset_option(`,
  `_respawn(` → `frozen_ops.respawn(`, `_pause_at(` → `frozen_ops.pause_at(`,
  `_int(` → `frozen_ops.int_or_zero(`.
  `_fail_at(` and `_StageFailure` call sites are untouched.
- `_capture` and `_enumerate_session` keep their freeze-specific bodies but
  issue tmux through `frozen_ops.run(...)`.
- Update the module docstring: boundary 1 ("every tmux call goes through
  `TmuxClient`") and boundary 2 ("every store WRITE goes through the shell
  wrapper") now name `agent_frozen_ops` as where that is enforced, and the test
  seam list points at `make_fail_at`.

**Deliberately staying in `agent_freeze.py`** (freeze-only, or explicitly
non-shareable): `DEFAULT_CAPTURE_MAX_LINES`, `capture_max_lines`, `_capture`,
`_write_private`, `_walk_up_to_project`, `_resolve_record`, `STAGES`,
`FreezeResult`, `RESTORE_ACK_GRACE`, `_RECONCILE_FORMAT` / `_RECONCILE_ARITY`
(whose docstring says explicitly *do not unify* with `_PANE_FACT_FORMAT`),
`_Observed`, `_Lease`, `_LeaseUnavailable`, `_respawn_standin`, the four
`_reconcile_*` handlers, `_epoch`, `_stale_grace`, `reconcile`, `main`.

### `tests/test_agent_freeze.py` — one function

`_install` (the only place the swap happens) re-points from `agent_freeze` to
`agent_frozen_ops`; add the `import agent_frozen_ops` beside the existing
imports and update the module docstring's `agent_freeze._store` mention. No
assertion changes — every `agent_freeze.EXIT_*` / `agent_freeze.*_OPTION` /
`agent_freeze._reconcile_*` / `agent_freeze._Observed` reference stays valid.

### New: `tests/test_agent_frozen_ops.py` — the shared-surface contract

The freeze suite only pins the shared module **incidentally**, through the
members `agent_freeze` happens to call. Three promised exports have **no caller
at all** after the move — `test_mode`, `SESSIONS_SH`, and
`PANE_FACT_FORMAT` / `PANE_FACT_KEYS` — so a rename or omission there ships
green and surfaces only when t1705_5 is written against a name that is not
there. Neither the one-way import arrow nor the "never import-alias the swapped
names" rule is enforced by anything but a docstring.

(For the record: an accidental alias of `store` or `_TMUX` inside
`agent_freeze` would *not* pass silently — the fakes would stop being called and
`_FakeStore.verbs()` / `_FakeTmux.calls_of("capture-pane")` would fail loudly.
The contract test's value is pinning the rule for the **second** consumer, and
covering the exports nothing calls.)

A new unit module — no tmux, no store file, no `agent_sessions`:

1. **Surface pin.** A literal `PROMISED` tuple of every exported name
   (`store`, `store_show`, `nonce_from`, `run`, `pane_facts`, `pane_location`,
   `set_option`, `unset_option`, `respawn`, `int_or_zero`, `test_mode`,
   `make_fail_at`, `pause_at`, `StageFailure`, `SESSIONS_SH`,
   `PANE_FACT_FORMAT`, `PANE_FACT_KEYS`, and the four `EXIT_*` codes) asserted
   present with `hasattr`, plus `callable(...)` on the functions. Failure
   message says the surface is a cross-module contract and a member must be
   re-pinned, not dropped.
2. **`store` is late-bound.** Replace `agent_frozen_ops.store` with a recorder
   returning `(0, "state:frozen")`; call `agent_frozen_ops.store_show("abc")`
   and assert the recorder saw `("show", "abc")` and the dict parsed. This is
   the case a flat `from … import store` inside the module would break.
3. **`_TMUX` is late-bound.** Replace `agent_frozen_ops._TMUX` with a fake
   client; drive `run`, `pane_facts`, `pane_location`, `set_option`,
   `unset_option`, `respawn` and assert each reached the fake with the expected
   argv (`-p`/`-pu` for the option pair, `respawn-pane -k`, the tab-joined
   `PANE_FACT_FORMAT`), and that `pane_facts` returns `{}` on a short/failed
   read.
4. **No engine import-aliases the swapped names.** Parameterized over the
   engine modules that exist (`agent_freeze` today; `agent_restore` joins the
   list in t1705_5):

   ```python
   banned = {id(agent_frozen_ops.store), id(agent_frozen_ops._TMUX)}
   offenders = [n for n, v in vars(engine).items() if id(v) in banned]
   self.assertEqual(offenders, [], ...)
   ```

   This is the direct, non-brittle enforcement of the seam rule — an
   import-time alias is exactly a module-global bound to the original object.
5. **The dependency arrow is one-way.** Assert `agent_frozen_ops`'s source
   contains no `import agent_freeze` / `import agent_restore`, and that neither
   name appears in `vars(agent_frozen_ops)`.
6. **`test_mode` / `make_fail_at` / `pause_at` honour their gate.** With
   `AITASKS_TEST_MODE` unset the seams are inert; with it `=1` and the named
   env var set, `make_fail_at("AITASKS_RESTORE_FAIL_AT")("begin")` raises
   `StageFailure` with `.stage == "begin"` while
   `make_fail_at("AITASKS_FREEZE_FAIL_AT")("begin")` does not — the exact
   two-engine isolation t1705_5 depends on.

### `tests/test_freeze_engine_live.sh` — one comment

Line ~126 names `agent_freeze._pane_facts` and `_pane_location`; re-point to
`agent_frozen_ops.pane_facts` / `pane_location`. Comment only.

### Not needed

- **No `tests/test_no_raw_tmux.sh` allowlist entry** — the new module routes
  through `TmuxClient`, so the guard never sees a `"tmux"` argv literal.
- **No `tests/test_metadata_writer_inventory.py` pin** — nothing that names an
  `aitasks/metadata` path (`capture_max_lines`, `_walk_up_to_project`) moves,
  and the new module has no write primitive matching `_PY_WRITE`.
- **No skill/permission touchpoints** — this is a Python lib module imported by
  other Python, not a skill-invoked shell helper
  (`aidocs/framework/aitasks_extension_points.md` § "Adding a new helper
  script").
- **No `aitask_frozen.sh` change** — it execs `agent_freeze.py`, unchanged.

## Implementation steps

1. Write `.aitask-scripts/lib/agent_frozen_ops.py` with the sys.path bootstrap
   idiom already used by `agent_freeze.py` (`_LIB_DIR` / `_SCRIPTS_DIR`
   insertion), the members above moved verbatim, and a docstring stating the
   one-way dependency rule, the two hard boundaries it now owns, and the seam
   rule (call through the module; never import-alias `store`).
2. Edit `agent_freeze.py`: imports, call-site rewrites, docstring update.
3. Write `tests/test_agent_frozen_ops.py` with the six case groups above.
   Written **against the module's promised surface**, not against whatever the
   implementation ended up named — a test derived from the finished file pins
   nothing.
4. Edit `tests/test_agent_freeze.py` `_install` + imports + docstring.
5. Edit the `tests/test_freeze_engine_live.sh` comment.
6. Run the verification below. Any failure is a defect in this refactor — the
   suite was green before it.

### Post-phase (risk mitigations)

1. `[note_shared_surface_to_t1705_5]` After the change is committed, send a note
   to the blocked sibling:
   `./ait note 1705_5 --from 1738 --with-live --file -`, body recording:
   the module path `.aitask-scripts/lib/agent_frozen_ops.py`; its exported
   surface (`store`, `store_show`, `nonce_from`, `run`, `pane_facts`,
   `pane_location`, `set_option`, `unset_option`, `respawn`, `int_or_zero`,
   `test_mode`, `make_fail_at`, `pause_at`, `StageFailure`, `SESSIONS_SH`, the
   four `EXIT_*` codes); the seam rule (call functions through the module —
   `frozen_ops.store(...)` — never import-alias `store`, and swap
   `agent_frozen_ops.store` / `agent_frozen_ops._TMUX` in
   `tests/test_agent_restore.py`); the failure seam idiom
   `_fail_at = frozen_ops.make_fail_at("AITASKS_RESTORE_FAIL_AT")`; and that
   `restore_ack_grace()` is a candidate for `agent_frozen_ops` rather than
   `agent_freeze.py`, since the latter would make the coordinator import the
   repair module for one accessor. Verify the output carries
   `NOTE_APPENDED:<id>|<path>`.
2. `[align_p1705_5_plan_with_shared_module]` Edit
   `aiplans/p1705/p1705_5_restore_and_repick_flows.md` so its durable record
   matches the shipped module: in step 3's seam bullet (~line 439) replace
   "reusing `agent_freeze._test_mode` / `_fail_at` / `_pause_at` shapes" with a
   reference to `lib/agent_frozen_ops` (`make_fail_at`, `pause_at`,
   `test_mode`); in `## Files`, add `lib/agent_frozen_ops.py` as an existing
   shared dependency of the new `lib/agent_restore.py`, and note against the
   `agent_freeze.py` "grace accessor only" row that `restore_ack_grace()`
   should be reconsidered for `agent_frozen_ops.py`. Do **not** change any other
   decision in that plan. Commit with `./ait git`.

## Verification

```bash
python3 tests/test_agent_frozen_ops.py       # the shared-surface contract
python3 tests/test_agent_freeze.py           # fast inner loop
bash tests/run_all_python_tests.sh           # includes the inventory test
bash tests/test_no_raw_tmux.sh
bash tests/test_freeze_engine_live.sh        # from OUTSIDE the -L ait server
```

**Prove the contract test can fail** before trusting it — a green surface pin
that pins nothing is worse than none. Temporarily (a) rename one export the
freeze engine never calls (`test_mode` → `_test_mode`) and confirm case 1
fails; (b) add `_store = frozen_ops.store` to `agent_freeze` and confirm case 4
fails; then revert both.

**Tmux preflight (inherited from t1705_5):** `test_freeze_engine_live.sh` calls
`require_clean_ait_server`, which refuses to run from inside tmux or while the
dedicated `-L ait` server holds any pane. Run it from a shell outside that
server.

Behaviour-preservation bar: no **existing** test edit may weaken an assertion.
The only permitted edits to existing tests are the seam re-point in `_install`,
the added import, and two comments. `tests/test_agent_frozen_ops.py` is new and
adds coverage.

## Post-implementation

Step 9 (Post-Implementation) applies as usual: commit, merge, archive.

## Risk

### Code-health risk: medium
- ~60 mechanical call-site rewrites inside a shipped, load-bearing 1075-line
  module (`agent_freeze.py`); a partially-applied rewrite could change
  behaviour on a path the unit fakes do not reach (`freeze_all`,
  `_write_observation`, `main`) · severity: medium · → mitigation: none — the
  existing unit suite drives the transaction with fakes and the live suite
  drives freeze + reconcile end-to-end; both must stay green unmodified
- The cross-module test seam is two mutable module globals
  (`agent_frozen_ops.store`, `agent_frozen_ops._TMUX`) reached by late binding.
  An import-time alias in either engine silently bypasses the swap — the rule
  is documented in the module docstring, but it is an implicit contract, not an
  enforced one. Mitigating factor: a bypassed `store` makes the existing
  `_FakeStore.verbs()` assertions fail loudly rather than pass wrongly ·
  severity: low · → mitigation: covered in-plan — `tests/test_agent_frozen_ops.py`
  cases 2/3 pin late binding and case 4 fails on any engine module that binds
  a global to the original `store` / `_TMUX` object
- A third module joins the `frozen` family (`agent_sessions` /
  `agent_freeze` / `agent_frozen_ops`), so a reader must now know which of the
  three owns a given helper · severity: low · → mitigation: none — the new
  module's docstring states its ownership boundary and the one-way arrow

### Goal-achievement risk: low
- The task exists to unblock t1705_5, but `aiplans/p1705/p1705_5_*.md` still
  names `agent_freeze._test_mode` / `_fail_at` / `_pause_at` as the shapes to
  reuse and still places `restore_ack_grace()` in `agent_freeze.py`. If that
  record is not corrected, the coordinator can still be built against
  `agent_freeze`'s privates and the fork this task prevents reappears ·
  severity: medium · → mitigation: inline post-phase
  note_shared_surface_to_t1705_5, inline post-phase
  align_p1705_5_plan_with_shared_module
- The extracted surface is scoped to the risk bullet's members plus their
  inseparable companions; `_epoch` / `_stale_grace` / `restore_ack_grace` are
  deliberately left in `agent_freeze.py`, so t1705_5 may still need one more
  member moved · severity: low · → mitigation: inline post-phase
  note_shared_surface_to_t1705_5
- Three promised exports (`test_mode`, `SESSIONS_SH`, `PANE_FACT_FORMAT` /
  `PANE_FACT_KEYS`) have no caller in `agent_freeze` after the move, so nothing
  in the existing suite would catch a rename or omission — it would surface
  only when t1705_5 is written against a name that is not there · severity:
  medium · → mitigation: covered in-plan — `tests/test_agent_frozen_ops.py`
  case 1 (surface pin) and case 5 (one-way arrow)

### Planned mitigations

- timing: inline post-phase | name: note_shared_surface_to_t1705_5 | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — t1705_5's record still points at `agent_freeze` privates | desc: `ait note` to t1705_5 carrying the shared module path, its surface, the seam/install rule, the `make_fail_at` idiom, and the `restore_ack_grace()` placement question
- timing: inline post-phase | name: align_p1705_5_plan_with_shared_module | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the durable sibling plan still names `agent_freeze._test_mode` / `_fail_at` / `_pause_at` | desc: Update `aiplans/p1705/p1705_5_restore_and_repick_flows.md` step 3's seam bullet and `## Files` to name `lib/agent_frozen_ops.py`
