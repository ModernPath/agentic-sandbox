"""Search results as bounded, safe sources. Search results and page text are untrusted."""

from __future__ import annotations

import re

MAX_SOURCES = 5
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def search_query(name: str) -> str:
    return f'"{name}" news'


def safe_sources(results) -> list[dict]:
    """http(s) results only, at most MAX_SOURCES, each as {title, url}."""
    sources = []
    for result in results:
        url = (result.url or "").strip()
        if url.startswith(("https://", "http://")) and len(url) <= 2000:
            sources.append({"title": clean(result.title)[:200] or url, "url": url})
        if len(sources) == MAX_SOURCES:
            break
    return sources


def clean(value) -> str:
    return _CONTROL.sub("", str(value or ""))
