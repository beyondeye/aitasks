# Plan: t1198 — Manual verification, fresh-install seed delivery

**Task:** t1198 (`aitasks/t1198_manual_verification_fresh_install_seed_delivery.md`)
**Verifies:** t1194
**Mode:** auto-verification, `strategy = autonomous` (whole checklist)
**Working directory:** current branch (profile `fast`)
**Scratch root:** `$SCRATCH = /tmp/claude-1000/-home-ddt-Work-aitasks/003c9bcd-299e-4543-a8c6-3fcd5e0665ab/scratchpad/auto_verify_1198`

## Fixtures

Three fixtures were built so each delivery path could be exercised for real,
and so items 6–7 are checked against an **independent ground truth** (the
tarball install's own output) rather than by re-deriving both sides from the
same two functions the way `tests/test_seed_manifest_drift.sh` necessarily does.

| Fixture | Contents | Exercises |
|---------|----------|-----------|
| `$SCRATCH/scratch-project` | fresh git repo, installed from `aitasks-v0.28.0.tar.gz` | install.sh `install_seed_*` path (items 1–5) |
| `$SCRATCH/clean-clone` | `ait`, `.aitask-scripts/`, `seed/`, `packaging/`, `.claude/skills/`; **no** `aitasks/` | `ait setup` source-tree path (item 6) |
| `$SCRATCH/seedless-clone` | same, but `seed/` removed, `gates_reference.yaml` kept | t1147 invariant (item 7) |

The tarball was built by replaying `.github/workflows/release.yml`: stage
`skills/`, `codex_skills/`, `opencode_skills/`, `opencode_commands/`, then
`tar -czf aitasks-v0.28.0.tar.gz ait CHANGELOG.md .aitask-scripts/ packaging/
skills/ seed/ codex_skills/ opencode_skills/ opencode_commands/`.

Two invocation details kept the run non-interactive and non-destructive:
`SHIM_DIR=$SCRATCH/fakebin` (so the user's real `~/.local/bin/ait` is never
rewritten — `SHIM_DIR` is env-overridable at `aitask_setup.sh:9`) and `</dev/null`
(stdin is not a TTY, so `confirm_install` and `setup_data_branch` take their
auto-accept paths).

## Execution Log

### Item 1 — tarball install completes without error
- **Item text:** Build a tarball and run `bash install.sh --local-tarball <tarball> --dir <scratch-project>`; confirm the run completes without error.
- **Approach:** CLI invocation.
- **Action run:** `SHIM_DIR=$SCRATCH/fakebin bash install.sh --local-tarball "$SCRATCH/aitasks-v0.28.0.tar.gz" --dir "$PROJ" </dev/null`
- **Output (trimmed):** `EXIT=0` … `=== aitasks installed successfully ===`; all `install_seed_*` steps logged an `Installed …` line.
- **Verdict:** pass

### Item 2 — doc_update_guide.md lands and matches the seed
- **Approach:** File inspection.
- **Action run:** `diff -q seed/doc_update_guide.md "$PROJ/aitasks/metadata/doc_update_guide.md"`
- **Output (trimmed):** no differences (3432 bytes).
- **Why it matters:** the `docs_updated` gate resolves this path at runtime, after `seed/` has been deleted.
- **Verdict:** pass

### Item 3 — code_areas.yaml lands with its full header
- **Approach:** File inspection.
- **Action run:** `diff -q seed/code_areas.yaml <dest>` plus `head -20 <dest>`.
- **Output (trimmed):** byte-identical; the `# Code areas map …` / `# Format:` comment block is intact — confirming `install_seed_code_areas` (`install.sh:611`) copies rather than yaml-merging, which would have round-tripped the file through `yaml.safe_dump` and destroyed the header.
- **Verdict:** pass

### Item 4 — pre-existing seeds still land
- **Approach:** File inspection over `aitasks/metadata/`.
- **Output (trimmed):** present — `task_types.txt`, `project_config.yaml`, `chatlink_config.yaml`, `codeagent_config.json`, `gates.yaml`, `models_{claudecode,codex,opencode}.json`, `profiles/{default,fast,remote}.yaml`, `codex_config.seed.toml`, `codex_rules.default.rules`, `codex_instructions.seed.md`, `opencode_config.seed.json`, `opencode_instructions.seed.md`, `aitasks_agent_instructions.seed.md`, `claude_settings.seed.json`. `claude_settings.local.json` is **absent** — the rename applied.
- **Verdict:** pass

### Item 5 — seed/ deleted, and --force preserves hand edits
- **Approach:** CLI invocation + sha256 fixpoint check.
- **Action run:** appended a `# HAND-EDIT SENTINEL t1198 …` line to both `doc_update_guide.md` and `code_areas.yaml`, recorded `sha256sum`, then re-ran the installer with `--force`, then `sha256sum -c`.
- **Output (trimmed):** `EXIT=0`; log shows `Code areas map exists (kept): code_areas.yaml` and `Doc-update guide exists (kept): doc_update_guide.md`; both checksums `OK`; both sentinels still present; `$PROJ/seed` absent after both runs.
- **Why it holds:** unlike `merge_seed`, `install_seed_doc_update_guide` and `install_seed_code_areas` early-return on an existing destination with **no** `FORCE` escape — these are user-editable prose/project-owned content.
- **Verdict:** pass

### Item 6 — `ait setup` from the source tree matches the tarball set
- **Approach:** CLI invocation + file-set diff against the item-1 install.
- **Action run:** `SHIM_DIR=$SCRATCH/fakebin ./ait setup </dev/null` in `$SCRATCH/clean-clone`, then `diff` of the two `aitasks/metadata/` listings.
- **Output (trimmed):** `EXIT=0`, `Setup complete!`. Seed-delivered set (top-level regular files + `profiles/`) is **identical**, 20/20 — including the two t1194 additions. `doc_update_guide.md`, `code_areas.yaml` and `gates.yaml` are each byte-identical to their sources.
- **Two by-design differences, neither drift:**
  - `userconfig.yaml` — per-user gitignored config written by `setup_userconfig`; not a seed, and install.sh leaves it to the post-install `ait setup`.
  - `codex_skills/`, `opencode_skills/`, `opencode_commands/` — tarball-only *transport staging*. `setup_codex_cli` (`aitask_setup.sh:2073`) **reads from** the staging dir and writes to `.agents/skills/`; it never creates it. A source tree owns `.agents/skills/` and `.opencode/skills/` directly, so the staging dirs are unnecessary there and setup logged `No Codex CLI staging files found — skipping` / `No OpenCode staging files found — skipping`. These are `install_codex_staging` / `install_opencode_staging`, not members of the `install_seed_*` family the manifests compare.
- **Note on the call path:** `populate_data_branch_seed_metadata` fires only on the fresh-data-branch arm (`aitask_setup.sh:1333`); when `aitasks/` already exists as a real directory the migration arm copies existing data instead. The fixture therefore deliberately has no `aitasks/`.
- **Verdict:** pass

### Item 7 — t1147 invariant, gates.yaml without seed/
- **Approach:** CLI invocation on the seedless fixture.
- **Action run:** `SHIM_DIR=$SCRATCH/fakebin ./ait setup </dev/null` in `$SCRATCH/seedless-clone`.
- **Output (trimmed):** `EXIT=0`; `aitasks/metadata/gates.yaml` exists and is byte-identical to `.aitask-scripts/gates_reference.yaml`; the metadata dir contains **only** `gates.yaml` and `userconfig.yaml` — no seed-derived file was fabricated.
- **Why it holds:** `populate_data_branch_seed_metadata` (`aitask_setup.sh:1620`) copies the gate reference **before** the `[[ -d "$seed_dir" ]] || return 0` guard, exactly as its comment states.
- **Verdict:** pass

## Result

7/7 pass, 0 fail, 0 skip, 0 defer. No follow-up bug tasks were created.
Both delivery paths agree on the seed manifest, the t1194 additions
(`doc_update_guide.md`, `code_areas.yaml`) reach both, user edits survive
`--force`, and the t1147 seedless-gates invariant holds end to end.

## Final Implementation Notes

- **Actual work done:** verification only — no framework source was modified. Seven checklist items executed against three purpose-built fixtures.
- **Deviations from plan:** none substantive. Plan mode engaged mid-run after item 1–5a had already executed; the remaining items were planned and then executed as approved.
- **Issues encountered:** the first file-set diff appeared to show drift (3 staging dirs + `userconfig.yaml`); tracing `setup_codex_cli`'s source resolution showed the staging dirs are a tarball-only transport that setup consumes but never produces, so the seed manifests do in fact agree.
- **Key decisions:** compared against the tarball install's own output rather than re-running `tests/test_seed_manifest_drift.sh`, since that guard derives both manifests from the same two functions and cannot catch a case where both sides are wrong together. `SHIM_DIR` was overridden so no real user state was touched.
- **Environment note:** `ait setup` pip-installs into the shared `~/.aitask/venv` (its path is hardcoded at `aitask_setup.sh:8`, not env-overridable). Both runs were idempotent re-installs of already-pinned specs.
- **Upstream defects identified:** None
