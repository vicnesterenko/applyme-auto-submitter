"""Orchestration: apply to a list of Lever postings and record the outcome.

For each URL the flow is:

1. Parse the URL into ``site`` + ``posting_id``.
2. ``GET`` the posting to confirm it is published and capture its title.
3. If ``dry_run`` — stop here and record ``dry_run``.
4. Otherwise look up the site's Postings API key; if none is configured record
   ``skipped:no_api_key``; if present, ``POST`` the application and record
   ``success`` (with ``applicationId``) or ``failed:<detail>``.

A randomised delay separates consecutive submissions to respect rate limits.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Sequence
from pathlib import Path

import httpx

from .config import Settings, get_settings
from .lever import USER_AGENT, LeverError, LeverPostingsClient, parse_posting_url
from .models import ApplicationResult, ApplyStatus, Candidate


async def submit_applications(
    candidate: Candidate,
    resume_path: str | Path,
    urls: Sequence[str],
    *,
    dry_run: bool = True,
    settings: Settings | None = None,
    client: LeverPostingsClient | None = None,
) -> list[ApplicationResult]:
    """Apply to each posting in ``urls`` and return one result per URL.

    If ``client`` is omitted a short-lived :class:`httpx.AsyncClient` is created
    (useful for CLI / scripts); the FastAPI app passes a shared client.
    """
    settings = settings or get_settings()

    if client is not None:
        return await _run(client, settings, candidate, resume_path, urls, dry_run)

    async with httpx.AsyncClient(
        timeout=settings.request_timeout,
        headers={"User-Agent": USER_AGENT},
    ) as http:
        owned_client = LeverPostingsClient(http, settings)
        return await _run(owned_client, settings, candidate, resume_path, urls, dry_run)


async def _run(
    client: LeverPostingsClient,
    settings: Settings,
    candidate: Candidate,
    resume_path: str | Path,
    urls: Sequence[str],
    dry_run: bool,
) -> list[ApplicationResult]:
    results: list[ApplicationResult] = []
    last_index = len(urls) - 1
    for index, url in enumerate(urls):
        results.append(
            await _apply_one(client, settings, candidate, resume_path, url, dry_run)
        )
        if index != last_index:
            await asyncio.sleep(_delay(settings))
    return results


async def _apply_one(
    client: LeverPostingsClient,
    settings: Settings,
    candidate: Candidate,
    resume_path: str | Path,
    url: str,
    dry_run: bool,
) -> ApplicationResult:
    try:
        posting = parse_posting_url(url)
    except LeverError as exc:
        return ApplicationResult(
            url=url, status=ApplyStatus.FAILED.with_detail(exc.message)
        )

    site, posting_id = posting.site, posting.posting_id

    try:
        posting = await client.get_posting(posting)
    except LeverError as exc:
        return ApplicationResult(
            url=url,
            site=site,
            posting_id=posting_id,
            status=ApplyStatus.FAILED.with_detail(exc.message),
        )

    base = {
        "url": url,
        "site": site,
        "posting_id": posting_id,
        "title": posting.text,
    }

    if dry_run:
        return ApplicationResult(**base, status=ApplyStatus.DRY_RUN.value)

    api_key = settings.key_for(site)
    if not api_key:
        return ApplicationResult(**base, status=ApplyStatus.SKIPPED_NO_KEY.value)

    try:
        application_id = await client.apply(
            posting, candidate, resume_path, api_key=api_key
        )
    except LeverError as exc:
        return ApplicationResult(
            **base, status=ApplyStatus.FAILED.with_detail(exc.message)
        )

    return ApplicationResult(
        **base, status=ApplyStatus.SUCCESS.value, application_id=application_id
    )


def _delay(settings: Settings) -> float:
    """Randomised inter-request delay within the configured range."""
    low, high = settings.min_delay, settings.max_delay
    if high <= low:
        return max(0.0, low)
    return random.uniform(low, high)
