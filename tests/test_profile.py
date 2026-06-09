"""Tests for the neutral profile/resume parsing logic."""

from __future__ import annotations

import json
from pathlib import Path

from applyme.profile import build_resume_pdf, load_profile_file, profile_to_candidate

SAMPLE_PROFILE = {
    "personal_information": {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "phone_number": "5551234",
        "country_code": "+1",
        "city": "London",
        "country": "UK",
    },
    "miscellaneous": {
        "linkedin_url": "https://linkedin.com/in/ada",
        "total_experience": "10",
    },
    "work_experience": [
        {
            "job_title": "Engineer",
            "company": "Analytical Engines",
            "currently_work_here": True,
            "description": "Built the first algorithm.",
        }
    ],
    "skills": [{"skill": "Python"}, {"skill": "Mathematics"}],
}


def test_profile_to_candidate_maps_core_fields():
    candidate = profile_to_candidate(SAMPLE_PROFILE, resume_text="Resume text")
    assert candidate["name"] == "Ada Lovelace"
    assert candidate["email"] == "ada@example.com"
    assert candidate["phone"] == "+15551234"
    assert candidate["org"] == "Analytical Engines"
    assert "Python" in candidate["skills"]
    assert candidate["linkedin"].endswith("/ada")
    assert "London" in candidate["location"]


def test_phone_not_double_prefixed():
    profile = {
        "personal_information": {
            "first_name": "A",
            "last_name": "B",
            "email": "a@b.co",
            "phone_number": "+15551234",
            "country_code": "+1",
        }
    }
    assert profile_to_candidate(profile)["phone"] == "+15551234"


def test_load_profile_file_json(tmp_path: Path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(SAMPLE_PROFILE), encoding="utf-8")
    data = load_profile_file(p)
    assert data["personal_information"]["email"] == "ada@example.com"


def test_build_resume_pdf_creates_file(tmp_path: Path):
    out = tmp_path / "resume.pdf"
    path = build_resume_pdf("Hello\n\nWorld", out)
    assert Path(path).exists()
    assert out.stat().st_size > 0
