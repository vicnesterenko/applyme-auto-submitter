"""Bundled sample data (the 5 test postings + example profile/resume).

These are only defaults for local experimentation; real input is supplied via
the ``POST /apply`` form.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = REPO_ROOT / "resourses"

SAMPLE_PROFILE_DOCX = RESOURCES_DIR / "profile_candidate.docx"
SAMPLE_RESUME_DOCX = RESOURCES_DIR / "resume.docx"

# The 5 postings provided with the test task.
DEFAULT_JOB_URLS: list[str] = [
    "https://jobs.lever.co/aledade/6fd40837-f0c2-4e8a-b22c-ae94e9145732",
    "https://jobs.lever.co/raptv/57dfc4b3-7853-401b-9887-459b23a58457",
    "https://jobs.lever.co/padsplit/8a9e818f-13a3-4591-8351-b1910fd971a8/apply",
    "https://jobs.lever.co/skillerszone/9322615b-cd4c-4d21-b414-a086a6311819",
    "https://jobs.lever.co/theathletic/12025a5f-02f4-4f03-802a-3d7466e2eb13",
]
