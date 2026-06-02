# Cross-Repo Coordination — Dogfooding Retrospective (t832_6)

Retrospective audit of the cross-repo coordination plumbing shipped by the
t832 decomposition (children t832_1–t832_5, t832_7, t832_8). It records what
was exercised end-to-end against a real sibling repo, what worked, what
friction surfaced, and which follow-ups (if any) are warranted.

- **Driven by:** t832_6 (`retrospective_dogfooding_evaluation`).
- **Date:** 2026-06-01.
- **Repos:** `aitasks` (this repo) ↔ `aitasks_mobile`
  (`/home/ddt/Work/aitasks_mobile`, a real `ait`-enabled KMP repo carrying the
  applink/QR-pairing work: `QrUrl`, `PairClient`, `ConnectionDBO`).

## Methodology — controlled, low-footprint dogfood

The exercise was scoped to match the task's `effort: low` and the audit-only
planning convention. Rather than driving a full applink wire-protocol bump
across both repos (which would leave permanent paired artifacts), the surfaces
were exercised as follows:

- **Read-only surfaces** were run against the sibling repo's *existing* tasks
  and source files — no creation needed.
- **Mutating surfaces** were exercised minimally with a single disposable local
  probe task (`t895`, since deleted) and a label add/remove round-trip on a
  sibling task (reverted). No permanent cross-repo artifacts remain; both repos
  were verified clean afterward.
- **TUI surfaces** (`ait board` cross-repo navigation) are interactive and are
  covered by the manual-verification checklist in **t889** / **t887**; they are
  not re-driven here.

## Pre-existing friction was already captured

A key finding: the t832 children were diligent about filing friction *inline*
as they implemented. The two upstream defects flagged in the archived sibling
plans are already resolved, and several follow-ups already exist. The
retrospective therefore correctly trends toward **audit-only** — most friction
is already tracked, and the dogfood surfaced no *new* defects.

Already-tracked items (do **not** re-file):

| Item | Origin | Status |
|------|--------|--------|
| Board multi-ref picker keyboard-nav (Tab leaked to board search) | p832_9 defect | Fixed in t886; manual verification pending in **t889** |
| `keybinding_registry.py` crash on malformed `userconfig.yaml` | p832_8 upstream defect | Fixed — `load_user_overrides()` now catches `yaml.YAMLError` and degrades to "no overrides" |
| `xdeprepo` interactive create UX | sibling follow-up | **t857** (manual verification) |
| `aitask_create` skill cross-repo port | sibling follow-up | **t858** (Postponed) |
| brainstorm cross-repo project references | sibling follow-up | **t872** (Implementing) |
| Cross-repo manual-verification carryover | sibling follow-up | **t887** (Implementing — verifies this retrospective) |

## Surface-by-surface findings

### t832_1 — `aitask_query_files.sh --project <name>`
**What worked.** All subcommands honor the `--project` prefix and re-exec into
the sibling repo correctly:
- `--project aitasks_mobile resolve 13` → `TASK_FILE:aitasks/t13_qr_pairing_screen_in_aap.md` + `HAS_CHILDREN:4`.
- `task-status 13` → `STATUS:Ready`; `child-file 13 6` → resolves the active child path; `sibling-context 13` → aggregates archived plans + pending siblings.
- Negative paths are clear: an unregistered project name dies with a
  `Run \`ait projects add\`` hint (exit 1); a non-existent task id returns
  `STATUS:NOT_FOUND` (exit 0).

**Friction.** None. (A `child-file 13 1` returning `NOT_FOUND` is *correct* —
children 1–5 are archived; only 6–9 are active.)

### t832_2 — `aitask_explain_context.sh --project <name>:<file>`
**What worked.** Both argument forms aggregate the sibling repo's historical
plan context for a cross-repo file:
- `--project aitasks_mobile:shared/.../applink/QrUrl.kt` → surfaced the sibling's
  `t13_4` QR-URL-parser plan with `Staleness: CURRENT`.
- Shorthand `aitasks_mobile#shared/.../applink/PairClient.kt` → surfaced the
  `t13_5` PairClient plan.
The per-project cache + merged formatter call worked transparently.

**Friction.** None with the surface itself. *Observation (out of scope):* the
sibling repo's older plans still use the deprecated `../aitasks/` sibling-path
notation and "sister" terminology (e.g. `p13_2_sister_qr_add_hostname_field`).
That is pre-existing content in the sibling repo, predates the logical-name
notation, and is the sibling repo's own cleanup to make — not a defect in the
t832 tooling.

### t832_3 — `--xdeps` / `--xdeprepo` task creation
**What worked.** Create-time cross-repo validation is real and correct:
- Valid: `--xdeps 13 --xdeprepo aitasks_mobile` created a draft; frontmatter
  emitted `xdeps: [13]` + `xdeprepo: aitasks_mobile`.
- Invalid id: `--xdeps 99999` → `Error: --xdeps id 99999 not found in cross-repo
  project 'aitasks_mobile'.` (exit 1).
- Both-or-neither: `--xdeps` without `--xdeprepo` → clear error (exit 1).

**Friction.** None.

### t832_4 — cross-repo blocking display in `aitask_ls.sh`
**What worked.** With the probe task pointing at the still-`Ready` sibling
`t13`, `aitask_ls.sh -v` rendered:
`t895_dogfood_t832_6_probe.md [Status: Blocked (by aitasks_mobile#13), …]` —
the `<repo>#<id>` blocking marker renders as designed.

**Friction.** Minor / by-design: the `UNREACHABLE` marker (for a stale or
unregistered `xdeprepo`) could not be triggered by simply pointing at a bogus
project, because `aitask_update.sh` *also* validates `--xdeprepo` at update time
and refuses an unregistered repo. `UNREACHABLE` is therefore only reachable when
a once-registered project is later deregistered — a genuinely stale state. This
is defensible (it prevents dangling xdeps at the source) and not worth a
follow-up; noted only so a future reader knows the display path is hard to reach
synthetically.

### t832_5 — `parallel-cross-repo-planning` procedure
**What worked (by inspection + helper test).** Trigger detection is
**metadata-only**: `planning-cross-repo.md` reads the `xdeprepo` scalar via
`aitask_query_files.sh task-file` / `lib/task_utils.sh::read_xdeprepo` and fires
iff it is non-empty. `read_xdeprepo` on the probe returned `aitasks_mobile`,
confirming the trigger would fire. Body text is intentionally *not* scanned, so
an incidental project-name mention in prose does not trip paired planning. The
procedure is read-only (design only); creation is deferred to
`cross-repo-child-assignment.md` post-approval.

**Friction.** None. A full paired-decomposition run was intentionally not driven
(would create real cross-repo artifacts, out of scope for this controlled
exercise).

### t832_7 — `aitask_update.sh --project <name>`
**What worked.** The cross-repo allowlist and guardrails behave exactly as
documented:
- Refused: `--status Implementing` cross-repo → dies directing the user to the
  sibling's own `/aitask-pick` (lock + plan externalization happen there).
- Refused: `--name` rename cross-repo → dies (`rename is not supported
  cross-repo`).
- Allowed: `--add-label` / `--remove-label` round-trip on sibling `t10`
  succeeded and reverted cleanly (labels returned to their original set).

**Friction.** None functionally. Two *observations*, both inherent (not
cross-repo-specific) and not worth a follow-up:
- A label add+remove round-trip still bumps the sibling task's `updated_at`, so
  a "revert" is not a byte-for-byte no-op.
- `--add-label` registers the new label in the *sibling's*
  `aitasks/metadata/labels.txt`; `--remove-label` does not unregister it (the
  registry is append-only, matching local behavior). When probing cross-repo
  this leaves a registry entry in the sibling that must be cleaned up by hand —
  worth being aware of, but consistent with how local label add/remove works.

### t832_8 — `ait board` cross-repo display + navigation
**What worked (per code inventory + already-shipped fix).** The board gathers
cross-repo refs from both `xdeps`/`xdeprepo` frontmatter and body notation,
renders a `🌐 blocked (cross-repo)` indicator, and opens a read-only popup on
`#` (single ref opens directly; ≥2 refs show a picker).

**Friction.** The multi-ref picker keyboard-navigation bug (Tab leaking to the
board search box) was already found (p832_9), already fixed (t886), and its
live re-verification is already queued as a manual-verification checklist in
**t889**. No action here. Live TUI verification is delegated to t889/t887 rather
than re-driven in this retrospective.

## Recommended follow-ups

**No new follow-ups needed.**

Every friction point surfaced during this dogfood is either (a) already fixed
and tracked for verification (board picker nav → t886/t889; keybinding YAML
crash → fixed), (b) already filed (t857, t858, t872, t887), or (c) a by-design
trade-off not worth a task (`UNREACHABLE` reachability, `updated_at` drift on
revert). The shipped cross-repo plumbing behaved as documented across every
scriptable surface exercised. Per the `aidocs/framework/planning_conventions.md`
audit-only convention, the deliverable is this audit with an explicit
no-follow-ups outcome.

The candidate follow-ups the original plan speculated about are resolved or
declined:
- **`ait monitor` cross-repo surfacing** — no friction bit during this exercise;
  not filed. Remains a deferred enhancement from t832 if the gap is felt later.
- **Board project-switch** (full switch vs. read-only popup) — the read-only
  popup carried its weight; the only picker friction (keyboard nav) is already
  fixed. Not filed.
- **xdeps maintenance/repair** — no stale-ref friction surfaced; not filed.
