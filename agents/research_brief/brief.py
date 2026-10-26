"""Research brief: search, read a few pages, and summarise with numbered citations.

Depends only on the building-block interfaces (`SearchClient`, `LLMClient`) and
on a `read_page` callable, so any provider selected by environment works here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from sandbox_blocks.llm import LLMClient
from sandbox_blocks.search import SearchClient

ReadPage = Callable[[str], object]  # returns an object with .title and .text


@dataclass(frozen=True)
class Source:
    number: int
    title: str
    url: str
    text: str


@dataclass(frozen=True)
class Brief:
    topic: str
    summary: Optional[str]
    sources: tuple[Source, ...] = field(default_factory=tuple)
    skipped: tuple[str, ...] = field(default_factory=tuple)
    provider: Optional[str] = None
    model: Optional[str] = None
    reason: Optional[str] = None


def build_brief(topic: str, *, search: SearchClient, read_page: ReadPage, llm: LLMClient,
                max_sources: int = 3) -> Brief:
    response = search.search(topic, max_results=max_sources * 2)
    sources: list[Source] = []
    skipped: list[str] = []
    for result in response.results:
        if len(sources) == max_sources:
            break
        try:
            page = read_page(result.url)
            title, text = getattr(page, "title", "") or result.title, getattr(page, "text", "")
        except Exception:  # a blocked or broken page must not stop the brief
            skipped.append(result.url)
            title, text = result.title, result.snippet
        if text.strip():
            sources.append(Source(number=len(sources) + 1, title=title, url=result.url, text=text))

    if not sources:
        return Brief(topic=topic, summary=None, skipped=tuple(skipped),
                     reason="No readable source text was found for this topic.")

    prompt = _prompt(topic, sources)
    answer = llm.complete(prompt)
    return Brief(topic=topic, summary=answer.text, sources=tuple(sources), skipped=tuple(skipped),
                 provider=answer.provider, model=answer.model)


def _prompt(topic: str, sources: list[Source]) -> str:
    blocks = [f"[{s.number}] {s.title} ({s.url})\n{s.text}" for s in sources]
    return (
        f"Write a short research brief on: {topic}\n"
        "Use only the numbered sources below. Cite each claim as [n]. "
        "If the sources do not cover the topic, say so.\n\n"
        + "\n\n".join(blocks)
    )
