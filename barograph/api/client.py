"""Minimal HTTP client with retries and an injectable transport.

The default transport uses :mod:`urllib` from the standard library so the
package does not depend on third-party HTTP libraries. Callers can supply a
custom ``transport`` callable (for example a cache or a ``requests``-style
function) while keeping the same signature::

    transport(url: str, **kwargs) -> tuple[int, str]

returning ``(status_code, body_text)``.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from loguru import logger

Transport = Callable[..., tuple[int, str]]


def _default_transport(url: str, **kwargs: Any) -> tuple[int, str]:
    """Perform an HTTP GET and return ``(status, body)``."""
    req = urllib.request.Request(url, headers={"User-Agent": "barograph/0.1"})
    with urllib.request.urlopen(req, timeout=kwargs.get("timeout", 10)) as resp:
        body = resp.read().decode(kwargs.get("encoding", "utf-8"))
        return resp.status, body


class HTTPError(RuntimeError):
    """Raised when an HTTP request ultimately fails."""


class HTTPClient:
    """Retrying JSON HTTP client over an injectable transport.

    Args:
        transport: Callable returning ``(status_code, body_text)``; defaults to urllib.
        max_retries: Number of retries after the first attempt.
        backoff_seconds: Base backoff between retries (exponential).
        timeout_seconds: Per-request timeout.
    """

    def __init__(
        self,
        transport: Transport | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 0.1,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.transport = transport or _default_transport
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.timeout_seconds = timeout_seconds

    def get_json(self, url: str, **params: Any) -> dict[str, Any]:
        """GET *url* with query parameters and parse the JSON response."""
        body = self.get_text(url, **params)
        if not body:
            raise HTTPError(f"Empty response from {url}")
        return json.loads(body)

    def get_text(self, url: str, **params: Any) -> str:
        """GET *url* with query parameters, retrying on failure."""
        if params:
            sep = "&" if "?" in url else "?"
            qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
            url = f"{url}{sep}{qs}"

        attempts = self.max_retries + 1
        backoff = self.backoff_seconds
        for attempt in range(attempts):
            try:
                status, body = self.transport(url, timeout=self.timeout_seconds)
            except Exception as exc:  # noqa: BLE001 - transport failures vary
                status, body = 0, str(exc)
            if 200 <= status < 300:
                return body
            if attempt < attempts - 1:
                logger.warning(
                    "HTTP {status} from {url}; retry {attempt}/{attempts}",
                    status=status,
                    url=url,
                    attempt=attempt + 1,
                    attempts=attempts,
                )
                time.sleep(backoff)
                backoff *= 2
        raise HTTPError(f"Request to {url} failed with status {status}")
