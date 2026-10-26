import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_composition_root_fails_closed_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import sandbox_app

    client = TestClient(sandbox_app.create_sandbox_app())
    assert client.get("/api/health").json()["database"] == "not_configured"
    response = client.get("/api/agents")  # sign-in needs the database, so protected routes refuse
    assert response.status_code == 503 and response.json()["error"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_research_brief_ui_script_is_valid_javascript(tmp_path):  # S27
    html = (ROOT / "agents/research_brief/ui/index.html").read_text()
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 1
    script = tmp_path / "ui.js"
    script.write_text(scripts[0])
    result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
