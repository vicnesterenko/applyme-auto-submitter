"""FastAPI application exposing the auto-submit service over HTTP."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from . import __version__
from .config import get_settings
from .lever import USER_AGENT, LeverPostingsClient
from .models import BatchSummary, Candidate
from .profile import (
    load_profile_file,
    profile_to_candidate,
    resume_pdf_from_file,
    resume_text_from_file,
)
from .sample_data import DEFAULT_JOB_URLS
from .service import submit_applications
from .templates import index_page

_SUCCESS_STATUSES = ("success", "dry_run")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create one shared HTTP client + settings for the app's lifetime."""
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.request_timeout,
        headers={"User-Agent": USER_AGENT},
    ) as http:
        app.state.http = http
        app.state.settings = settings
        yield


app = FastAPI(
    title="ApplyMe Auto Submitter",
    description="Подача заявок на Lever через офіційний Postings API.",
    version=__version__,
    lifespan=lifespan,
)


def get_lever_client(request: Request) -> LeverPostingsClient:
    """Dependency: build a client backed by the shared HTTP connection pool."""
    return LeverPostingsClient(request.app.state.http, request.app.state.settings)


def _parse_urls(raw: str | None) -> list[str]:
    """Split a newline/comma/space separated string into a list of URLs."""
    if not raw or not raw.strip():
        return list(DEFAULT_JOB_URLS)
    parts = raw.replace(",", "\n").split("\n")
    urls = [u.strip() for u in parts if u.strip()]
    return urls or list(DEFAULT_JOB_URLS)


async def _save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    """Persist an uploaded file to ``dest_dir``, preserving its suffix."""
    suffix = Path(upload.filename or "").suffix
    dest = dest_dir / f"{Path(upload.filename or 'upload').stem}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    await upload.close()
    return dest


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return index_page(DEFAULT_JOB_URLS)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/apply", response_model=BatchSummary)
async def apply(
    resume: UploadFile = File(..., description="Резюме (.pdf/.docx/.txt/.md)"),
    profile: UploadFile = File(..., description="Профіль кандидата (.docx/.json)"),
    urls: str | None = Form(None, description="URL вакансій Lever"),
    dry_run: bool = Form(True, description="True — лише перевірити, без подачі"),
    client: LeverPostingsClient = Depends(get_lever_client),
) -> BatchSummary:
    """Upload resume + profile and submit applications via the Postings API."""
    job_urls = _parse_urls(urls)
    work_dir = Path(tempfile.mkdtemp(prefix="applyme_"))

    try:
        resume_file = await _save_upload(resume, work_dir)
        profile_file = await _save_upload(profile, work_dir)

        try:
            profile_data = load_profile_file(profile_file)
        except Exception as exc:  # noqa: BLE001 - surfaced to the client as 422
            raise HTTPException(
                status_code=422,
                detail=f"Не вдалося розпарсити профіль кандидата: {exc}",
            ) from exc

        candidate_data = profile_to_candidate(
            profile_data, _resume_text_safe(resume_file)
        )

        try:
            candidate = Candidate.model_validate(candidate_data)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"У профілі бракує обовʼязкових полів (імʼя/email): {exc}",
            ) from exc

        resume_pdf = resume_pdf_from_file(resume_file, work_dir / "resume.pdf")

        results = await submit_applications(
            candidate,
            resume_pdf,
            job_urls,
            dry_run=dry_run,
            settings=client._settings,  # noqa: SLF001 - intentional shared settings
            client=client,
        )

        succeeded = sum(1 for r in results if r.status.startswith(_SUCCESS_STATUSES))
        return BatchSummary(
            candidate_name=candidate.name,
            candidate_email=str(candidate.email),
            dry_run=dry_run,
            total=len(results),
            succeeded=succeeded,
            results=results,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _resume_text_safe(resume_file: Path) -> str:
    """Best-effort resume text extraction for the candidate summary."""
    try:
        return resume_text_from_file(resume_file)
    except Exception:  # noqa: BLE001 - summary text is optional
        return ""
