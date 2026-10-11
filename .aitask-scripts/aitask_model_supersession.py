#!/usr/bin/env python3
"""aitask_model_supersession.py - offer newer models for superseded defaults (t1910).

Usage:
    aitask_model_supersession.py check [--root DIR] [--interactive] [--porcelain]
                                       [--no-commit] [--table PATH]
    aitask_model_supersession.py record --table P --output P --models P
                                        --agent A --new B
                                        (--seed-before P --seed-after P | --old X --seed P)
                                        [--assume-registered] [--variant-change TEXT]
                                        [--source TEXT]

check
    Scans every key under `.defaults` in the project layer
    (aitasks/metadata/codeagent_config.json) and the per-user layer
    (codeagent_config.local.json) for models the supersession table
    (lib/model_supersessions.json) supersedes, and groups them into one offer per
    superseded model per layer.

    Report mode (the default) never reads stdin — under `curl | bash` stdin is
    the installer script itself. --interactive asks one [Y/n] question per offer,
    writes only the accepted ops, and remembers a declined offer in
    <git-common-dir>/ait-codeagent-supersession-kept.json so it is not re-asked
    until a different target is offered. An accepted project-layer switch is
    committed path-scoped through lib/metadata_commit.py, but only when the file
    was clean before this run; otherwise it is written and left for the user.
    EOF or Ctrl-C at a prompt stops asking and applies only earlier answers.

    --porcelain lines: OFFER:/KEPT:/NONE (report), plus SWITCHED:/DECLINED:/
    UNANSWERED:/COMMIT:<status>/UNCOMMITTED:<reason>/NOT_REMEMBERED: (interactive).
    Warnings always go to stderr.

record
    Computes the table change a promotion implies (--seed-before/--seed-after)
    or an explicit declaration (--old/--seed) and writes the proposed table to
    --output. Prints RECORDED:/RECORDED_SIBLING:/SKIPPED:/WARN:/BLOCKED:/NOTE:
    lines. --assume-registered adds --new to the registry (previews of a model
    `add-json` has not written yet); it never vouches for --old. For a
    provider-prefixed agent (opencode) --old must be registered (any status)
    and a change of variant (tier) needs --variant-change, the reason recorded
    on the edge.

Exit: 0 ok, 1 I/O or parse error, 2 usage, 3 record blocked.

Stdlib only: install.sh runs this before `ait setup` may have built the venv.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))

import atomic_write  # noqa: E402
import metadata_commit  # noqa: E402
import model_supersession as ms  # noqa: E402

DEFAULT_TABLE = Path(ms.DEFAULT_TABLE_PATH)
METADATA_REL = "aitasks/metadata"
PROJECT_REL = f"{METADATA_REL}/codeagent_config.json"
LOCAL_REL = f"{METADATA_REL}/codeagent_config.local.json"
KEPT_FILENAME = ms.KEPT_FILENAME
COMMIT_TIMEOUT = 60
RERUN_HINT = "Run 'ait codeagent check-superseded' in a terminal to review them."

LAYER_FILES = (("project", PROJECT_REL), ("local", LOCAL_REL))
LAYER_LABELS = {"project": "project", "local": "per-user (local)"}

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_BLOCKED = 0, 1, 2, 3


def _warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def _dump_json(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _read_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --- git ---------------------------------------------------------------------

def _git_common_dir(root: Path):
    common = ms.git_common_dir(root)
    return Path(common) if common is not None else None


def _scrubbed_env() -> dict:
    # metadata_commit resolves its scope from ${TASK_DIR}; a value leaking from
    # the calling session would aim it at the wrong tree.
    env = dict(os.environ)
    env.pop("TASK_DIR", None)
    env.pop("METADATA_DIR", None)
    return env


# --- writers (pinned in tests/test_metadata_writer_inventory.py) -------------

def _write_project_layer(root: Path, data) -> str:
    """Write the tracked project layer; :func:`_commit_project_layer` commits it."""
    text = _dump_json(data)
    atomic_write.atomic_write_text(str(root / PROJECT_REL), text)
    return text


def _commit_project_layer(root: Path, text: str, out) -> None:
    """Commit exactly the bytes we wrote, path-scoped, through the metadata seam."""
    with tempfile.TemporaryDirectory(prefix="ait_supersession_") as tmp:
        holder = Path(tmp) / "codeagent_config.json"
        holder.write_text(text, encoding="utf-8")
        result = metadata_commit.commit_metadata(
            [PROJECT_REL], root=str(root), env=_scrubbed_env(),
            expect={PROJECT_REL: str(holder)}, timeout=COMMIT_TIMEOUT)
    out.commit(result, root)


def _write_local_layer(root: Path, data) -> None:
    """Write the per-user layer. Gitignored user state — never committed."""
    atomic_write.atomic_write_text(str(root / LOCAL_REL), _dump_json(data))


def _write_kept(kept_path: Path, kept) -> None:
    """Persist declined offers. Per-clone state in the git dir, never committed."""
    atomic_write.atomic_write_text(str(kept_path), _dump_json(kept))


# --- output ------------------------------------------------------------------

def _ops_text(ops) -> str:
    return ", ".join(ops)


class Output:
    def __init__(self, porcelain: bool):
        self.porcelain = porcelain

    def _line(self, tag, offer):
        return (f"{tag}:{offer.layer}|{offer.agent}/{offer.old}|"
                f"{offer.agent}/{offer.new}|{','.join(offer.ops)}")

    def offer(self, offer):
        if self.porcelain:
            print(self._line("OFFER", offer))
        else:
            print(f"  {LAYER_LABELS[offer.layer]}: {offer.agent}/{offer.old} "
                  f"({_ops_text(offer.ops)}) — superseded by {offer.agent}/{offer.new}")

    def kept(self, offer):
        if self.porcelain:
            print(self._line("KEPT", offer))
        else:
            print(f"  {LAYER_LABELS[offer.layer]}: keeping {offer.agent}/{offer.old} "
                  f"({_ops_text(offer.ops)}) — you declined {offer.agent}/{offer.new} earlier")

    def none(self):
        print("NONE" if self.porcelain else "  No superseded code-agent model defaults.")

    def header(self):
        if not self.porcelain:
            print("  Superseded code-agent model defaults:")

    def hint(self):
        if not self.porcelain:
            print(f"  {RERUN_HINT}")

    def switched(self, offer):
        if self.porcelain:
            print(self._line("SWITCHED", offer))
        else:
            print(f"  Switched {LAYER_LABELS[offer.layer]} {_ops_text(offer.ops)} to "
                  f"{offer.agent}/{offer.new}.")

    def declined(self, offer, remembered):
        if self.porcelain:
            print(self._line("DECLINED", offer))
            if not remembered:
                print(self._line("NOT_REMEMBERED", offer))
        else:
            tail = ("" if remembered else
                    " (not remembered: not a git repository — you will be asked again)")
            print(f"  Keeping {offer.agent}/{offer.old} for {_ops_text(offer.ops)}{tail}.")

    def unanswered(self, offer):
        if self.porcelain:
            print(self._line("UNANSWERED", offer))
        else:
            print(f"  Not answered: {LAYER_LABELS[offer.layer]} {offer.agent}/{offer.old} "
                  f"(you will be asked again).")

    def uncommitted(self, reason):
        if self.porcelain:
            print(f"UNCOMMITTED:{reason}")
        else:
            print(f"  {PROJECT_REL} updated but left uncommitted ({reason}) — "
                  f"review and commit it yourself.")

    def commit(self, result, root):
        status = result.status
        if self.porcelain:
            detail = result.subject or result.detail or ""
            print(f"COMMIT:{status}" + (f":{detail}" if detail else ""))
            return
        if status == "committed":
            print(f"  Committed {PROJECT_REL} ({result.subject}).")
        elif status in ("nochange", "skipped"):
            print(f"  {PROJECT_REL}: nothing to commit.")
        else:
            remedy = metadata_commit.remedy_command([PROJECT_REL],
                                                    allow_new=result.allow_new)
            why = "it changed while committing" if status == "raced" else (
                result.detail or status)
            print(f"  {PROJECT_REL} updated but NOT committed ({why}). "
                  f"Review it, then run: cd {shlex.quote(str(root))} && {remedy}")


# --- check -------------------------------------------------------------------

def _load_layer(root: Path, layer: str, rel: str):
    """``(data, defaults)`` for a layer, or ``(None, None)`` to skip it."""
    path = root / rel
    if not path.is_file():
        return None, None
    try:
        data = _read_json(path)
    except (OSError, ValueError) as exc:  # ValueError: bad JSON or bad UTF-8
        _warn(f"{layer}: cannot read {rel}: {exc} — skipped")
        return None, None
    if not isinstance(data, dict) or not isinstance(data.get("defaults"), dict):
        _warn(f"{layer}: {rel} has no 'defaults' object — skipped")
        return None, None
    return data, data["defaults"]


def _load_registries(root: Path) -> dict:
    registries, warnings = ms.load_registries(str(root / METADATA_REL))
    for msg in warnings:
        _warn(msg)
    return registries


def _load_kept(kept_path):
    kept, warnings = ms.load_kept(str(kept_path) if kept_path is not None else None)
    for msg in warnings:
        _warn(msg)
    return kept


def _ask(question: str):
    """True / False, or None on EOF or Ctrl-C."""
    while True:
        try:
            answer = input(f"  {question} [Y/n] ")
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        answer = answer.strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please answer y or n.")


def _question(offer) -> str:
    noun, verb = ("defaults", "use") if len(offer.ops) > 1 else ("default", "uses")
    return (f"Your {LAYER_LABELS[offer.layer]} {noun} for {_ops_text(offer.ops)} {verb} "
            f"{offer.agent}/{offer.old}, which is superseded by "
            f"{offer.agent}/{offer.new}. Switch?")


def _commit_precheck(root: Path, git_dir):
    """Decide BEFORE writing whether the project file may be committed by us."""
    if git_dir is None:
        return False, "not a git repository"
    pre = metadata_commit.preflight_metadata(
        [PROJECT_REL], root=str(root), env=_scrubbed_env(), timeout=COMMIT_TIMEOUT)
    if pre.status != "ok":
        return False, f"could not inspect git state: {pre.detail}"
    if pre.midop:
        return False, f"repository is mid-{pre.midop}"
    state = pre.states.get(PROJECT_REL)
    if state == "clean":
        return True, ""
    if state == "dirty":
        return False, "it already had uncommitted changes"
    return False, f"it is {state} in git"


def _apply_offers(data, offers) -> list:
    """Switch the offered ops whose value is STILL the old model; return applied."""
    applied = []
    defaults = data.setdefault("defaults", {})
    for offer in offers:
        old_value = f"{offer.agent}/{offer.old}"
        ops = tuple(op for op in offer.ops if defaults.get(op) == old_value)
        for op in ops:
            defaults[op] = f"{offer.agent}/{offer.new}"
        if ops:
            applied.append(offer._replace(ops=ops))
    return applied


def cmd_check(args) -> int:
    root = Path(args.root).resolve()
    out = Output(args.porcelain)
    try:
        table = ms.load_table(args.table)
    except ms.SupersessionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    registries = _load_registries(root)
    git_dir = _git_common_dir(root)
    kept_path = git_dir / KEPT_FILENAME if git_dir is not None else None
    kept = _load_kept(kept_path)

    pending, kept_offers = [], []
    for layer, rel in LAYER_FILES:
        _, defaults = _load_layer(root, layer, rel)
        if defaults is None:
            continue
        offers, warnings = ms.find_offers(layer, defaults, table, registries)
        for msg in warnings:
            _warn(msg)
        for offer in offers:
            (kept_offers if ms.is_kept(kept, offer) else pending).append(offer)

    if not pending and not kept_offers:
        out.none()
        return EXIT_OK

    if not args.interactive:
        out.header()
        for offer in pending:
            out.offer(offer)
        for offer in kept_offers:
            out.kept(offer)
        if pending:
            out.hint()
        return EXIT_OK

    for offer in kept_offers:
        out.kept(offer)

    accepted = {layer: [] for layer in ms.LAYERS}
    new_kept = kept
    declined = []
    for index, offer in enumerate(pending):
        answer = _ask(_question(offer))
        if answer is None:
            for rest in pending[index:]:
                out.unanswered(rest)
            break
        if answer:
            accepted[offer.layer].append(offer)
            new_kept = ms.without_kept(new_kept, offer)
        else:
            declined.append(offer)
            new_kept = ms.with_kept(new_kept, offer)

    try:
        if accepted["project"]:
            commit_ok, reason = (False, "")
            if not args.no_commit:
                commit_ok, reason = _commit_precheck(root, git_dir)
            # Re-read after the prompts: only ops still on the old model switch.
            data, _ = _load_layer(root, "project", PROJECT_REL)
            applied = _apply_offers(data, accepted["project"]) if data is not None else []
            if applied:
                text = _write_project_layer(root, data)
                for offer in applied:
                    out.switched(offer)
                if commit_ok:
                    _commit_project_layer(root, text, out)
                elif not args.no_commit:
                    out.uncommitted(reason)

        if accepted["local"]:
            data, _ = _load_layer(root, "local", LOCAL_REL)
            applied = _apply_offers(data, accepted["local"]) if data is not None else []
            if applied:
                _write_local_layer(root, data)
            for offer in applied:
                out.switched(offer)
    except OSError as exc:
        print(f"error: could not write the config: {exc}", file=sys.stderr)
        return EXIT_ERROR

    for offer in declined:
        out.declined(offer, remembered=kept_path is not None)
    if kept_path is not None and new_kept != kept:
        try:
            _write_kept(kept_path, new_kept)
        except OSError as exc:
            _warn(f"could not remember declined offers in {kept_path}: {exc}")
    return EXIT_OK


# --- record ------------------------------------------------------------------

def _defaults_of(path) -> dict:
    data = _read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("defaults", {}), dict):
        raise ms.SupersessionError(f"{path}: 'defaults' must be an object")
    return data.get("defaults", {})


def cmd_record(args, parser) -> int:
    if not ms.valid_agent(args.agent):
        parser.error(f"invalid --agent value: {args.agent!r}")
    for label, value in (("--new", args.new), ("--old", args.old)):
        if value is not None and not ms.valid_model(value):
            parser.error(f"invalid {label} value: {value!r}")
    if args.old is not None and (args.seed is None or args.seed_before or args.seed_after):
        parser.error("--old needs --seed (and excludes --seed-before/--seed-after)")
    if args.old is None and (args.seed_before is None or args.seed_after is None):
        parser.error("a promotion needs --seed-before and --seed-after (or use --old/--seed)")
    if args.variant_change is not None and (args.old is None or not args.variant_change):
        parser.error("--variant-change needs --old and a non-empty reason")

    try:
        table = ms.load_table(args.table)
        # One read: the offerable names gate --new; every registered name (any
        # status) gates --old, which may be unavailable. --assume-registered
        # never vouches for --old.
        registry, listed = ms.load_registry_sets(args.models)
        registry, listed = registry or set(), listed or set()
        events = []
        available = set(registry)
        if args.assume_registered and args.new not in available:
            available.add(args.new)
            events.append(f"NOTE:assumes_registration:{args.agent}/{args.new}")
        source = args.source or "promote-config"
        if args.old is not None:
            new_table, plan_events, blocked = ms.plan_explicit(
                table, args.agent, args.old, args.new, _defaults_of(args.seed),
                available, source, variant_change=args.variant_change, listed=listed)
        else:
            new_table, plan_events, blocked = ms.plan_promotion(
                table, args.agent, args.new, _defaults_of(args.seed_before),
                _defaults_of(args.seed_after), available, source, listed=listed)
        events.extend(plan_events)
        atomic_write.atomic_write_text(args.output, ms.render_table(new_table))
    except (OSError, ValueError) as exc:  # ValueError covers SupersessionError and bad JSON/UTF-8
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    for event in events:
        print(event)
    return EXIT_BLOCKED if blocked else EXIT_OK


# --- main --------------------------------------------------------------------

def _parser():
    parser = argparse.ArgumentParser(
        prog="aitask_model_supersession.py",
        description="Offer newer models for superseded code-agent defaults.")
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="find superseded defaults and offer switches")
    check.add_argument("--root", default=".")
    check.add_argument("--interactive", action="store_true")
    check.add_argument("--porcelain", action="store_true")
    check.add_argument("--no-commit", action="store_true")
    check.add_argument("--table", default=str(DEFAULT_TABLE))

    record = sub.add_parser("record", help="compute a supersession table change")
    record.add_argument("--table", required=True)
    record.add_argument("--output", required=True)
    record.add_argument("--models", required=True)
    record.add_argument("--agent", required=True)
    record.add_argument("--new", required=True)
    record.add_argument("--old")
    record.add_argument("--seed")
    record.add_argument("--seed-before")
    record.add_argument("--seed-after")
    record.add_argument("--assume-registered", action="store_true")
    record.add_argument("--variant-change",
                        help="why an edge of a provider-prefixed agent changes variant (tier)")
    record.add_argument("--source")
    return parser, record


def main(argv=None) -> int:
    parser, record_parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "record":
        return cmd_record(args, record_parser)
    parser.print_help(sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
