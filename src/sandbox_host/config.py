"""Host settings read from the environment once at startup."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class HostSettings:
    database_url: Optional[str] = None
    host: str = "127.0.0.1"
    port: int = 8100

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> "HostSettings":
        url = (environ.get("DATABASE_URL") or "").strip() or None
        host = (environ.get("SANDBOX_HOST") or "127.0.0.1").strip()
        port_raw = (environ.get("SANDBOX_PORT") or "8100").strip()
        try:
            port = int(port_raw)
        except ValueError as error:
            raise ValueError("SANDBOX_PORT must be an integer") from error
        return cls(database_url=url, host=host, port=port)

    def is_loopback(self) -> bool:
        if self.host == "localhost":
            return True
        try:
            return ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            return False
