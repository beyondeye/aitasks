"""skill_template - Render skill .j2 templates via minijinja.

t777_22 extension: dep-walker for uniform recursive rendering. Every referenced
.md file in a rendered skill is itself rendered through minijinja into a
per-profile sibling location, with cross-references rewritten to point at the
rendered tree. Identity-transform when a source has no Jinja markers.

NOTE: minijinja is NOT 100% Jinja2-compatible. Stick to:
  {{ var }}, {% if %}/{% else %}/{% endif %}, {% include %},
  {% raw %}/{% endraw %}.
No {% extends %} with arbitrary Python, smaller filter set, no `do` extension.

Usage (library):
    from skill_template import render_skill, walk_closure
    text = render_skill(Path("aitask-pick/SKILL.md.j2"), profile_dict, "claude")

Usage (CLI):
    # Single-file render to stdout (legacy)
    python skill_template.py <template> <profile.yaml> <agent>

    # Walk dep closure + write to disk under <repo_root>
    python skill_template.py walk-write <entry> <profile.yaml> <agent> <repo_root> [--force]

    # Walk dep closure to validate (no disk writes)
    python skill_template.py walk-check <entry> <profile.yaml> <agent> <repo_root>
"""
from __future__ import annotations

import os
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

# t777_22: full-path refs <root>/skills/<dir>/<file>.md across all agent roots.
FULL_PATH_REF_RE = re.compile(
    r'(?P<root>\.claude|\.agents|\.opencode)/skills/'
    r'(?P<dir>[A-Za-z0-9._-]+)/'
    r'(?P<file>[A-Za-z0-9._-]+\.md)\b'
)
# Short refs: sibling (Y.md) or skill-relative (X/Y.md). Anchored on
# non-path-char boundaries to avoid splitting longer paths or word fragments.
SHORT_REF_RE = re.compile(
    r'(?<![A-Za-z0-9._/-])'
    r'(?P<inner>(?:[A-Za-z0-9._-]+/)?[A-Za-z0-9._-]+\.md)'
    r'(?![A-Za-z0-9./-])'
)

AGENT_ROOTS = {
    "claude":   ".claude/skills",
    "codex":    ".agents/skills",
    "opencode": ".opencode/skills",
}
# Agents whose physical skills root is shared with another agent. Shared
# roots get an additional -<agent>- segment in rendered dir names so two
# agents writing into the same root do not collide (t834). Mirror of
# agent_shared_skills_root() in lib/agent_skills_paths.sh.
AGENT_SHARED_SKILLS_ROOT = {
    "claude":   False,
    "codex":    True,
    "opencode": False,
}
SOURCE_AGENT_ROOT = ".claude/skills"  # Claude is source of truth (t777_1).


def _render_dir_name(skill: str, profile_name: str, agent: str) -> str:
    """Return the rendered-dir basename for a (skill, profile, agent) triple.
    Shared-root agents get an extra `-<agent>-` segment so they do not
    collide with other agents writing into the same physical root."""
    if AGENT_SHARED_SKILLS_ROOT.get(agent, False):
        return f"{skill}-{profile_name}-{agent}-"
    return f"{skill}-{profile_name}-"


# Cross-pipeline include bridge (t818): shared markdown fragments live in
# .aitask-scripts/skill_templates/ and are consumed by both the bash crew
# template resolver (resolve_template_includes in agentcrew_utils.sh) and
# this minijinja renderer via {% include %}.
def _find_repo_root(start: Path) -> Path | None:
    for p in [start, *start.parents]:
        if (p / ".aitask-scripts").is_dir():
            return p
    return None


def _include_search_dirs(template_path: Path) -> list[Path]:
    """Return the ordered list of dirs minijinja's loader should search for
    {% include %} targets. Mirrors the dep-walker's resolution for
    {% include %} staleness tracking."""
    dirs = [template_path.parent, template_path.parent.parent]
    root = _find_repo_root(template_path)
    if root is not None:
        st = root / ".aitask-scripts" / "skill_templates"
        if st.is_dir():
            dirs.append(st)
    return dirs


# Dep-walker tracks three Jinja directives that pull in another template
# at runtime: {% include "X" %}, {% from "X" import Y %}, {% import "X" as Y %}.
# Touching any referenced file must invalidate cached renders of the consumer.
TEMPLATE_DEP_RES = [
    re.compile(r'\{%-?\s*include\s+["\']([^"\']+)["\']'),
    re.compile(r'\{%-?\s*from\s+["\']([^"\']+)["\']\s+import\b'),
    re.compile(r'\{%-?\s*import\s+["\']([^"\']+)["\']'),
]


def render_skill(template_path: Path, profile: dict[str, Any], agent_name: str) -> str:
    import minijinja

    env = minijinja.Environment(
        loader=minijinja.load_from_path(
            [str(d) for d in _include_search_dirs(template_path)]
        ),
        keep_trailing_newline=True,
        undefined_behavior="strict",
    )
    template_source = template_path.read_text(encoding="utf-8")
    try:
        return env.render_str(template_source, profile=profile, agent=agent_name)
    except minijinja.TemplateError as e:
        raise RuntimeError(
            f"Template '{template_path}' render failed: {e}. "
            f"If this is an undefined-variable error, check the profile YAML "
            f"for the missing key."
        ) from e


# === t777_22 dep-walker ===


def _skill_name_from_source(source_abs: Path, repo_root: Path) -> str | None:
    """Extract <skill> from <repo_root>/<agent_root>/skills/<skill>/<file>(.j2)?
    Returns None if path is not under any agent skill root."""
    try:
        rel = source_abs.relative_to(repo_root)
    except ValueError:
        return None
    parts = rel.parts
    if (
        len(parts) >= 4
        and parts[1] == "skills"
        and parts[0] in (".claude", ".agents", ".opencode")
    ):
        return parts[2]
    return None


def _target_path_for(source_abs: Path, agent: str, profile_name: str, repo_root: Path) -> Path:
    """Compute the per-profile target path for a non-entry source file.
    Sources always live under .claude/skills/<skill>/<rest>; target depends
    on the requested agent."""
    rel = source_abs.relative_to(repo_root)
    parts = rel.parts
    if len(parts) < 4 or parts[1] != "skills":
        raise ValueError(f"Source not under <agent_root>/skills/: {source_abs}")
    skill = parts[2]
    rest = parts[3:]
    target_root = AGENT_ROOTS[agent]
    return repo_root / target_root / _render_dir_name(skill, profile_name, agent) / Path(*rest)


def discover_refs(text: str, current_source: Path, repo_root: Path):
    """Yield discovered refs. Each ref is a dict with:
       start, end, original_str, resolved_source, kind, ref_dir, ref_file.
    kind ∈ {full, sibling, skill_relative}. Only refs whose resolved file
    exists are yielded (filters prose mentions of nonexistent filenames)."""
    spans_seen: list[tuple[int, int]] = []

    # 1) Full-path refs first.
    for m in FULL_PATH_REF_RE.finditer(text):
        original = m.group(0)
        source_root = m.group("root")
        # All sources live under .claude/skills/<skill>/... regardless of which
        # agent root the ref string mentions (claude is SoT per t777_1).
        rel_under_source = (
            original
            if source_root == SOURCE_AGENT_ROOT
            else SOURCE_AGENT_ROOT + "/" + original[len(source_root) + len("/skills/"):]
        )
        resolved = (repo_root / rel_under_source).resolve()
        if resolved.is_file():
            spans_seen.append((m.start(), m.end()))
            yield {
                "start": m.start(),
                "end": m.end(),
                "original_str": original,
                "resolved_source": resolved,
                "kind": "full",
                "ref_dir": m.group("dir"),
                "ref_file": m.group("file"),
            }

    # 2) Short refs (sibling or skill-relative). Dedupe against full-path spans.
    for m in SHORT_REF_RE.finditer(text):
        s, e = m.start(), m.end()
        if any(not (e <= so or s >= eo) for so, eo in spans_seen):
            continue
        inner = m.group("inner")
        if "/" in inner:
            dir_name, file_name = inner.split("/", 1)
            resolved = (repo_root / SOURCE_AGENT_ROOT / dir_name / file_name).resolve()
            kind = "skill_relative"
        else:
            file_name = inner
            dir_name = current_source.parent.name
            resolved = (current_source.parent / file_name).resolve()
            kind = "sibling"
        if resolved.is_file():
            yield {
                "start": s,
                "end": e,
                "original_str": inner,
                "resolved_source": resolved,
                "kind": kind,
                "ref_dir": dir_name,
                "ref_file": file_name,
            }


def rewrite_ref(ref: dict, agent: str, profile_name: str) -> str:
    """Return the rewritten reference string for the target tree.
       full           → <target_root>/<dir>-<profile>-/<file>.md
       sibling        → <file>.md  (unchanged; rendered into same per-profile dir)
       skill_relative → <target_root>/<dir>-<profile>-/<file>.md"""
    if ref["kind"] == "sibling":
        return ref["ref_file"]
    target_root = AGENT_ROOTS[agent]
    dir_name = _render_dir_name(ref["ref_dir"], profile_name, agent)
    return f"{target_root}/{dir_name}/{ref['ref_file']}"


def _atomic_write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(target))


def _resolve_template_deps(source_abs: Path, raw_text: str) -> set[Path]:
    """Scan raw template source for {% include %} / {% from %} / {% import %}
    directives and resolve each referenced filename against the same search
    dirs the runtime loader uses. Returns the set of existing matches.
    minijinja resolves these directives at render time so they never appear
    in the dep-walker's source list — folding them into the staleness check
    makes editing a shared fragment (procedure include, macro library, …)
    correctly invalidate every consuming rendered file."""
    dirs = _include_search_dirs(source_abs)
    deps: set[Path] = set()
    for regex in TEMPLATE_DEP_RES:
        for m in regex.finditer(raw_text):
            name = m.group(1)
            for d in dirs:
                candidate = (d / name).resolve()
                if candidate.is_file():
                    deps.add(candidate)
                    break
    return deps


def _is_stale(plan: list, profile_yaml: Path, include_deps: set[Path] | None = None) -> bool:
    """True if any target is missing or older than any closure source /
    profile YAML / runtime-resolved {% include %} dep."""
    max_source_mtime = profile_yaml.stat().st_mtime
    for src, _t, _c in plan:
        st = src.stat().st_mtime
        if st > max_source_mtime:
            max_source_mtime = st
    if include_deps:
        for dep in include_deps:
            try:
                st = dep.stat().st_mtime
            except OSError:
                continue
            if st > max_source_mtime:
                max_source_mtime = st
    for _s, target, _c in plan:
        if not target.is_file():
            return True
        if target.stat().st_mtime < max_source_mtime:
            return True
    return False


def _any_target_differs(plan: list) -> bool:
    """True if any target is missing or its on-disk content differs from the
    freshly rendered content.

    Used as an authoritative safety net alongside the mtime-based `_is_stale`:
    a `git checkout`/clone resets the mtimes of source *and* target to the same
    checkout timestamp, so `target.mtime < source.mtime` reads as "fresh" even
    when a committed prerender has really drifted from its source (t907). That
    masked drift — committed `*-remote-` prerenders silently staying stale — is
    what this comparison catches. It is effectively free: `walk_closure`
    already renders every target's content into the plan, so this only adds a
    short read+compare of each (small) target file, short-circuiting on the
    first difference."""
    for _src, target, content in plan:
        try:
            if target.read_text(encoding="utf-8") != content:
                return True
        except OSError:
            return True  # missing/unreadable target → must (re)write
    return False


def walk_closure(
    entry_template: Path,
    profile: dict,
    agent: str,
    profile_name: str,
    profile_yaml: Path,
    repo_root: Path,
    write: bool,
    force: bool,
) -> list:
    """BFS over dep closure starting at entry_template. Renders every
    reachable .md / .md.j2 source through minijinja, rewrites references in
    each rendered output, and (if write=True and force/stale/content-differs)
    atomically writes every (source, target) pair to disk. Returns the plan
    list. Skip-if-fresh combines an mtime fast-path (`_is_stale`) with an
    authoritative content comparison (`_any_target_differs`) so git-equalized
    mtimes cannot mask real drift in committed prerenders (t907)."""
    skill = _skill_name_from_source(entry_template, repo_root)
    if skill is None:
        raise ValueError(f"Entry template not under <agent_root>/skills/: {entry_template}")
    target_root = AGENT_ROOTS[agent]
    entry_target = repo_root / target_root / _render_dir_name(skill, profile_name, agent) / "SKILL.md"

    visited: set[Path] = {entry_template.resolve()}
    queue: deque = deque([(entry_template.resolve(), entry_target)])
    plan: list = []
    include_deps: set[Path] = set()

    while queue:
        src, target = queue.popleft()
        # Scan raw source for {% include %} directives BEFORE rendering, so
        # we capture them even when conditionals would suppress execution.
        try:
            raw_source = src.read_text(encoding="utf-8")
        except OSError:
            raw_source = ""
        include_deps |= _resolve_template_deps(src, raw_source)

        try:
            raw = render_skill(src, profile, agent)
        except Exception as e:
            raise RuntimeError(f"Render failed for source '{src}': {e}") from e

        refs = list(discover_refs(raw, src, repo_root))

        # Rewrite refs in-place by descending span. Each match has a unique
        # (start, end), so span-based slice replacement is correct even when
        # the same path appears multiple times.
        new_raw = raw
        for ref in sorted(refs, key=lambda r: -r["start"]):
            new_str = rewrite_ref(ref, agent, profile_name)
            new_raw = new_raw[: ref["start"]] + new_str + new_raw[ref["end"]:]

        # Enqueue unvisited children for further walking.
        for ref in refs:
            child_src = ref["resolved_source"]
            if child_src in visited:
                continue
            child_target = _target_path_for(child_src, agent, profile_name, repo_root)
            if child_target == entry_target:
                # A prose mention of the skill's own SKILL.md resolves to the
                # entry-point stub, whose target path collides with the
                # rendered entry-point. The stub is not a real closure
                # dependency — skip it so it never overwrites the entry.
                visited.add(child_src)
                continue
            visited.add(child_src)
            queue.append((child_src, child_target))

        plan.append((src, target, new_raw))

    # Guard: every closure source must map to a distinct target path. The
    # entry-target collision (prose SKILL.md ref) is filtered above; any
    # remaining collision is a walker bug — fail loudly instead of letting
    # the last write silently win.
    targets_seen: dict[Path, Path] = {}
    for src, target, _content in plan:
        prior = targets_seen.get(target)
        if prior is not None and prior != src:
            raise RuntimeError(
                f"Closure target-path collision: '{prior}' and '{src}' "
                f"both render to '{target}'"
            )
        targets_seen[target] = src

    if write:
        # Write the closure when forced, when the mtime fast-path reports a
        # stale leaf, OR when any target's on-disk content differs from the
        # freshly rendered content. The content check is the authority: it
        # repairs committed prerenders that drifted under git-equalized mtimes,
        # which `_is_stale` alone misses (t907).
        if (
            force
            or _is_stale(plan, profile_yaml, include_deps)
            or _any_target_differs(plan)
        ):
            for _src, target, content in plan:
                _atomic_write(target, content)

    return plan


# === CLI ===


def _load_profile(path: Path) -> dict:
    import yaml

    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _profile_name(profile: dict, profile_yaml: Path) -> str:
    name = profile.get("name")
    if isinstance(name, str) and name:
        return name
    return profile_yaml.stem


def _main_legacy(argv: list) -> int:
    if len(argv) != 3:
        sys.stderr.write(
            "usage: skill_template.py <template.j2> <profile.yaml> <agent>\n"
        )
        return 2
    template = Path(argv[0])
    profile_yaml = Path(argv[1])
    agent = argv[2]
    profile = _load_profile(profile_yaml)
    sys.stdout.write(render_skill(template, profile, agent))
    return 0


def _main_walk(argv: list, write: bool) -> int:
    force = False
    positional: list = []
    for a in argv:
        if a == "--force":
            force = True
        else:
            positional.append(a)
    if len(positional) != 4:
        mode = "walk-write" if write else "walk-check"
        sys.stderr.write(
            f"usage: skill_template.py {mode} "
            f"<entry.j2> <profile.yaml> <agent> <repo_root> [--force]\n"
        )
        return 2
    entry = Path(positional[0]).resolve()
    profile_yaml = Path(positional[1]).resolve()
    agent = positional[2]
    repo_root = Path(positional[3]).resolve()
    if agent not in AGENT_ROOTS:
        sys.stderr.write(f"skill_template: unknown agent '{agent}'\n")
        return 2
    profile = _load_profile(profile_yaml)
    profile_name = _profile_name(profile, profile_yaml)
    try:
        walk_closure(
            entry,
            profile,
            agent,
            profile_name,
            profile_yaml,
            repo_root,
            write=write,
            force=force,
        )
    except Exception as e:
        sys.stderr.write(f"skill_template walk error: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.stderr.write(
            "usage: skill_template.py <template> <profile.yaml> <agent>\n"
            "       skill_template.py walk-write|walk-check <entry> <profile.yaml> <agent> <repo_root>\n"
        )
        sys.exit(2)
    if args[0] == "walk-write":
        sys.exit(_main_walk(args[1:], write=True))
    if args[0] == "walk-check":
        sys.exit(_main_walk(args[1:], write=False))
    sys.exit(_main_legacy(args))
