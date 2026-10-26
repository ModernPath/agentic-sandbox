import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI_PAGES = [
    "agents/research_brief/ui/index.html",
    "agents/emeia_dashboard/ui/index.html",
]


@pytest.mark.parametrize("page", UI_PAGES)
def test_pages_with_unsafe_requests_send_the_sandbox_request_header(page):  # A-17
    html = (ROOT / page).read_text(encoding="utf-8")
    assert "method:" in html, f"{page}: expected requests to check"
    assert "'X-Sandbox-Request': '1'" in html, f"{page}: requests without the sandbox header"
