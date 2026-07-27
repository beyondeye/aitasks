---
Task: t635_34_reconcile_installed_gate_registry.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_30_*.md, aitasks/t635/t635_37_*.md
Archived Sibling Plans: aiplans/archived/p635/p635_33_gate_activation_render_time.md
Base branch: main
Output branch: main
---

# t635_34 — Reconcile installed gate registries + early "no verifier" warning

## Context

Projects seeded **before** t1147 carry a stale `aitasks/metadata/gates.yaml`
missing `verifier` / `kind` / `signal` keys. Their tasks block on
`risk_evaluated` with `blocked: no verifier configured (deferred)`
(`lib/gate_orchestrator.py:254`), forcing a manual
`aitask_gate.sh append <id> risk_evaluated pass` before archival (observed
2026-07-10 in `thinking_app`).

t1147 Part A fixed **new** installs by making `.aitask-scripts/gates_reference.yaml`
canonical, plus a drift guard. This task is the absorbed Part 2 (reconcile) +
Part 3 (early warning) that t635_33 split out, shaped against the
`active_gates` / `rendered_gates` model t635_33 landed.

**Premise correction found while planning — the task body overstates the gap.**
`ait upgrade` runs `install.sh --force`, which routes gates.yaml through
`aitask_install_merge.py merge_yaml` → `config_utils.deep_merge(src, dest)`
with dest winning per-leaf-key. That path **already fills absent keys** at any
depth. So "existing installs remain broken until a reconcile path lands" is
not accurate. The real deficiencies of that path are:

1. it destroys the registry's 113-line schema/edit-protocol comment header
   (`yaml.safe_dump`) and every in-block comment;
2. it requires a full framework version upgrade (downloads a release tarball) —
   there is no way to reconcile without upgrading;
3. it reports **nothing** — dest silently wins, so a project whose `verifier:`
   genuinely diverges from the reference stays diverged with zero notice;
4. it needs **PyYAML**, while `read_registry` is deliberately stdlib-only so
   the gate system works where PyYAML is unavailable — i.e. `ait upgrade
   --force` cannot even run in some of the environments that need the fix.

`ait gates sync-registry` is the targeted, comment-preserving,
conflict-reporting, stdlib-only version. That is the honest justification.
Update the task's Acceptance at Step 7 to say so rather than silently
narrowing it ([[feedback_no_silent_AC_deviation]]).

**Hard constraint following from (4): zero PyYAML anywhere in this path.**
That also rules out "parse with PyYAML, diff, write textually" as a shortcut.

## Decisions taken (confirmed with the user during planning)

- **Warning surface: stderr from `materialize-active`, not a skill edit.**
  The obvious plan-time site — `planning.md`'s End-of-planning terminal step —
  is entirely inside `{%- if 'risk_evaluated' in rendered_set %}`
  (`.claude/skills/task-workflow/planning.md:309-323`), so a warning there is
  invisible under exactly the profiles most likely to be misconfigured
  (`remote`, `rendered_gates: []`). The always-rendered site is `SKILL.md`
  Step 4's `materialize-active` block (`:209-224`, Jinja-free) — but emitting
  from the **helper** gets the same reach with zero render/goldens blast
  radius and fires in every lane (attended, `aitask-pickrem`,
  `aitask-pickweb`) for free.
  *Accepted cost:* the warning is not a documented contract the skill is told
  to act on. Mitigated by making it loud, actionable, and pinned by a test on
  the exact stderr text; promotion to the Step-4 contract is a confirmed
  after-mitigation.
- **Profile reconcile is report-only.** t635_37 owns registry-driven profile
  editing + edit-time validation in the settings TUI.
- **Apply by default, `--dry-run` previews.**
- **`sync-registry` is a subcommand of `aitask_gate.sh`, not a new script** —
  `aitask_gate.sh` is already whitelisted in all 5 touchpoints
  (`aitask_audit_wrappers.sh:296-319`), so this costs zero policy-file churn.

## Working-tree hazard (read before starting)

`.claude/skills/task-workflow/{SKILL.md,planning.md}`,
`.aitask-scripts/lib/profile_editor.py` and
`tests/golden/procs/task-workflow/*` currently hold **uncommitted edits from
another session** (an `output_branch` feature, last written 2026-07-27 ~13:56).
This plan deliberately touches **none** of those files. Stage explicitly by
path at Step 8; never `git add -A`.
See [[project_concurrent_worktree_file_hunks]].

---

## Part 1 — `ait gates sync-registry`

### Step 1 (FIRST, before any refactor) — characterization test

`read_registry` (`gate_ledger.py:845`) has seven behaviours a careless refactor
would silently lose. Pin them **against the current implementation and land
that test first**, so the refactor in Step 2 has a real net rather than an
inspection argument ([[feedback_characterization_flip_contract_deterministic_contention]]):

1. `gate_indent` is **sticky** across a dedent (never reset when the mapping
   deactivates).
2. `cur` **is** reset on dedent, so orphan fields after a dedent are dropped.
3. A duplicate gate header re-assigns `_default_gate_meta()`, wiping the
   earlier block's fields entirely — last wins wholesale, not field-wise.
4. Blank lines inside a block-form `unlocks` do **not** terminate it.
5. `gates: {}` never activates the parser (the regex is `^gates:\s*$`).
6. **Any** column-0 line terminates the mapping — including a `#` comment.
7. `.strip("'\"")` strips any leading/trailing quote chars, mismatched pairs
   included; no inline-comment stripping.

New file `tests/test_gate_registry_parser_quirks.py`, table-driven over a new
text-level entry point `read_registry_text(text)` (so cases need no tempfiles).

### Step 2 — one line-walk, two consumers (`lib/gate_ledger.py`)

`read_registry` fills defaults from `_default_gate_meta()` (`:828`), so
`verifier: ""` and *no* `verifier:` line both parse to `""`, and
`max_retries: 0` is indistinguishable from absent. A fill-vs-conflict decision
keyed off the parsed dict alone is therefore **wrong** — a raw-text probe is
required. Do not fork the parser: extract the walk, build both readers on it.

```python
_SCALAR_GATE_KEYS = ("type", "kind", "description", "verifier",
                     "signal", "signal_target")
_GATE_FIELD_KEYS = _SCALAR_GATE_KEYS + ("blocks_dependents", "max_retries",
                                        "timeout_seconds", "unlocks")

class _RegRec(NamedTuple):
    kind: str          # "open" | "close" | "gate" | "field"
    gate: str
    key: str
    value: str         # raw text after `key:`, .strip()ed, NOT quote-stripped
    ws: str            # LITERAL leading whitespace (tabs preserved —
                       # _indent_width collapses \t to 4 and cannot be inverted)
    line: int
    end: int           # last line of this record (block-form unlocks spans)
    items: list[str] | None

def _walk_registry(lines): ...          # the existing loop, moved verbatim
def read_registry_text(text): ...       # field dispatch over the records
def read_registry(path):                # unchanged signature/return
    ...
    return read_registry_text(fh.read())
```

The `unlocks` block branch must keep advancing the outer index (`i = j`) inside
the generator so both consumers see one line stream; `end` reports the last
**non-blank** consumed line so the writer never inserts after a blank.

Then the layout/presence reader over the same walk:

```python
class GateBlock(NamedTuple):
    name: str
    header_line: int
    header_ws: str            # literal indent of the `name:` line
    field_ws: str | None      # literal indent of the FIRST field line
    fields: dict              # key -> line index (last occurrence)
    raw_values: dict          # key -> raw value text (pre quote-strip)
    last_field_end: int       # insertion anchor (== header_line if no fields)

class RegistryLayout(NamedTuple):
    lines: list[str]; raw: list[str]      # splitlines() / splitlines(keepends=True)
    open_line: int | None                 # first activating `gates:`
    close_line: int | None                # line that terminated it; None => EOF
    close_starts_with_hash: bool
    order: list[str]; blocks: dict
    duplicates: list[str]
    orphan_field_names: list[str]         # parsed "gates" whose name is a field key
```

`orphan_field_names` is free from this walk and is the mis-indent tell (Step 5).

### Step 3 — fill policy

**Governing filter: fill only when the reference's *parsed* value differs from
`_default_gate_meta()`'s default for that key.** This falls out cleanly and
does the right thing where it matters — `blocks_dependents: false` and
`max_retries: 0` are never written (pure churn, identical to absent), while
`blocks_dependents: true` and `max_retries: 1` are.

| key | policy | why |
|---|---|---|
| `verifier` | fill / CONFLICT | the t1147 defect itself. A project that deliberately wrote `verifier: ""` is a **CONFLICT, never a fill** — this is the case that makes the presence oracle load-bearing. |
| `kind` | fill / CONFLICT | absent `kind: procedure` makes the headless engine try to shell-exec a *skill name* instead of deferring |
| `type` | fill / CONFLICT | a gate with no `type` is neither human nor procedure and falls into the "no verifier" trap even after a verifier is filled. Present-and-different (`human` vs `machine`) is never overwritten. |
| `signal`, `signal_target` | fill / CONFLICT | absent = an async human gate the headless lane cannot pend or sign |
| `max_retries` | fill / CONFLICT | widening 0→1 is harmless |
| `timeout_seconds` | fill / CONFLICT | absent = **unbounded**. Filling 600 can newly kill a slow build — an unbounded hang in the headless engine is worse, and `--dry-run` + the `FILLED:` line make it visible. **Call this out in `--help`.** |
| `blocks_dependents` | fill / CONFLICT | filling `true` does change dependency-unblock — but `ait upgrade --force` already performs exactly this fill, silently and while destroying comments. Doing it *with* a `FILLED:` line and a preview is strictly better than the status quo it replaces. |
| `description` | fill when absent, **never CONFLICT** | zero machine semantics (only consumer is the display string in `format_list:965`). A reworded description would emit a CONFLICT on every run forever, training people to skim the report — and the report is the product. |
| `unlocks` | **never fill, either direction** | `None` (linear default) and `[]` (terminal) are deliberately distinct (`gate_ledger.py:831-835`). Report only, as `CONFLICT:<gate>.unlocks:(absent)\|[a, b]` — `(absent)` is the honest project side. |

The fill allowlist is a hard-coded tuple, and a test asserts it is a subset of
`_default_gate_meta().keys()` — a key the parser cannot round-trip must never
be written, or the writer emits text `read_registry` silently drops while the
drift guard reports parity.

Project-local gates absent from the reference: untouched, unreported.

**Documented asymmetry on schema growth.** A key the reference gains that is
*not* in `_GATE_FIELD_KEYS` is carried faithfully into a `NEW_GATE` copy (the
lexical extent copies everything) but is **never filled into an existing
gate** (fills are allowlist-driven). That is the safe direction — the writer
must never emit a key `read_registry` cannot consume — but it is a real
limitation and must not be a surprise. Two things make it explicit:

- a test pins the asymmetry directly (new-gate copy carries the unknown key;
  the same unknown key against an *existing* gate produces no `FILLED:` line);
- **a drift guard asserts `_GATE_FIELD_KEYS` covers every key appearing in
  `gates_reference.yaml`** — so adding a key to the reference without teaching
  the parser fails loudly rather than silently half-propagating. That is the
  same edit the parser needs anyway, since `read_registry` must learn a key to
  consume it at all ([[feedback_derive_dont_duplicate_with_guard]]).

### Step 4 — the textual writer

- **Splice, never re-join.** Read with `open(path, newline="", encoding="utf-8")`
  so universal-newline translation doesn't normalise CRLF before you see it;
  build output from `splitlines(keepends=True)` and `"".join(...)`. A `"\n".join`
  silently rewrites CRLF files wholesale and mangles `\x85` / ` `.
  Inserted lines carry the file's **dominant** terminator.
- **Copy raw value text, never re-serialize** — so `signal_target:
  ".aitask-gates/<task-id>/<gate>.signed"` keeps its quotes and a value
  containing `#` keeps parsing identically on both sides. Invariant to test:
  after a fill, `read_registry(project)[g][k] == read_registry(reference)[g][k]`.
- **Insert at `last_field_end + 1`** — after the last *field* line, not the last
  line of the block. In this file's own style comments *precede* what they
  annotate (`risk_evaluated`'s 5-line note sits between `blocks_dependents:`
  and `verifier:`), so a trailing comment introduces the *next* thing;
  inserting before it keeps that reading and never orphans a comment.
  Gate with no fields → `header_line + 1`. Multiple fills → one contiguous
  group in the **reference's** key order (deterministic output).
- **Indent resolution — a defined, layered, deterministic policy.**
  `field_ws` is `None` for a header-only gate (`  g:` with nothing under it),
  and a project may legitimately have no observed field indentation at all, so
  "use the gate's own `field_ws`" is not a total function. Resolve in order:

  1. **Gate has fields** → that gate's own literal `field_ws`. A gate whose
     block indent differs from its siblings needs no guard — YAML only requires
     consistency *within* a block.
  2. **Header-only gate, ≥1 other gate in the file has fields** → `header_ws +
     unit`, where `unit` is the **dominant observed delta**
     `field_ws[len(header_ws):]` across gates whose `field_ws` actually
     `startswith` their `header_ws` (gates failing that test are excluded from
     the vote); ties break to first-in-file-order. This is *observed house
     style*, not a guess.
  3. **No gate in the file has any field, but ≥1 gate header exists** →
     `header_ws + "  "`. Two spaces deeper than an observed header is
     *provably* `> gate_indent`, so the inserted line can never be re-read as a
     sibling gate — which is the only correctness property that matters here.
     Emit a stderr note that the indent was derived.
  4. **Zero gate headers inside the mapping** (a bare `gates:` with nothing
     under it) → **fail closed, exit 4**. With nothing observed, both the gate
     and field indent would be invented, and inventing them is the
     silent-corruption class. Creating a registry from scratch is `ait setup`'s
     job.

  The same ladder supplies `dst_gate_ws` / `dst_field_ws` for `NEW_GATE`
  re-indentation. Every derived case is still gated by the post-write re-parse
  (below), so a wrong derivation aborts the write rather than landing.
- **`NEW_GATE`: copy the reference block's full lexical extent**, not
  `[header_line .. last_field_end]`. `last_field_end` is derived from records
  the walk yields, and the walk only recognises `key:` lines (plus `- item`
  lines under `unlocks` specifically). A future reference key carrying a
  **block list** (`env:` / `requires:` with `- item` lines) as the *last* field
  of a gate would have its items silently truncated from the copy.
  Define the extent lexically instead: from the gate header to the last line
  before the next line at indent ≤ `gate_indent` (or the mapping close / EOF),
  then trim trailing blanks. That captures **all** indented content — comments,
  unknown scalar keys, block lists, nested mappings — with zero dependency on
  the key allowlist, and removes the schema-evolution coupling entirely.
  Record it as `block_end` on `GateBlock` alongside `last_field_end` (which
  remains the *insertion* anchor for fills). In-block comments come along for
  free (they follow each header in this file), and we never reach backwards
  past the header.
  **Re-indentation is mandatory, not cosmetic.** The reference is 2-space
  gate / 4-space field; pasted verbatim into a 4/8 project the parser sets
  `gate_indent = 4`, the pasted header at 2 still reads as a gate, and its
  fields at 4 satisfy `4 <= 4` and become **sibling gates named `type`,
  `description`, `verifier`** — silent catastrophic corruption. Re-map
  header-indent → project header indent, field-indent → project field indent,
  deeper → field indent + the extra width.
- **Append point:** `close_line` if the mapping was terminated, else EOF,
  backing up over trailing blanks so the separator stays between the mapping
  and the next top-level key. If the last line has no terminator, terminate it
  first.
- **Post-write self-verification — do not skip.** Re-parse the candidate text
  before writing: gate set changed only by intended `NEW_GATE`s; every intended
  fill now parses equal to the reference's parsed value; every other
  `(gate, key)` byte-identical to before; layout still activates with no new
  duplicates/orphans. Any mismatch → **write nothing**, exit 6, dump the diff.
  Then `_atomic_write(os.path.realpath(path), new_text)`.

  **Accurate rationale for `realpath` (an earlier draft of this plan got it
  wrong).** In the live layout `aitasks` is a *directory* symlink
  (`aitasks -> .aitask-data/aitasks`) while `gates.yaml` is a regular file —
  path traversal resolves the directory link, so plain `_atomic_write` already
  behaves correctly there, exactly as its docstring (`gate_ledger.py:357-364`)
  states. `realpath` buys two other things: if `gates.yaml` itself is ever a
  **file** symlink, `os.replace` onto the link path would *destroy the link*
  and leave a regular file, whereas resolving first updates the target and the
  link survives; and it keeps the adjacent tempfile on the target's filesystem,
  so the rename stays atomic across a cross-device link.

### Step 5 — fail-closed matrix (write nothing, nonzero exit)

| condition | exit | why |
|---|---|---|
| reference missing / unreadable / not a regular file | 3 | "couldn't look" must never render as `NOOP` |
| reference parses to **zero** gates | 3 | a truncated reference would otherwise report a clean `NOOP` |
| project registry missing / not a regular file | 3 | this is a reconciler, not an installer — `install.sh:499-507` owns creation |
| non-UTF-8 bytes | 3 | |
| no `gates:` activation, incl. a UTF-8 **BOM** (`﻿gates:` fails `^gates:`) | 3 | name the BOM cause explicitly; do **not** open with `utf-8-sig`, which would strip it on read and silently drop it on write |
| `gates: {}` | 3 | the parser never activates, so we have zero information about the file; rewriting `{}` into block form is a structural edit, not additive |
| bare `gates:` with **zero gate headers** under it | 4 | neither gate nor field indent is observable; inventing both is the silent-corruption class (Step 4 ladder, rung 4) |
| **duplicate gate name** in the project | 4 | the parser keeps the last and wipes the earlier block, so fill/conflict would be computed against a partial view and the anchor targets only one block. No correct additive edit exists — refuse loudly. (Duplicate *field* keys within one gate is fine: last wins, presence holds.) |
| a parsed gate name ∈ `_GATE_FIELD_KEYS` (mis-indent tell) | 4 | the fields already became gates |
| **the line terminating the mapping starts with `#`, and indented `name:` lines follow it** | 4 | **the worst available failure mode.** `^\S` deactivates on `#`, so a project with `# --- local gates ---` mid-mapping parses as only the gates above it — and sync would append **duplicates of gates already in the file** |
| lock timeout | 5 | `registry_lock.sh` invariant 1: never proceed unlocked |
| self-verification mismatch | 6 | Step 4 |
| no python interpreter | die | this verb is python-only (like `deps-unblock` / `archive-ready`); note it in the `aitask_gate.sh` header, whose stated convention is bash-first |

**Exit 0 for every completed run** — `NOOP`, applied, or conflicts-reported
alike — so a caller cannot read "I did work" as failure. A CI-style
nonzero-on-drift belongs in a later `--check` flag, not overloaded onto
`--dry-run`.

**`NOOP` is printed only** when the run completed, read both files, and
produced zero other report lines. It must never appear because something could
not be read — otherwise a broken install reads as "you're in sync", which is
the exact t1147 failure class this command exists to catch.

### Step 6 — CLI verb (`aitask_gate.sh`)

`sync-registry [--dry-run] [--registry <file>] [--reference <file>]`, following
the `cmd_materialize_active` house style (`:644-782`): flag `while`/`case` loop
with the positional absorbed by `*)`. The bash arm is a **pass-through** — the
python arm prints the report vocabulary and nothing else, so there is no
`sed -n 's/^KEY://p'` layer to maintain.

**Add `REFERENCE="${AIT_GATES_REFERENCE:-$SCRIPT_DIR/gates_reference.yaml}"`.**
This is a design requirement, not test convenience: the fixture pattern
symlinks the real `.aitask-scripts`, so without the override every test runs
against the live reference — brittle, and the edge-case tests are simply
unwritable. (`TASK_DIR` and `PROFILES_DIR` are already env-overridable.)

Serialized with `lib/registry_lock.sh` —
`registry_lock_acquire "/tmp/aitask_registry_sync_<cksum-of-abs-path>" 10`,
mirroring `acquire_gate_lock`'s `/tmp` convention (`:71-73`) rather than
dropping a lock dir into the git-tracked data worktree. It serializes concurrent
*syncs* only; readers need no lock because `os.replace` is atomic and no reader
ever sees a torn file — state that in the comment so nobody later "fixes" it.

**No auto-commit.** Unlike `materialize-active` (whose tuple must reach other
checkouts to be enforced), a registry change is review-worthy and the report is
the deliverable. Print a one-line stderr hint naming `./ait git add
aitasks/metadata/gates.yaml`. This is a deliberate divergence from the
neighbouring verb's `_persist_task_file` convention.

Report vocabulary (deterministic order: gates in reference file order, keys in
reference-block order, `PROFILE_UNKNOWN` sorted by stamp/key/gate):

```
FILLED:<gate>.<key>=<value>
CONFLICT:<gate>.<key>:<project>|<reference>
NEW_GATE:<gate>
PROFILE_UNKNOWN:<profile>.<key>:<gate>
NOOP
```

**Post-fill verifier probe:** after filling a `verifier:`, check
`$SCRIPT_DIR/aitask_gate_<x>.sh` exists; if not, `warn` on stderr. Filling
`aitask-gate-build` into a project whose framework copy predates that script
arms a gate that hard-fails at run time. Warn, don't fail, don't add a stdout verb.

### Step 7 — profile scan (report-only)

Enumerate with the canonical scanner `./.aitask-scripts/aitask_scan_profiles.sh`
(parses `PROFILE|<filename>|…`; already handles the `local/` prefix) rather than
globbing. Read the two **raw** key lists per profile with
`_frontmatter_has_key` + `_read_frontmatter_list_from_text` — not
`_read_profile_rendered_gates`, which returns the resolved ceiling and would
mask which key named the gate. Report `<profile>` in `_profile_stamp_name` form
(`aitask_gate.sh:610`) so `local/foo` is distinguishable from `foo`.

**Compute against the post-sync name set** (`registry_names ∪ new_gate_names`),
and use the same union under `--dry-run`. Otherwise a profile naming `lint` on
a registry missing `lint` reports `PROFILE_UNKNOWN` on the very run that adds
`lint`, and dry-run output diverges from apply output — which would kill the
cheapest idempotence test available.

Run `_validate_profile_gate_list_syntax` rather than letting
`_read_frontmatter_list_from_text` silently return `[]` (a silent `[]` hides
gates from the scan). A malformed profile warns on stderr and continues — it
must never block a correct registry fill. Missing profiles dir → skip silently.

### Step 8 — `ait` dispatcher registration (four edits, all easy to miss)

1. `ait:310` — new `sync-registry)` case arm.
2. `ait:311` — the inline `--help` string.
3. `ait:312` — the unknown-subcommand `Available:` list.
4. `ait:51-58` — the top-level `show_usage` "Gates:" block (verb padded to 15).

Plus `show_help()` and `main()` in `aitask_gate.sh`.
**`tests/test_gate_cli_wiring.sh:31` asserts the literal string
`"run | unlocked | list | status"`** and breaks on edit 2 — update it in the
same change.

---

## Part 2 — Early "no verifier" warning

### 2a. The shared predicate (`lib/gate_ledger.py`)

```python
def unverifiable_reason(gate: str, registry: dict[str, dict]) -> str | None:
    """Why an ENFORCED gate can never be satisfied — None when it can.

    Mirrors the last arms of gate_orchestrator.blocked_reason (:249-255):
    a human gate legitimately has no verifier (it pends on a signal) and a
    procedure gate is run by the attended agent, so neither is a defect.
    """
    if gate not in registry:
        return "no registry entry"
    meta = registry[gate]
    if meta.get("type") == "human":
        return None
    if meta.get("kind") == "procedure":
        return None
    if not meta.get("verifier"):
        return "no verifier configured"
    return None
```

Exposed as a `gate_ledger.py main()` arm
`unverifiable-gates <registry_file> <gates_csv>` printing
`UNVERIFIABLE:<gate>:<reason>` lines — a **new arm** rather than an extra line
on `compute-active`'s output, so the load-bearing digest/tuple path
(`cmd_compute_active`, shared with `active-gates-status`) is untouched.

**`blocked_reason` is switched to call it — one seam, not a parallel
reimplementation.** `gate_orchestrator.py` already does `import gate_ledger as
gl` (`:47`), and by `:254` the `human` (`:249`) and `procedure` (`:251`) arms
have already returned, so

```python
if not registry.get(g, {}).get("verifier"):     # :254 today
```

becomes `if gl.unverifiable_reason(g, registry):` — **behavior-identical** on
that path (for a machine/command gate the predicate reduces to exactly
`gate not in registry or not verifier`, and the missing-entry case already fell
through the same way). The orchestrator's pinned strings are untouched, and a
matrix test pins the correspondence
([[feedback_reuse_canonical_seam_not_parallel_reimpl]]).

### 2b. Emission site

In `cmd_materialize_active`, after the active set is computed, and **only** for
gates in that set — the genuine "declared-and-active-but-unconfigured" case.
A gate outside the profile's rendered ceiling is already filtered from
`active_gates` and never enforced, so it must not warn (t635_33's model).

`warn` (`lib/terminal_compat.sh:21`) prefixes `Warning: ` and writes to stderr:

```
Warning: materialize-active: active gate 'risk_evaluated' has no verifier
configured in aitasks/metadata/gates.yaml — it will block archival. Run
`ait gates sync-registry` to reconcile the registry.
```

**stdout stays exactly one status line** — t635_33's contract.

**Fixture noise:** `new_fixture()` in `tests/test_gate_active_gates.sh`
(`:43-51`) writes a `gates.yaml` whose `risk_evaluated` has no `verifier:`, so
every materialize test there would start warning. Add `verifier:
aitask-gate-risk` to that fixture (quiet, and representative of a healthy
install) and let the new warning test build the verifier-less variant
explicitly — which also makes the new test discriminating. Re-run all 87
asserts after the change. The existing `2>&1` captures (`:175`, `:183`, `:199`)
are error paths that `die` before this site and use `assert_contains`, so they
are unaffected — verified during planning.

---

## Docs

- `.aitask-scripts/gates_reference.yaml` header (`:8-15`) — the EDIT PROTOCOL
  block prescribes a manual `cp`; point it at `ait gates sync-registry` for the
  *downstream reconcile* direction while keeping the maintainer `cp` for
  refreshing this repo's live registry from the reference. Do not conflate the
  two directions.
- `aidocs/gates/aitask-gate-framework.md:107-125` — add `sync-registry` to the
  consumers list.
- `aitask_gate.sh` file-header subcommand list (`:13-25`) — **already stale**
  (stops at `resume-point`); fix while adding the verb.
- No website page: gates are undocumented on the site and the comprehensive
  sweep is t635_18's scope. `ait --help` + `aitask_gate.sh --help` are the
  user-facing surfaces here.

---

## Tests

### `tests/test_gate_registry_parser_quirks.py` (new, lands FIRST)

The seven characterization cases from Step 1, table-driven over
`read_registry_text`, plus a property check that for every
(gate, fill-eligible key) pair, applying the fill and re-parsing yields the
reference's parsed value exactly.

### `tests/test_gates_sync_registry.sh` (new)

Fixture style of `tests/test_gate_cli_wiring.sh:20-27` (tmpdir, `cp ait`,
symlink `.aitask-scripts`, `( cd "$d" && ./ait gates sync-registry )`) so the
**real user entry point** is exercised
([[feedback_test_real_entrypoint_and_live_acceptance]]). A `sum_of() { cksum <
"$1"; }` helper is the workhorse: every guard test asserts **both** a nonzero
exit **and** an unchanged file, so an implementation that fails loudly *after*
corrupting the file cannot pass.

| # | fixture | asserts | guard proven |
|---|---|---|---|
| 1 | `build_verified` with only `type`+`description` | `FILLED:` for verifier/max_retries/timeout_seconds/blocks_dependents; re-parse == reference; **comment lines byte-identical** (`grep '^ *#' \| cksum`) | the whole point vs `merge_yaml` |
| 2 | `verifier: ""` present | `CONFLICT:...verifier:\|aitask-gate-build`; **file cksum unchanged** | **presence oracle (string)** — a dict-driven impl necessarily rewrites the file |
| 3 | `max_retries: 0` present | `CONFLICT:...:0\|1`; unchanged | **presence oracle (int)** |
| 4 | doctored reference with `unlocks: [x]` | `CONFLICT:...unlocks:(absent)\|[x]`, unchanged; and project `unlocks: []` + reference absent → no line, unchanged | `unlocks` untouchable both ways |
| 5 | registry missing `lint` | `NEW_GATE:lint`; appended block re-parses field-for-field equal; its `#` lines present | new-gate copy incl. comments |
| 6 | project uses 4-space gate / 8-space field indent | inserts use 8; **parse contains no gate named `type`/`verifier`/`description`** | the catastrophic silent-corruption case |
| 7 | tab-indented project | tabs preserved, re-parse OK | literal-indent copying |
| 8 | CRLF fixture | `\r` count == line count after; the **inserted** line ends CRLF | keepends splicing |
| 9 | no trailing newline | last line terminated, appended block follows, re-parse OK | keepends splicing |
| 10 | duplicate `build_verified:` blocks | nonzero, unchanged, stderr names the gate | fail-closed |
| 11 | column-0 `#` mid-mapping with gates after it | nonzero, unchanged | **the duplicate-append catastrophe** |
| 12 | `gates: {}` | nonzero, unchanged | fail-closed |
| 13 | no `gates:` key | nonzero, unchanged | fail-closed |
| 14 | `AIT_GATES_REFERENCE=/nonexistent` | nonzero **and stdout does NOT contain `NOOP`** | **the most important negative test** — "silent no-op hides a broken install" |
| 15 | reference containing only `gates:` | nonzero | empty-reference guard |
| 16 | fixture 1 + `--dry-run` | stdout byte-identical to the apply run's stdout; file unchanged | dry-run fidelity + post-sync `PROFILE_UNKNOWN` union |
| 17 | run fixture 1 twice | second prints exactly `NOOP`; cksum identical to post-run-1 | idempotence + deterministic ordering |
| 18 | `fast.yaml` `default_gates: [not_a_gate]`, `local/x.yaml` `rendered_gates: [nope]` | both `PROFILE_UNKNOWN` lines incl. the `local/x` stamp; **both profile files unchanged** | report-only, `local/` scanned |
| 19 | reworded `description` | **no** `CONFLICT`; unchanged | the exemption is deliberate, not an oversight |
| 20 | pre-created lock dir with a live PID, 1s timeout | nonzero within timeout, unchanged | fail-closed, not first-writer-wins |
| 21 | `ait gates --help` | contains `sync-registry` | dispatcher wiring |
| 22 | **header-only gate** (`  build_verified:` with no fields) alongside siblings that have 4-space fields | fill lands at 4 spaces; re-parse shows a *field*, not a new gate | indent ladder rung 2 (observed house style) |
| 23 | **every** gate header-only (no field line anywhere in the file) | fill lands at `header_ws + 2`; re-parse shows a field, not a gate; stderr notes the derived indent | indent ladder rung 3 — the case that would otherwise crash on `field_ws is None` |
| 24 | bare `gates:` with zero gate headers, reference-only gates pending | nonzero, file unchanged | indent ladder rung 4 (fail closed, no invention) |
| 25 | **symlinked `gates.yaml` file** → real file elsewhere | after a fill: the path is **still a symlink**, `readlink` unchanged, and the **target's** content changed; a `.tmp` file is left nowhere | `realpath` before atomic replace — the claim was previously untested |
| 26 | **symlinked `aitasks/` directory** (the live repo layout) reproduced in the fixture | fill succeeds, the directory symlink survives, target file updated | the primary deployed layout, previously unverified |
| 27 | **forward-schema reference**: a gate carrying an unknown scalar key *and* an unknown block-list key (`requires:` + `- a`/`- b`) as its **last** field | `NEW_GATE` copy reproduces **every** line re-indented, block-list items included; re-parse equals the reference for all known keys | lexical block extent — `last_field_end` would truncate the list |
| 28 | same unknown key, but against an **existing** project gate | **no** `FILLED:` line for it; file otherwise correct | the documented allowlist asymmetry is deliberate |
| 29 | doctored reference introducing a key absent from `_GATE_FIELD_KEYS` | the coverage drift guard **fails** | adding a reference key without teaching the parser fails loudly |

### Warning tests (extend `tests/test_gate_active_gates.sh`)

22. **Fires** — verifier-less `risk_evaluated` in the active set → stderr
    contains the warning and names `ait gates sync-registry`; **stdout is still
    exactly `MATERIALIZED:risk_evaluated`**.
23. **Does NOT fire** — three distinct negative controls: a human gate with no
    verifier; a `kind: procedure` gate; and a gate **declared but
    profile-filtered** (not in `active_gates`) — the last proves the warning
    respects t635_33's ceiling rather than scanning raw `gates:`.
24. **Predicate/orchestrator agreement matrix** — `unverifiable_reason(...) is
    not None` ⟺ `blocked_reason(...)` yields
    `"blocked: no verifier configured (deferred)"`, over five registry shapes.

### Proving the harness itself can fail ([[feedback_prove_test_harness_can_fail]])

- **Assertion-machinery self-test:** run a deliberately-failing `assert_eq` in a
  subshell with throwaway counters and assert it registered `FAIL=1` — catches a
  stubbed `tests/lib/asserts.sh` where everything "passes" because nothing is
  checked.
- **Assertion-count pin:** end the file with `assert_eq "assertion count" "<N>"
  "$TOTAL"` — catches the other mode, where the body aborts early (a `set -e`
  trip, a failed `mktemp`) and a whole block silently never runs while the
  summary still reads green.
- Confirm `bash tests/test_gates_sync_registry.sh; echo $?` prints `1` when the
  presence oracle is reverted to a plain `read_registry` lookup (test 2 must
  fail **and the suite must exit 1**), then restore by undoing the edit — not
  `git checkout --` ([[feedback_negctrl_restore_without_git_checkout]]).

---

## Verification

- `bash tests/test_gate_registry_parser_quirks.py` and
  `bash tests/test_gates_sync_registry.sh` pass.
- `bash tests/test_gate_cli_wiring.sh` (updated help string) passes.
- `bash tests/test_gates_reference_drift.sh` still passes (10/10) — this repo's
  live registry is byte-identical to the reference, so `sync-registry` here must
  report `NOOP` and write nothing. **Extend its Part-3 consumer-wiring assertion**
  (currently pins `install.sh` + `aitask_setup.sh` as the only readers of
  `gates_reference.yaml`) to include `aitask_gate.sh`. Also add the one-line
  reference lint the design surfaced: no unquoted `#` in a reference value,
  where `read_registry` and PyYAML would disagree.
- `bash tests/test_gate_active_gates.sh` (87 + new asserts),
  `tests/test_gate_orchestrator.sh` (40), `tests/test_gate_ledger.sh`,
  `tests/test_gate_ledger_python_parser.py`,
  `tests/test_gate_orchestrator_registry.py` all pass.
- `shellcheck .aitask-scripts/aitask_gate.sh`; `./ait --help` renders.
- **Live smoke:** fixture install whose `gates.yaml` has zero `verifier:` keys →
  picking a task under `fast` emits the stderr warning → `ait gates
  sync-registry` fills additively, reports a customised value as `CONFLICT`, and
  preserves every comment line.

## Risk

### Code-health risk: medium

- **The `read_registry` refactor sits under every gate consumer** —
  `format_list`, `required_unblock_gates`, `dependents_status`,
  `unmet_procedure_gates`, `read_task_gate_state`, the orchestrator (`:359`,
  `:543`), `aitask_gate_pass.sh:53`, `aitask_board.py:1026` · severity: medium
  · → mitigation: the seven-quirk characterization test lands **first**, the
  walk moves verbatim, and five existing suites plus the full-field reference
  parity test are the net.
- **First purpose-built writer for `gates.yaml`; three silent-corruption paths
  exist** — a mis-indented `NEW_GATE` paste turning fields into gates; a
  column-0 `#` causing duplicate appends; and an *unobservable* field indent
  (header-only gates) where any invented indentation can re-read as a sibling
  gate · severity: high · → mitigation: the layered indent ladder (observed →
  observed-house-style → provably-deeper → fail closed), explicit
  re-indentation, the `#`-terminator and duplicate/orphan guards, post-write
  re-parse self-verification before **any** write, temp-file + `realpath`
  atomic replace, and a test asserting *both* nonzero exit and an unchanged
  file for every guard.
- **Schema evolution can silently half-propagate.** A reference key outside
  `_GATE_FIELD_KEYS` reaches new gates (lexical copy) but not existing ones
  (allowlist fills) · severity: low · → mitigation: lexical block extent so
  copies are never truncated, the asymmetry pinned by tests 27-28, and a
  coverage drift guard (test 29) that fails when the reference grows a key the
  parser does not know.
- **Absent-vs-empty must not be decided from parsed values** — getting it wrong
  overwrites a project's deliberate `verifier: ""` opt-out · severity: medium ·
  → mitigation: presence oracle, tests 2 and 3 as discriminating cases, proven
  load-bearing by revert-and-rerun.
- **`materialize-active` is on every pick in every lane**; a stray stdout write
  breaks t635_33's one-line contract · severity: low · → mitigation: stderr-only
  via `warn`, stdout re-pinned by test 22, existing 87 asserts re-run.

### Goal-achievement risk: medium

- **The task body's premise is partly wrong** — `ait upgrade` already fills
  absent keys, so the deliverable is narrower (comment preservation,
  upgrade-decoupling, reporting, no-PyYAML) than "unblock broken installs" ·
  severity: medium · → mitigation: stated in Context; the task's Acceptance is
  updated at Step 7 rather than silently narrowed.
- **The early warning is not a documented skill contract** — it reaches every
  lane via stderr, but no skill instructs the agent to surface it · severity:
  medium · → mitigation: user-confirmed trade-off; the message is
  self-describing and names the repair command;
  `promote_no_verifier_warning_to_step4_contract` promotes it once the
  concurrent `SKILL.md` work lands.
- **Filling `timeout_seconds` / `blocks_dependents` changes runtime behaviour**
  in projects that had neither · severity: low · → mitigation: `--dry-run`,
  an explicit `FILLED:` line per key, and a `--help` note; both are fills
  `ait upgrade --force` already performs silently.
- **Profile reconcile is report-only**, so a typo'd gate name is surfaced but
  not repaired · severity: low · → mitigation: deliberate boundary — t635_37
  owns registry-driven profile editing and edit-time rejection.

### In-task structural guards (not separate tasks)

- Seven-quirk characterization test landed **before** the parser refactor.
- Post-write re-parse self-verification gates every write — including every
  *derived* indent, so a wrong derivation aborts rather than lands.
- Indent ladder is total: every rung is either observed or provably deeper than
  `gate_indent`, and the unobservable case fails closed.
- Both symlink layouts (directory and file) exercised through the production
  write path ([[feedback_test_universal_claim_at_weakest_surface]]).
- `_GATE_FIELD_KEYS` coverage drift guard against the live reference.
- Presence oracle proven load-bearing by a revert-and-rerun negative control.
- Three distinct warning negative controls (human / procedure /
  profile-filtered), so "does not fire" is tested per reason, not in aggregate.
- `unverifiable_reason` ⟺ `blocked_reason` agreement matrix.
- Harness self-test + assertion-count pin.
- Drift-test Part 3 extended to pin `aitask_gate.sh` as a reference reader.

### Planned mitigations

- timing: after | name: gates_sync_registry_live_verify | type: manual_verification | priority: medium | effort: low | addresses: code-health (first registry writer) + goal-achievement (real installed-project shape) | desc: Run `ait gates sync-registry` against a real stale downstream install (not a fixture) — confirm archival unblocks with no manual gate append, every comment line survives, a customised verifier is reported as CONFLICT and left intact, and `--dry-run` changes nothing.
- timing: after | name: promote_no_verifier_warning_to_step4_contract | type: enhancement | priority: low | effort: low | addresses: goal-achievement (warning is not a documented contract) | desc: Once the concurrent `output_branch` edits to `.claude/skills/task-workflow/SKILL.md` are committed, add the stderr no-verifier warning to Step 4's documented parse list and regenerate the 3 SKILL goldens + 3 committed remote prerenders.

## Step 9 (Post-Implementation)

Standard cleanup / archival / merge per task-workflow Step 9. Stage by explicit
path — the working tree carries another session's uncommitted work.
