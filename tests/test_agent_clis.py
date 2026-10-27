"""Every agent's command-line entry point must run as a real subprocess and print usage.

Discovered from the agents folder, so a new agent is covered without a test edit. Offline: --help and no arguments only.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"


def _modules(filename):
    found = []
    for path in sorted(AGENTS.glob(f"*/{filename}")):
        package = path.parent
        if (package / "__init__.py").is_file() and package.name.isidentifier():
            found.append(f"{package.name}.{path.stem}")
    return found


CLI_MODULES = _modules("cli.py")
MAIN_MODULES = [m for m in _modules("__main__.py")]


def _run(args):
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{AGENTS}"}
    return subprocess.run([sys.executable, *args], cwd=AGENTS, env=env, capture_output=True, text=True,
                          timeout=60)


def test_agent_clis_were_discovered():
    assert {"competitor_watch.cli", "file_reader.cli", "emeia_dashboard.cli", "people_company_search.cli"} <= set(CLI_MODULES)


@pytest.mark.parametrize("module", CLI_MODULES)
def test_cli_prints_usage_for_help(module):
    result = _run(["-m", module, "--help"])
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "usage" in output.lower() and "Traceback" not in output, output


@pytest.mark.parametrize("module", MAIN_MODULES)
def test_package_entry_point_prints_usage_without_arguments(module):
    package = module.rsplit(".", 1)[0]
    result = _run(["-m", package])
    output = result.stdout + result.stderr
    assert "usage" in output.lower() and "Traceback" not in output, output
