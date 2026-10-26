"""Create a new agent from templates/host_agent and register it in sandbox_app.py.

  python -m sandbox_host.scaffold <agent-name> [--description "..."]

Nothing is written unless the name is valid, the folder is free, and both registration markers exist.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from string import Template
from typing import Optional

from .registry import NAME_PATTERN

IMPORT_MARKER = "# <scaffold:imports>"
AGENTS_MARKER = "# <scaffold:agents>"
TEMPLATE_DIR = Path("templates") / "host_agent"
DEFAULT_DESCRIPTION = "Describe what this agent does for the team."


class ScaffoldError(ValueError):
    """The scaffold cannot be created. The message says why."""


def scaffold(repo_root: Path, name: str, description: Optional[str] = None) -> Path:
    repo_root = Path(repo_root)
    if not NAME_PATTERN.match(name):
        raise ScaffoldError(f"Agent name {name!r} must be lowercase letters, digits, and hyphens, "
                            "start with a letter, and be 2-40 characters")
    module = name.replace("-", "_")
    target = repo_root / "agents" / module
    if target.exists():
        raise ScaffoldError(f"{target.relative_to(repo_root)} already exists")
    template_root = repo_root / TEMPLATE_DIR
    if not template_root.is_dir():
        raise ScaffoldError(f"Template folder missing: {TEMPLATE_DIR}")
    app_file = repo_root / "sandbox_app.py"
    app_text = app_file.read_text(encoding="utf-8")
    for marker in (IMPORT_MARKER, AGENTS_MARKER):
        if marker not in app_text:
            raise ScaffoldError(f"sandbox_app.py is missing the marker {marker}")

    mapping = {
        "name": name,
        "module": module,
        "Title": " ".join(part.capitalize() for part in name.split("-")),
        "ClassStore": "".join(part.capitalize() for part in name.split("-")) + "Store",
        "table": module,
        "description": (description or DEFAULT_DESCRIPTION).replace('"', "'"),
    }
    rendered = {}
    for source in sorted(template_root.rglob("*.tpl")):
        relative = source.relative_to(template_root).with_suffix("")
        try:
            rendered[relative] = Template(source.read_text(encoding="utf-8")).substitute(mapping)
        except KeyError as error:
            raise ScaffoldError(f"Template {source.name} uses an unknown placeholder: {error}") from None

    for relative, content in rendered.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _register(app_file, module, name)
    return target


def _register(app_file: Path, module: str, name: str) -> None:
    text = app_file.read_text(encoding="utf-8")
    spec = f"make_{module}_spec"
    import_line = f"from {module}.api import make_agent_spec as {spec}\n"
    agent_line = f"    {spec}(),\n"
    text = text.replace(IMPORT_MARKER + "\n", IMPORT_MARKER + "\n" + import_line, 1)
    text = text.replace(AGENTS_MARKER + "\n", AGENTS_MARKER + "\n" + agent_line, 1)
    compile(text, str(app_file), "exec")
    app_file.write_text(text, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a host agent from the template.")
    parser.add_argument("name")
    parser.add_argument("--description", default=None)
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    try:
        target = scaffold(repo_root, args.name, args.description)
    except ScaffoldError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"created {target.relative_to(repo_root)} and registered '{args.name}' in sandbox_app.py")
    print("next: write the spec in specs/features/" + args.name + "/ and add a failing test first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
