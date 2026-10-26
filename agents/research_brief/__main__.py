"""CLI: python -m research_brief "topic". Providers come from environment variables."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from typing import Optional, Sequence

from sandbox_blocks.config import Settings
from sandbox_blocks.errors import ConfigurationError, ProviderError
from sandbox_blocks.readers import build_reader
from sandbox_blocks.llm import build_llm
from sandbox_blocks.search import build_search

from .brief import build_brief


def main(argv: Optional[Sequence[str]] = None, environ: Mapping[str, str] = os.environ) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print('usage: python -m research_brief "topic"', file=sys.stderr)
        return 2
    try:
        settings = Settings.from_env(environ)
        brief = build_brief(
            " ".join(args),
            search=build_search(settings),
            read_page=build_reader(settings).read,
            llm=build_llm(settings),
        )
    except (ConfigurationError, ProviderError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(brief.summary or brief.reason)
    for source in brief.sources:
        print(f"[{source.number}] {source.title} - {source.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
