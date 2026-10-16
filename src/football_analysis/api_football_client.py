"""Dependency-free API-Football v3 client with bounded retries.

Network requests occur only when get() is explicitly called. The API key is
never logged or included in exception messages.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

API_BASE = "https://v3.football.api-sports.io"


class ApiFootballError(RuntimeError):
    """Base exception for provider errors."""


class ApiFootballAuthError(ApiFootballError):
    """The API key is missing or rejected."""


class ApiFootballRateLimitError(ApiFootballError):
    """The provider rejected a request due to rate limiting."""


class ApiFootballResponseError(ApiFootballError):
    """The provider returned an invalid or unsuccessful response."""


@dataclass(frozen=True)
class QuotaSnapshot:
    daily_limit: int | None = None
    daily_remaining: int | None = None
    minute_limit: int | None = None
    minute_remaining: int | None = None


def _int_header(headers: Any, name: str) -> int | None:
    try:
        value = headers.get(name)
        return int(value) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


class ApiFootballClient:
    """API-Football v3 HTTP client with safe authentication and bounded retries."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 25.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = (api_key if api_key is not None else os.environ.get("API_FOOTBALL_KEY", "")).strip()
        if not key:
            raise ApiFootballAuthError("Missing API_FOOTBALL_KEY environment variable")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        self._api_key = key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._opener = opener or urllib.request.urlopen
        self._sleep = sleep
        self.last_quota = QuotaSnapshot()

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        path = endpoint.strip().strip("/")
        if not path or "://" in path or "?" in path or path.startswith("."):
            raise ValueError("endpoint must be a relative API-Football v3 path")
        clean_params = {str(k): str(v) for k, v in (params or {}).items() if v is not None}
        query = urllib.parse.urlencode(clean_params)
        url = f"{API_BASE}/{path}" + (f"?{query}" if query else "")
        request = urllib.request.Request(
            url,
            headers={"x-apisports-key": self._api_key, "Accept": "application/json"},
            method="GET",
        )

        for attempt in range(self.max_retries + 1):
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    self._capture_quota(response.headers)
                    raw = response.read().decode("utf-8")
                    status = getattr(response, "status", 200)
                if status >= 500:
                    if attempt < self.max_retries:
                        self._sleep(self.backoff_seconds * (2 ** attempt))
                        continue
                    raise ApiFootballResponseError(f"API-Football returned HTTP {status} for {path}")
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ApiFootballResponseError(f"Invalid JSON returned by API-Football for {path}") from exc
                return self._validate_body(body, path)
            except urllib.error.HTTPError as exc:
                self._capture_quota(exc.headers)
                if exc.code in (401, 403):
                    raise ApiFootballAuthError(f"API-Football authentication/permission failed (HTTP {exc.code})") from exc
                if exc.code == 429:
                    if attempt >= self.max_retries:
                        raise ApiFootballRateLimitError(f"API-Football rate limit persisted for {path} after retries") from exc
                    retry_after = self._retry_after(exc.headers)
                    delay = retry_after if retry_after is not None else self.backoff_seconds * (2 ** attempt)
                    self._sleep(min(max(delay, 0.0), 60.0))
                    continue
                if exc.code >= 500 and attempt < self.max_retries:
                    self._sleep(self.backoff_seconds * (2 ** attempt))
                    continue
                raise ApiFootballResponseError(f"API-Football returned HTTP {exc.code} for {path}") from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt < self.max_retries:
                    self._sleep(self.backoff_seconds * (2 ** attempt))
                    continue
                raise ApiFootballError(f"API-Football network failure for {path}: {type(exc).__name__}") from exc
        raise ApiFootballError(f"API-Football request failed for {path}")

    def _capture_quota(self, headers: Any) -> None:
        self.last_quota = QuotaSnapshot(
            daily_limit=_int_header(headers, "x-ratelimit-requests-limit"),
            daily_remaining=_int_header(headers, "x-ratelimit-requests-remaining"),
            minute_limit=_int_header(headers, "X-RateLimit-Limit"),
            minute_remaining=_int_header(headers, "X-RateLimit-Remaining"),
        )

    @staticmethod
    def _retry_after(headers: Any) -> float | None:
        try:
            value = headers.get("Retry-After")
            return max(0.0, float(value)) if value is not None else None
        except (TypeError, ValueError, AttributeError):
            return None

    @staticmethod
    def _validate_body(body: Any, path: str) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise ApiFootballResponseError(f"Unexpected response shape for {path}")
        errors = body.get("errors")
        if errors:
            message = "provider validation error"
            if isinstance(errors, dict):
                safe_keys = ", ".join(str(key) for key in errors.keys())
                message = f"provider validation error ({safe_keys})"
            raise ApiFootballResponseError(f"API-Football rejected {path}: {message}")
        return body


_default_client: ApiFootballClient | None = None


def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Get JSON from API-Football using the configured environment key."""
    global _default_client
    if _default_client is None:
        _default_client = ApiFootballClient()
    return _default_client.get(path, params)
