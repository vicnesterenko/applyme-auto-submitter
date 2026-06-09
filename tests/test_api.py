"""End-to-end API tests via FastAPI's TestClient (Lever calls mocked)."""

from __future__ import annotations

import json

import httpx
import respx
from fastapi.testclient import TestClient

from applyme.api import app

PID = "6fd40837-f0c2-4e8a-b22c-ae94e9145732"

SAMPLE_PROFILE = {
    "personal_information": {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
    }
}


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@respx.mock
def test_apply_dry_run_returns_results():
    respx.get(f"https://api.lever.co/v0/postings/acme/{PID}").mock(
        return_value=httpx.Response(200, json={"text": "Engineer", "applyUrl": "a"})
    )
    files = {
        "resume": ("resume.txt", b"hello resume", "text/plain"),
        "profile": ("profile.json", json.dumps(SAMPLE_PROFILE).encode(), "application/json"),
    }
    data = {"urls": f"https://jobs.lever.co/acme/{PID}", "dry_run": "true"}

    with TestClient(app) as client:
        resp = client.post("/apply", data=data, files=files)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    assert body["total"] == 1
    assert body["succeeded"] == 1
    assert body["results"][0]["status"] == "dry_run"
    assert body["results"][0]["title"] == "Engineer"


@respx.mock
def test_apply_no_key_is_skipped():
    respx.get(f"https://api.lever.co/v0/postings/acme/{PID}").mock(
        return_value=httpx.Response(200, json={"text": "Engineer"})
    )
    files = {
        "resume": ("resume.txt", b"hello resume", "text/plain"),
        "profile": ("profile.json", json.dumps(SAMPLE_PROFILE).encode(), "application/json"),
    }
    # dry_run disabled, but no API key configured -> skipped:no_api_key
    data = {"urls": f"https://jobs.lever.co/acme/{PID}", "dry_run": "false"}

    with TestClient(app) as client:
        resp = client.post("/apply", data=data, files=files)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["results"][0]["status"] == "skipped:no_api_key"


def test_apply_invalid_profile_returns_422():
    files = {
        "resume": ("resume.txt", b"hello resume", "text/plain"),
        "profile": (
            "profile.json",
            json.dumps({"personal_information": {}}).encode(),
            "application/json",
        ),
    }
    data = {"urls": f"https://jobs.lever.co/acme/{PID}", "dry_run": "true"}

    with TestClient(app) as client:
        resp = client.post("/apply", data=data, files=files)

    assert resp.status_code == 422
