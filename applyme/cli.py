"""Command-line runner: apply to postings and write ``results.json``.

Examples::

    # Dry-run (default) against the bundled sample profile + 5 test postings:
    python -m applyme.cli

    # Real submission (requires APPLYME_LEVER_API_KEY / per-site keys):
    python -m applyme.cli --no-dry-run --profile profile.json --resume resume.pdf
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .config import get_settings
from .models import Candidate
from .profile import (
    ensure_resume_pdf,
    load_profile_file,
    parse_resume_docx,
    profile_to_candidate,
    resume_pdf_from_file,
    resume_text_from_file,
)
from .sample_data import DEFAULT_JOB_URLS, SAMPLE_PROFILE_DOCX, SAMPLE_RESUME_DOCX
from .service import submit_applications


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="applyme", description=__doc__)
    parser.add_argument("urls", nargs="*", help="Lever posting URLs (default: bundled sample)")
    parser.add_argument("--profile", type=Path, help="Profile file (.json/.docx)")
    parser.add_argument("--resume", type=Path, help="Resume file (.pdf/.docx/.txt/.md)")
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Validate postings without submitting (default: on)",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("results.json"), help="Where to write results"
    )
    return parser


def _load_inputs(args: argparse.Namespace) -> tuple[Candidate, str]:
    """Resolve the candidate + resume PDF from CLI args or bundled samples."""
    if args.profile:
        profile_data = load_profile_file(args.profile)
        resume_text = resume_text_from_file(args.resume) if args.resume else ""
    else:
        profile_data = load_profile_file(SAMPLE_PROFILE_DOCX)
        resume_text = parse_resume_docx(SAMPLE_RESUME_DOCX)

    candidate = Candidate.model_validate(profile_to_candidate(profile_data, resume_text))

    if args.resume:
        resume_pdf = resume_pdf_from_file(args.resume, Path("resume.pdf"))
    else:
        resume_pdf = ensure_resume_pdf()

    return candidate, resume_pdf


async def _run(args: argparse.Namespace) -> int:
    urls = args.urls or list(DEFAULT_JOB_URLS)
    candidate, resume_pdf = _load_inputs(args)

    results = await submit_applications(
        candidate, resume_pdf, urls, dry_run=args.dry_run, settings=get_settings()
    )

    payload = [r.model_dump(exclude_none=True) for r in results]
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in results:
        print(f"{r.status:<22} {r.url}")
    print(f"\nWrote {len(results)} results to {args.out}")
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
