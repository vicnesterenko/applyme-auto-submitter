"""Tests for URL parsing and the Lever Postings API client (mocked)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from applyme.config import Settings
from applyme.lever import LeverError, LeverPostingsClient, parse_posting_url
from applyme.models import Candidate, JobPosting

PID = "6fd40837-f0c2-4e8a-b22c-ae94e9145732"


@pytest.fixture
def resume_file(tmp_path: Path) -> Path:
    p = tmp_path / "resume.pdf"
    p.write_bytes(b"%PDF-1.4 minimal test resume")
    return p


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(name="Ada Lovelace", email="ada@example.com", phone="+15551234")


def test_parse_posting_url_standard():
    posting = parse_posting_url(f"https://jobs.lever.co/aledade/{PID}")
    assert posting.site == "aledade"
    assert posting.posting_id == PID
    assert posting.eu is False


def test_parse_posting_url_apply_suffix_and_query():
    posting = parse_posting_url(f"https://jobs.lever.co/padsplit/{PID}/apply?ref=x")
    assert posting.site == "padsplit"
    assert posting.posting_id == PID


def test_parse_posting_url_eu_instance():
    posting = parse_posting_url(f"https://jobs.eu.lever.co/acme/{PID}")
    assert posting.eu is True


def test_parse_posting_url_invalid():
    with pytest.raises(LeverError):
        parse_posting_url("https://example.com/jobs/123")


@respx.mock
async def test_get_posting_success():
    route = respx.get(f"https://api.lever.co/v0/postings/acme/{PID}").mock(
        return_value=httpx.Response(
            200, json={"text": "Engineer", "hostedUrl": "h", "applyUrl": "a"}
        )
    )
    async with httpx.AsyncClient() as http:
        client = LeverPostingsClient(http, Settings())
        enriched = await client.get_posting(JobPosting(site="acme", posting_id=PID))

    assert route.called
    assert enriched.text == "Engineer"
    assert enriched.apply_url == "a"


@respx.mock
async def test_get_posting_404():
    respx.get(f"https://api.lever.co/v0/postings/acme/{PID}").mock(
        return_value=httpx.Response(404)
    )
    async with httpx.AsyncClient() as http:
        client = LeverPostingsClient(http, Settings())
        with pytest.raises(LeverError) as exc:
            await client.get_posting(JobPosting(site="acme", posting_id=PID))
    assert exc.value.status == 404


@respx.mock
async def test_apply_success(candidate: Candidate, resume_file: Path):
    respx.post(f"https://api.lever.co/v0/postings/acme/{PID}").mock(
        return_value=httpx.Response(200, json={"ok": True, "applicationId": "app_1"})
    )
    async with httpx.AsyncClient() as http:
        client = LeverPostingsClient(http, Settings(lever_api_key="k"))
        app_id = await client.apply(
            JobPosting(site="acme", posting_id=PID), candidate, resume_file, api_key="k"
        )
    assert app_id == "app_1"


@respx.mock
async def test_apply_failure_raises(candidate: Candidate, resume_file: Path):
    respx.post(f"https://api.lever.co/v0/postings/acme/{PID}").mock(
        return_value=httpx.Response(400, json={"ok": False, "error": "invalid email"})
    )
    async with httpx.AsyncClient() as http:
        client = LeverPostingsClient(http, Settings(lever_api_key="k"))
        with pytest.raises(LeverError) as exc:
            await client.apply(
                JobPosting(site="acme", posting_id=PID),
                candidate,
                resume_file,
                api_key="k",
            )
    assert "invalid email" in str(exc.value)
