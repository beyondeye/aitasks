---
Task: t1680_register_fable5_1_claudecode_model.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1680 — Register `claudecode/fable5_1` (Fable 5.1)

## Context

Anthropic released **Claude Fable 5.1**. The framework's `claudecode` model
registry does not know it, so any session running on that model resolves
`implemented_with` to `AGENT_STRING_FALLBACK:claudecode/claude-fable-5-1`
instead of a proper `claudecode/fable5_1`, and per-model verified/usage scores
have nowhere to accumulate.

This is a **register-only** change (t1680 mirrors t966, which registered
`fable5`): the new model is added to the registry but is **not** promoted to
default. Per `aidocs/framework/model_reference_locations.md`, register-only
touches **§1 (core model registry)** and nothing else — no
`codeagent_config.json`, no `DEFAULT_AGENT_STRING`, no docs, no
default-sensitive tests.

No source change is needed for attribution:
`.aitask-scripts/aitask_resolve_detected_agent.sh:81` matches `cli_id` straight
out of `models_claudecode.json`, so resolution works as soon as the entry lands.

## Confirmed model identity

Verified against the bundled `claude-api` skill's current model table:

| field | value |
|---|---|
| `name` | `fable5_1` (registry convention: dots → underscores, cf. `opus4_7_1m`, `fable5`) |
| `cli_id` | `claude-fable-5-1` |
| `notes` | `Fable 5.1 — most capable model, 1M context, 128K output, thinking always on` |

No 1M-context *variant* is announced for this model — 1M is the model's own
context window (and its default), not a separate `[1m]` SKU as it was for
`claude-opus-4-7[1m]` / `claude-opus-4-8[1m]`. So **one** entry, no
`fable5_1_1m`.

---

## Acceptance criterion: reconciled before implementation

The task states *"Both registry copies stay byte-identical in their `models`
array."* **That criterion is already false, for every one of the 12 existing
entries, before this task changes anything.** Measured baseline:

```
byte-identical:   False
name lists equal: True
  opus4_6     differs in: verified, verifiedstats
  sonnet4_6   differs in: verifiedstats
  haiku4_5    differs in: verifiedstats
  opus4_5     differs in: verifiedstats
  sonnet4_5   differs in: verifiedstats
  opus4_7     differs in: usagestats, verified, verifiedstats
  opus4_7_1m  differs in: usagestats, verified, verifiedstats
  opus4_8     differs in: usagestats, verified, verifiedstats
  opus4_8_1m  differs in: usagestats, verified, verifiedstats
  fable5      differs in: usagestats, verified, verifiedstats
  opus5       differs in: usagestats, verified, verifiedstats
  sonnet5     differs in: usagestats, verified, verifiedstats
```

The divergence is **structural and intended**: the metadata copy accumulates
per-model runtime scoring (`verified`, `verifiedstats`, `usagestats`, written by
`aitask_verified_update.sh`), while the seed copy is a pristine template shipped
into new projects. Satisfying the criterion as literally written would mean
deleting the project's scoring history — destructive, and out of scope.

**Amended criterion** (three parts, all machine-checked in Verification below):

- **AC-1 — identity parity.** For every entry, the triple
  (`name`, `cli_id`, `notes`) and the entry *order* are identical in both files.
  This holds at baseline and must still hold after. This is what "the two copies
  agree" actually means for this registry.
- **AC-2 — new entry fully identical.** The `fable5_1` entry is byte-identical
  in both files. (It carries empty `verified: {}` / `verifiedstats: {}` and no
  `usagestats`, so full equality *is* achievable for the new row.)
- **AC-3 — no collateral change.** Every pre-existing entry, in *both* files, is
  byte-identical to a snapshot taken immediately before the apply. This is the
  part that catches the failure mode a new-row-only check would miss: an
  unrelated row silently rewritten.

**One tolerated exception to AC-3, and it must be enumerated, never waved
through:** a *concurrent* agent session can bump `verified` / `verifiedstats` /
`usagestats` in the **metadata** copy mid-task. That is not hypothetical — it
happened during this session (`aitasks/metadata/models_claudecode.json` was
rewritten on disk at 09:05 by another writer). If AC-3 reports a difference, the
check prints it; it may be accepted **only** if every differing key is one of
those three stats fields on an entry other than `fable5_1`, and the accepted
list is named in the Final Implementation Notes. Any difference to `name`,
`cli_id`, `notes`, entry order, or to *any* field in `seed/` is a hard failure —
stop and investigate.

The amended criterion and the measured baseline are recorded in the task's Final
Implementation Notes at Step 8, so the deviation from the task text is on the
record rather than silent.

---

## Implementation

### Pre-phase (risk mitigations)

**`snapshot_registry_baseline`** — step 1 below. Inline pre-phase mitigating the
code-health risk that a collateral row change (including one from a concurrent
session) lands unnoticed: without a pre-apply snapshot, AC-3 has nothing to
compare against.

### 1. Snapshot the baseline (required by AC-3)

Immediately before any write — so the snapshot is not stale — capture both
files and both file modes into the scratchpad:

```bash
SCRATCH=/tmp/claude-1000/-home-ddt-Work-aitasks/75bf18af-20ac-4f5d-a56f-a3fd7d415eae/scratchpad
cp aitasks/metadata/models_claudecode.json "$SCRATCH/base_metadata.json"
cp seed/models_claudecode.json             "$SCRATCH/base_seed.json"
stat -c '%a %n' aitasks/metadata/models_claudecode.json seed/models_claudecode.json \
  | tee "$SCRATCH/base_modes.txt"
```

`base_modes.txt` is the authority for the mode restore in step 5 — each file is
returned to **its own** pre-change mode. (Today: metadata `644`, seed `600`.
`seed/` is mixed — 4 files at `600`, 2 at `644` — so imposing `644` on the seed
copy would be an unrequested policy change, not a repair.)

### 2. Dry-run and review the diff

```bash
./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
  --agent claudecode --name fable5_1 --cli-id claude-fable-5-1 \
  --notes "Fable 5.1 — most capable model, 1M context, 128K output, thinking always on"
```

Confirm the unified diff appends exactly one entry — with `verified: {}` and
`verifiedstats: {}` — to **both** `aitasks/metadata/models_claudecode.json` and
`seed/models_claudecode.json`, and touches nothing else.

(`cmd_add_json`, `.aitask-scripts/aitask_add_model.sh:72-148`, writes both
copies from one invocation, validates with `jq .`, and `mv`s atomically. It
refuses on a duplicate `name` in either file.)

### 3. Apply

Re-run the same command without `--dry-run`.

### 4. Refresh the now-stale `fable5` note (in-file, §1 scope)

`fable5`'s note currently reads `Fable 5 — latest-generation Claude model`.
Registering `fable5_1` makes that claim untrue. Same file, same §1 category, one
string, applied to **both** copies so AC-1 is preserved:

```bash
for f in aitasks/metadata/models_claudecode.json seed/models_claudecode.json; do
  jq '(.models[] | select(.name == "fable5") | .notes) = "Fable 5 — previous-generation Fable model"' \
     "$f" > "$SCRATCH/tmp.json" && mv "$SCRATCH/tmp.json" "$f"
done
```

This is the only step beyond the helper's own output. If you'd rather keep
t1680 strictly mechanical, say so and it is dropped — the stale note is then
flagged in the final report instead. Note it makes `fable5`'s `notes` an
*intended* AC-3 difference: it is enumerated as such in the check below.

### Post-phase (risk mitigations)

**`restore_and_assert_file_modes`** — step 5 below. Inline post-phase mitigating
the code-health risk that both write paths `mv` a `0600` tempfile into place and
narrow permissions invisibly to git. It must be the **last** write-affecting
step, and it asserts rather than assumes.

**`verify_amended_acceptance_criteria`** — Verification 3 below. Inline
post-phase mitigating the goal-achievement risk that the task's literal
"byte-identical" criterion is unsatisfiable and would otherwise be silently
substituted; it machine-checks AC-1/AC-2/AC-3 and enumerates every tolerated
concurrent-stats difference by name.

### 5. Restore file modes — **after every write, then assert**

This runs last, after step 4's `mv`, not between steps 3 and 4. Both
`aitask_add_model.sh` and step 4 `mv` a `mktemp` file (mode `0600`) into place,
so an earlier `chmod` would be silently undone by the later write — and because
git does not track read permissions, nothing in the diff would show it.

```bash
while read -r mode path; do chmod "$mode" "$path"; done < "$SCRATCH/base_modes.txt"
# assert, do not assume:
stat -c '%a %n' aitasks/metadata/models_claudecode.json seed/models_claudecode.json
diff <(stat -c '%a %n' aitasks/metadata/models_claudecode.json seed/models_claudecode.json) \
     "$SCRATCH/base_modes.txt" && echo "MODES_RESTORED_OK"
```

`MODES_RESTORED_OK` must print. If it does not, stop — do not commit.

---

## Verification

```bash
# 1. The model is listed
./.aitask-scripts/aitask_codeagent.sh list-models claudecode | grep fable5_1

# 2. Attribution resolves (must be AGENT_STRING:, not AGENT_STRING_FALLBACK:)
./.aitask-scripts/aitask_resolve_detected_agent.sh \
  --agent claudecode --cli-id claude-fable-5-1
```

### 3. AC-1 / AC-2 / AC-3 — one check, all three, fails loudly

```bash
python3 - "$SCRATCH" <<'PY'
import json, sys
S = sys.argv[1]
NEW = "fable5_1"
STATS = {"verified", "verifiedstats", "usagestats"}
load = lambda p: json.load(open(p))["models"]
cur = {"metadata": load("aitasks/metadata/models_claudecode.json"),
       "seed":     load("seed/models_claudecode.json")}
base = {"metadata": load(f"{S}/base_metadata.json"),
        "seed":     load(f"{S}/base_seed.json")}
fail = []

# AC-1: identity parity (name, cli_id, notes) and order, across the two copies
idm = [(m["name"], m["cli_id"], m["notes"]) for m in cur["metadata"]]
ids = [(m["name"], m["cli_id"], m["notes"]) for m in cur["seed"]]
print("AC-1 identity parity + order:", "PASS" if idm == ids else "FAIL")
if idm != ids:
    fail.append("AC-1")
    for a, b in zip(idm, ids):
        if a != b: print("   ", a, "!=", b)

# AC-2: the new entry is byte-identical in both copies
na = [m for m in cur["metadata"] if m["name"] == NEW]
nb = [m for m in cur["seed"]     if m["name"] == NEW]
ok2 = len(na) == 1 and len(nb) == 1 and na[0] == nb[0]
print("AC-2 new entry identical:", "PASS" if ok2 else "FAIL")
if not ok2: fail.append("AC-2"); print("   ", na, "\n   ", nb)
else: print("    ", json.dumps(na[0], ensure_ascii=False))

# AC-3: no pre-existing entry changed, in either file, vs. the pre-apply snapshot
for copy in ("metadata", "seed"):
    b = {m["name"]: m for m in base[copy]}
    c = {m["name"]: m for m in cur[copy]}
    added, removed = set(c) - set(b), set(b) - set(c)
    if added != {NEW} or removed:
        fail.append(f"AC-3/{copy}/membership")
        print(f"AC-3 {copy}: FAIL  added={added} removed={removed}")
    if [n for n in c if n != NEW] != list(b):
        fail.append(f"AC-3/{copy}/order"); print(f"AC-3 {copy}: FAIL existing order changed")
    for n in b:
        if b[n] == c.get(n): continue
        diffs = {k for k in set(b[n]) | set(c[n]) if b[n].get(k) != c[n].get(k)}
        # tolerated: concurrent runtime-stat bump, metadata copy only
        # intended:  the step-4 fable5 notes refresh, both copies
        tolerated = copy == "metadata" and diffs <= STATS
        intended  = n == "fable5" and diffs == {"notes"}
        tag = "TOLERATED(concurrent stats)" if tolerated else \
              "INTENDED(step 4 notes)"      if intended  else "UNEXPECTED"
        print(f"AC-3 {copy}: {n} changed in {sorted(diffs)} -> {tag}")
        if tag == "UNEXPECTED": fail.append(f"AC-3/{copy}/{n}")
print("AC-3 collateral change:", "FAIL" if any(f.startswith("AC-3") for f in fail) else "PASS")

print("\nRESULT:", "FAILED " + ", ".join(sorted(set(fail))) if fail else "ALL ACCEPTANCE CHECKS PASSED")
sys.exit(1 if fail else 0)
PY
```

Every `TOLERATED` line printed must be copied into the Final Implementation
Notes by name — an unenumerated concurrent bump is not an acceptable pass.

### 4. Tests

```bash
bash tests/test_add_model.sh
bash tests/test_install_merge.sh
```

Both are fixture-isolated (`test_install_merge.sh` builds its registries under
`$TMP`/`$INSTALL_ROOT`), so neither reads the real registry — they verify the
helper, not the data.

---

## Commit split

Two path-scoped commits (never `git add -A` / `git commit -a` — the working
tree carries unrelated in-flight website-docs edits and an untracked test file):

```bash
./ait git add aitasks/metadata/models_claudecode.json
./ait git commit -m "feature: Register claudecode/fable5_1 (Fable 5.1) (t1680)"

git add seed/models_claudecode.json
git commit -m "feature: Sync claudecode/fable5_1 registration to seed (t1680)"
```

Verify each with `git show --stat` that exactly the one intended file landed.

## Explicitly out of scope

Per the task and `model_reference_locations.md` §2–§4: no `promote-config`, no
`promote-default-agent-string`, no edits to `aidocs/codeagents/claudecode_tools.md`,
`website/content/docs/commands/codeagent.md`, or any default-sensitive test. No
change to the seed copy's file mode beyond restoring its own pre-change value.

Related but **not** folded: t967 (fable5 content-safety auto-switch to Opus 4.8
— likely applies to fable5_1 too, stays there) and t1150 (Fable prose invisible
alongside `AskUserQuestion` — already mitigated).

## Step 8 / Step 9 (Post-Implementation)

Final Implementation Notes must record: the amended acceptance criterion and the
measured baseline divergence above, plus any `TOLERATED` concurrent-bump entries
the AC-3 check reported. Then: current-branch mode (profile `fast`, no worktree,
nothing to merge) → gate orchestration for the active `risk_evaluated` gate →
archive `t1680` and `p1680`.

## Risk

### Code-health risk: low
- A collateral change to an unrelated registry row — from step 4, or from a
  concurrent session writing runtime stats — lands unnoticed, because a
  new-row-only check cannot see it. · severity: medium · → mitigation: inline
  pre-phase `snapshot_registry_baseline` (+ its AC-3 consumer in
  `verify_amended_acceptance_criteria`)
- Both write paths `mv` a `0600` tempfile into place, narrowing file permissions
  in a way git does not track and the diff cannot show. · severity: low · →
  mitigation: inline post-phase `restore_and_assert_file_modes`

### Goal-achievement risk: low
- The task's literal acceptance criterion is unsatisfiable without destroying
  scoring history, so a substituted weaker check could pass while the task is
  not met as written. · severity: medium · → mitigation: inline post-phase
  `verify_amended_acceptance_criteria`
- Model identity: confirmed against the bundled `claude-api` model table; the
  resolution path is verified by direct invocation of
  `aitask_resolve_detected_agent.sh`; t966 is a working precedent for the
  identical operation. No residual concern.

### Planned mitigations
- timing: pre-phase | name: snapshot_registry_baseline | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — undetected collateral row change | desc: Snapshot both registry copies and both file modes immediately before the first write, as the comparison basis for AC-3 and the mode restore.
- timing: post-phase | name: restore_and_assert_file_modes | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — silent 0644→0600 permission narrowing | desc: After the last write, restore each file's own recorded pre-change mode and assert the result with stat/diff; refuse to commit unless MODES_RESTORED_OK prints.
- timing: post-phase | name: verify_amended_acceptance_criteria | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — unsatisfiable literal AC silently substituted | desc: Machine-check AC-1 identity parity, AC-2 new-entry equality, and AC-3 no-collateral-change against the snapshot, enumerating every tolerated concurrent-stats difference by name.

Dispositions were decided by the user in chat before the design prompt (both
review findings marked `Disposition: blocking`), which is the one carve-out
`risk-mitigation-followup.md` Part 1 step 2 recognises. All three are **inline**
— no task is spawned, and Parts 2/3 correctly skip `pre-phase`/`post-phase`
lines.

## Final Implementation Notes

- **Actual work done:** Registered `claudecode/fable5_1` (`cli_id: claude-fable-5-1`)
  in both registry copies via `aitask_add_model.sh add-json` (dry-run reviewed
  first), with empty `verified: {}` / `verifiedstats: {}` matching the other
  recently-added models. Additionally refreshed the now-stale `fable5` note from
  "Fable 5 — latest-generation Claude model" to "Fable 5 — previous-generation
  Fable model" in both copies (plan step 4). No promote, no source change, no
  docs — register-only, §1 of `model_reference_locations.md` and nothing else.
  Final textual diff is exactly `8 insertions(+), 1 deletion(-)` per file: the
  new entry plus the one `notes` line, with no jq reformatting collateral.

- **Amended acceptance criterion (deviation from the task text, recorded here
  deliberately):** The task asked that "both registry copies stay byte-identical
  in their `models` array". **That was already false for all 12 pre-existing
  entries before this task touched anything** — measured baseline: `opus4_6`
  differs in `verified`+`verifiedstats`; `sonnet4_6`/`haiku4_5`/`opus4_5`/
  `sonnet4_5` in `verifiedstats`; `opus4_7`/`opus4_7_1m`/`opus4_8`/`opus4_8_1m`/
  `fable5`/`opus5`/`sonnet5` in `usagestats`+`verified`+`verifiedstats`. The
  divergence is structural and intended: the metadata copy accumulates per-model
  runtime scoring (written by `aitask_verified_update.sh`) while the seed copy is
  a pristine template. Satisfying the criterion literally would mean deleting the
  project's scoring history. It was replaced by three machine-checked criteria,
  all of which PASSED:
  - **AC-1 identity parity** — `(name, cli_id, notes)` and entry order identical
    across both copies. PASS.
  - **AC-2 new entry fully identical** — the `fable5_1` row is byte-identical in
    both files (achievable because its stats are empty). PASS.
  - **AC-3 no collateral change** — every pre-existing entry in *both* files
    byte-identical to a snapshot taken immediately before the apply. PASS; the
    only differences reported were the two `INTENDED(step 4 notes)` `fable5`
    rows. **No `TOLERATED(concurrent stats)` lines were reported** — no concurrent
    writer touched the registry inside the apply window, so there is nothing to
    enumerate on that count.
  AC-3 is the part a new-row-only check would have missed; it is what makes the
  "unrelated row silently rewritten" failure mode detectable, including a
  concurrent-session stats bump (one such rewrite had already been observed on
  this file at 09:05, before the snapshot was taken).

- **Deviations from plan:** One, and it inverted a prediction. The plan expected
  both write paths to *narrow* file modes (`mv` of a `mktemp` 0600 file), so
  `restore_and_assert_file_modes` was written to restore each file's own recorded
  pre-change mode. In practice step 4's `jq > tmp` created its temp at the umask
  default, so the `mv` **widened** `seed/models_claudecode.json` from `600` to
  `644` — the opposite direction. Restoring against the recorded per-file
  baseline handled it correctly and `MODES_RESTORED_OK` printed (metadata `644`,
  seed `600`, both their pre-change values). A hardcoded `chmod 644` — the
  obvious version of this fix — would have silently changed the seed copy's mode
  instead of restoring it. Asserting against a recorded baseline, rather than
  against an assumed direction of drift, is what made the difference.

- **Issues encountered:** None blocking. The two concerns raised in plan review
  (unreconciled acceptance criterion; `chmod` ordered before a later write that
  would undo it) were both valid and were fixed in the plan before implementation
  — the mode-ordering one demonstrably mattered, per the deviation above.

- **Key decisions:**
  - `fable5_1` registered as a **single** entry with no `fable5_1_1m` sibling: 1M
    is this model's own context window and its default, not a separate bracketed
    SKU as it was for `claude-opus-4-7[1m]` / `claude-opus-4-8[1m]`. If a distinct
    1M SKU is later announced, it gets its own entry per §1's bracketed-suffix rule.
  - Model identity confirmed against the bundled `claude-api` skill's current
    model table rather than from memory, per the task's instruction to verify
    `cli_id` against current Claude model docs.
  - The `fable5` notes refresh was included because registering `fable5_1`
    falsifies the neighbouring "latest-generation" claim in the same file and the
    same `model_reference_locations.md` §1 category. It was presented explicitly
    in the approved plan (and again at Step 8 review) rather than done silently.
  - Seed copy's file mode left at its pre-existing `600`. `seed/` is mixed (4
    files at `600`, 2 at `644`); normalizing it would be an unrequested policy
    change, not a repair.

- **Upstream defects identified:**
  `.aitask-scripts/aitask_add_model.sh:145-146 — cmd_add_json mv's a mktemp (0600) file over both registries, narrowing their permissions; git does not track read bits so the change is invisible in any diff. seed/models_claudecode.json has been 0600 since the t966 fable5 registration for exactly this reason. The helper should preserve the destination's pre-existing mode (or chmod to the umask default) after the mv. Same pattern in cmd_promote_config / cmd_promote_default_agent_string, and seed/codeagent_config.json is likewise 0600.`

- **Notes for sibling tasks:** N/A (not a child task). Related: t967 (whether the
  content-safety auto-switch that affects `fable5` also affects `fable5_1`) stays
  on t967 and is now newly checkable, since `claude-fable-5-1` resolves.
