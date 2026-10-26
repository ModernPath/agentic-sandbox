"""Plain-text CLI kept for existing callers: python -m people_company_search people|company "<query>"

Runs one Exa Agent list build, waits for it to finish, and prints each item with its sources.
Use `python -m people_company_search.cli` for JSON output.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from typing import Optional, Sequence

from sandbox_blocks.errors import ConfigurationError, ProviderError

from . import service
from .cli import build_client
from .schemas import clean_text

USAGE = 'usage: python -m people_company_search people|company "<query>"'


def main(argv: Optional[Sequence[str]] = None, environ: Mapping[str, str] = os.environ, client=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] not in service.KINDS:
        print(USAGE, file=sys.stderr)
        return 2
    kind = args[0]
    query = " ".join(args[1:]).strip()
    try:
        agent = client if client is not None else build_client(environ)
        result = service.run_search(agent, kind, query)
    except ValueError as error:
        print(f"error: {clean_text(error)}", file=sys.stderr)
        return 2
    except (ConfigurationError, ProviderError) as error:
        print(f"error: {clean_text(error)}", file=sys.stderr)
        return 1

    key = service.KINDS[kind][0]
    cost = f"${result['cost']:.2f}" if result["cost"] is not None else "unknown"
    print(f"{len(result['items'])} {key} found (run {result['run_id']}, cost {cost})")
    for item in result["items"]:
        print(_format_item(kind, item))
    return 0


def _format_item(kind: str, item: dict) -> str:
    if kind == "people":
        line = f"- {item['name']} — {item['job_title']}, {item['company']}"
    else:
        line = f"- {item['name']} — {item['industry']}"
    return f"{line} ({', '.join(item['sources'])})" if item["sources"] else f"{line} (unsourced)"


if __name__ == "__main__":
    raise SystemExit(main())
