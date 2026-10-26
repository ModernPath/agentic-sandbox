import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sandbox_host.scaffold import ScaffoldError, scaffold

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    """A copy of the parts of the repository the scaffolder reads and writes."""
    (tmp_path / "templates").mkdir()
    shutil.copytree(ROOT / "templates" / "host_agent", tmp_path / "templates" / "host_agent")
    (tmp_path / "agents").mkdir()
    (tmp_path / "sandbox_app.py").write_text(
        "from sandbox_host.app import create_app\n"
        "# <scaffold:imports>\n"
        "AGENTS = [\n"
        "    # <scaffold:agents>\n"
        "]\n")
    return tmp_path


def test_scaffold_creates_all_template_files_with_names_substituted(repo):  # G-7
    target = scaffold(repo, "notes-demo")
    assert target == repo / "agents" / "notes_demo"
    names = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    assert {"api.py", "store.py", "models.py", "service.py", "tools.py", "cli.py", "README.md", "AGENTS.md",
            "migrations/0001_init.sql", "migrations/0001_init.down.sql", "ui/index.html", "tests/test_api.py",
            "tests/test_standard.py", "tests/conftest.py", "__init__.py"} <= set(names)
    assert not any(n.endswith(".tpl") for n in names)
    assert "$" not in (target / "api.py").read_text()
    assert "notes_demo" in (target / "store.py").read_text()


def test_scaffold_refuses_to_overwrite(repo):  # G-8
    scaffold(repo, "notes-demo")
    with pytest.raises(ScaffoldError, match="exists"):
        scaffold(repo, "notes-demo")


@pytest.mark.parametrize("name", ["Bad Name", "1x", "a", "under_score"])
def test_scaffold_refuses_invalid_names(repo, name):  # G-9
    with pytest.raises(ScaffoldError):
        scaffold(repo, name)
    assert not (repo / "agents").joinpath(name.replace("-", "_")).exists()


def test_scaffold_registers_the_agent(repo):  # G-10
    scaffold(repo, "notes-demo")
    app_file = (repo / "sandbox_app.py").read_text()
    assert "from notes_demo.api import make_agent_spec as make_notes_demo_spec" in app_file
    assert "    make_notes_demo_spec()," in app_file
    compile(app_file, "sandbox_app.py", "exec")


def test_missing_marker_fails_before_writing_anything(repo):  # G-11
    (repo / "sandbox_app.py").write_text("AGENTS = []\n")
    with pytest.raises(ScaffoldError, match="scaffold:imports"):
        scaffold(repo, "notes-demo")
    assert not (repo / "agents" / "notes_demo").exists()


def test_generated_agent_tests_pass(repo):  # G-12
    scaffold(repo, "notes-demo")
    env = {"PYTHONPATH": str(ROOT / "src") + ":" + str(repo / "agents"), "PATH": "/usr/bin:/bin"}
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                            cwd=repo / "agents" / "notes_demo", env=env, capture_output=True, text=True, timeout=170)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_migration_only_creates_prefixed_tables(repo):  # G-13
    import re

    scaffold(repo, "notes-demo")
    sql = (repo / "agents" / "notes_demo" / "migrations" / "0001_init.sql").read_text()
    tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql)
    assert tables and all(t.startswith("notes_demo_") for t in tables)


def test_generated_ui_sends_the_sandbox_header(repo):  # G-14
    scaffold(repo, "notes-demo")
    html = (repo / "agents" / "notes_demo" / "ui" / "index.html").read_text()
    assert "'X-Sandbox-Request': '1'" in html
