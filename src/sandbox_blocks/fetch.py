"""Read one public web page as bounded plain text.

Limitation: DNS rebinding between validation and connection is not prevented
here. Production agents that read untrusted URLs need network egress controls.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable, Optional

USER_AGENT = "SandboxBlocks/0.1 (+page reader)"
SKIPPED_TAGS = {"script", "style", "noscript", "template"}

Resolver = Callable[[str], list[str]]
Reader = Callable[[str, float, int], bytes]


@dataclass(frozen=True)
class PageContent:
    url: str
    title: str
    text: str


def validate_url(url: str, resolver: Optional[Resolver] = None) -> str:
    """Return the URL if it is http(s) and every resolved address is public; else raise ValueError."""
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs can be read")
    host = parts.hostname
    if not host:
        raise ValueError("URL has no host")
    addresses = [host] if _is_ip_literal(host) else (resolver or _resolve)(host)
    if not addresses:
        raise ValueError("Host did not resolve")
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("Host must resolve to a public address")
    return parts.geturl()


def extract_text(html: str, max_chars: int) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    title = " ".join(parser.title.split())
    text = "\n".join(" ".join(block.split()) for block in parser.blocks if block.strip())
    return title, text[:max_chars]


def fetch_page(url: str, *, max_chars: int = 8000, timeout: float = 30,
               reader: Optional[Reader] = None, resolver: Optional[Resolver] = None) -> PageContent:
    checked = validate_url(url, resolver=resolver)
    body = (reader or _read_bytes)(checked, timeout, max_chars * 4)
    title, text = extract_text(body.decode("utf-8", errors="replace"), max_chars)
    return PageContent(url=checked, title=title, text=text)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}:
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip_depth:
            if not self.blocks:
                self.blocks.append("")
            self.blocks[-1] += data


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return []
    return [info[4][0] for info in infos]


class _ValidatingRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_bytes(url: str, timeout: float, max_bytes: int) -> bytes:
    opener = urllib.request.build_opener(_ValidatingRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=timeout) as response:
        return response.read(max_bytes)
