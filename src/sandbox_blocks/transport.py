"""JSON-over-HTTPS transport. Standard library only; tests inject fakes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Callable, Optional

from .errors import ProviderError

JsonTransport = Callable[[str, Mapping[str, str], Optional[dict], float], dict]
ERROR_BODY_LIMIT = 300


def urllib_transport(url: str, headers: Mapping[str, str], body: Optional[dict], timeout: float) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Content-Type": "application/json", "Accept": "application/json", **headers}
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        detail = _redact(raw, headers.values())[:ERROR_BODY_LIMIT]
        raise ProviderError(f"Provider returned HTTP {error.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ProviderError(f"Provider request failed: {type(error).__name__}") from None


def _redact(text: str, secrets: Any) -> str:
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "[redacted]")
    return text
