"""Pydantic models shared across the service."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr


class Candidate(BaseModel):
    """Normalised candidate profile used to build a Lever application.

    Extra keys produced by :func:`applyme.profile.profile_to_candidate` (e.g.
    ``skills``, ``target_job_titles``) are preserved via ``extra="allow"`` but
    only the fields below are sent to Lever.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    email: EmailStr
    phone: str | None = None
    org: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    summary: str | None = None


class JobPosting(BaseModel):
    """A Lever posting identified by ``site`` + ``posting_id``."""

    site: str
    posting_id: str
    eu: bool = False
    text: str | None = None
    hosted_url: str | None = None
    apply_url: str | None = None


class ApplyStatus(str, Enum):
    """High-level outcome categories for a single application."""

    SUCCESS = "success"
    DRY_RUN = "dry_run"
    SKIPPED_NO_KEY = "skipped:no_api_key"
    FAILED = "failed"

    def with_detail(self, detail: str) -> str:
        """Render a status string, appending ``detail`` for failures."""
        if self is ApplyStatus.FAILED and detail:
            return f"{self.value}:{detail}"
        return self.value


class ApplicationResult(BaseModel):
    """Result recorded for each posting (matches the task's status format)."""

    url: str
    site: str | None = None
    posting_id: str | None = None
    title: str | None = None
    status: str
    application_id: str | None = None


class BatchSummary(BaseModel):
    """Aggregate response returned by ``POST /apply``."""

    candidate_name: str
    candidate_email: str
    dry_run: bool
    total: int
    succeeded: int
    results: list[ApplicationResult]
