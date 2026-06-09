"""Client for Lever's official, public Postings API.

Reference: https://github.com/lever/postings-api

Endpoints used:

* ``GET  /v0/postings/{site}/{id}?mode=json`` — fetch a published posting.
* ``POST /v0/postings/{site}/{id}?key={api_key}`` — submit an application
  (multipart form). The apply endpoint requires a Postings API key that the
  site owner generates in Lever and shares with the integration.

No CAPTCHA solving, stealth, or anti-bot evasion is performed — this is the
sanctioned programmatic interface, and requests use an honest ``User-Agent``.
"""

from __future__ import annotations

import asyncio
import re
import secrets
from pathlib import Path

import httpx

from . import __version__
from .config import Settings
from .models import Candidate, JobPosting

USER_AGENT = f"ApplyMe/{__version__} (+https://github.com/lever/postings-api)"

# jobs.lever.co/<site>/<uuid>[/apply], optionally on the EU instance.
_POSTING_RE = re.compile(
    r"""jobs(?P<eu>\.eu)?\.lever\.co/
        (?P<site>[^/?#]+)/
        (?P<posting_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}
                       -[0-9a-fA-F]{4}-[0-9a-fA-F]{12})""",
    re.VERBOSE,
)

# Status codes that are safe / worth retrying.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class LeverError(Exception):
    """Raised when a Lever API call fails (network, HTTP, or ``ok: false``)."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def parse_posting_url(url: str) -> JobPosting:
    """Parse a Lever job URL into a :class:`JobPosting`.

    Handles the ``/apply`` suffix, query strings, fragments, and the EU
    instance. Raises :class:`LeverError` for non-Lever or malformed URLs.
    """
    match = _POSTING_RE.search(url.strip())
    if not match:
        raise LeverError(f"Не схоже на URL вакансії Lever: {url}")
    return JobPosting(
        site=match.group("site"),
        posting_id=match.group("posting_id"),
        eu=bool(match.group("eu")),
    )


class LeverPostingsClient:
    """Thin async wrapper over the Lever Postings API."""

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def _base(self, posting: JobPosting) -> str:
        s = self._settings
        return s.lever_api_base_eu if posting.eu else s.lever_api_base

    def _posting_url(self, posting: JobPosting) -> str:
        return f"{self._base(posting)}/{posting.site}/{posting.posting_id}"

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        """Issue a request with bounded exponential backoff on transient errors."""
        attempts = self._settings.max_retries
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = await self._http.request(method, url, **kwargs)  # type: ignore[arg-type]
            except httpx.TransportError as exc:
                last_exc = exc
            else:
                if resp.status_code not in _RETRY_STATUS:
                    return resp
                last_exc = LeverError(
                    f"HTTP {resp.status_code}", status=resp.status_code
                )
                if attempt == attempts - 1:
                    return resp

            await asyncio.sleep(self._backoff_seconds(attempt))

        assert last_exc is not None  # pragma: no cover - defensive
        raise LeverError(f"Запит до Lever не вдався: {last_exc}")

    def _backoff_seconds(self, attempt: int) -> float:
        """Exponential backoff with full jitter."""
        ceiling = self._settings.backoff_base * (2 ** attempt)
        return secrets.SystemRandom().uniform(0, ceiling)

    async def get_posting(self, posting: JobPosting) -> JobPosting:
        """Fetch posting metadata; enriches title / hosted + apply URLs."""
        resp = await self._request(
            "GET",
            self._posting_url(posting),
            params={"mode": "json"},
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            raise LeverError("вакансію не знайдено або вона не опублікована", status=404)
        if resp.status_code >= 400:
            raise LeverError(f"HTTP {resp.status_code}", status=resp.status_code)

        data = resp.json()
        return posting.model_copy(
            update={
                "text": data.get("text"),
                "hosted_url": data.get("hostedUrl"),
                "apply_url": data.get("applyUrl"),
            }
        )

    async def apply(
        self,
        posting: JobPosting,
        candidate: Candidate,
        resume_path: str | Path,
        *,
        api_key: str,
        silent: bool | None = None,
    ) -> str:
        """Submit an application; returns Lever's ``applicationId`` on success."""
        if silent is None:
            silent = self._settings.silent

        data: dict[str, str] = {"name": candidate.name, "email": str(candidate.email)}
        if candidate.phone:
            data["phone"] = candidate.phone
        if candidate.org:
            data["org"] = candidate.org
        if candidate.linkedin:
            data["urls[LinkedIn]"] = candidate.linkedin
        if candidate.github:
            data["urls[GitHub]"] = candidate.github
        if candidate.portfolio:
            data["urls[Portfolio]"] = candidate.portfolio
        if silent:
            data["silent"] = "true"

        resume_path = Path(resume_path)
        files = {
            "resume": (
                resume_path.name,
                resume_path.read_bytes(),
                "application/pdf",
            )
        }

        resp = await self._request(
            "POST",
            self._posting_url(posting),
            params={"key": api_key},
            data=data,
            files=files,
        )

        return self._parse_apply_response(resp)

    @staticmethod
    def _parse_apply_response(resp: httpx.Response) -> str:
        try:
            body = resp.json()
        except ValueError:
            body = {}

        if resp.status_code >= 400 or not body.get("ok", False):
            detail = body.get("error") or f"HTTP {resp.status_code}"
            raise LeverError(str(detail), status=resp.status_code)
        return str(body.get("applicationId", ""))
