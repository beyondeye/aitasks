"""skill_template - Render skill .j2 templates via minijinja.

NOTE: minijinja is NOT 100% Jinja2-compatible. Stick to:
  {{ var }}, {% if %}/{% else %}/{% endif %}, {% include %},
  {% raw %}/{% endraw %}.
No {% extends %} with arbitrary Python, smaller filter set, no `do` extension.

Usage (library):
    from skill_template import render_skill
    text = render_skill(Path("aitask-pick/SKILL.md.j2"), profile_dict, "claude")

Usage (CLI):
    python skill_template.py <template> <profile.yaml> <agent> > rendered.md
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def render_skill(template_path: Path, profile: dict[str, Any], agent_name: str) -> str:
    import minijinja

    env = minijinja.Environment(
        loader=minijinja.load_from_path([str(template_path.parent)]),
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


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.stderr.write(
            "usage: skill_template.py <template.j2> <profile.yaml> <agent>\n"
        )
        sys.exit(2)

    import yaml

    template = Path(sys.argv[1])
    profile_yaml = Path(sys.argv[2])
    agent = sys.argv[3]
    with profile_yaml.open(encoding="utf-8") as f:
        profile = yaml.safe_load(f) or {}
    sys.stdout.write(render_skill(template, profile, agent))
