# applyme-auto-submitter

A Playwright-based automation bot that opens [Lever](https://www.lever.co/) job-application pages,
fills them out from a candidate profile, and (optionally) submits them. It builds the candidate
data and a PDF résumé from `.docx` sources, mimics human-like mouse/typing behavior to reduce
bot detection, attempts to answer custom/required fields automatically, and writes a run report
to `results.json`.

> ⚠️ Use responsibly. Automating form submissions on third-party sites may violate their Terms of
> Service. Keep `DRY_RUN` enabled while testing.

## Features

- **Human-like interaction** — randomized mouse paths, click jitter, and per-character typing delays.
- **Stealth** — runs through [`playwright-stealth`](https://pypi.org/project/playwright-stealth/) with
  `AutomationControlled` disabled.
- **Profile-driven** — reads a candidate profile and résumé from `.docx`, generates a Cyrillic-capable
  PDF résumé via ReportLab, and maps everything to the form fields.
- **Smart field filling** — heuristics for salary, sponsorship, relocation, work authorization,
  experience, cover-letter/motivation text, plus required radios, selects, and checkboxes.
- **CAPTCHA awareness** — detects reCAPTCHA/hCAPTCHA frames and reports when a submission is blocked
  (no third-party solver is used).
- **Dry-run mode** — fills the form and screenshots it without clicking Submit.
- **Reporting** — per-URL status plus a JSON report and screenshots on success/error.

## Requirements

- Python **3.13+**
- [Poetry](https://python-poetry.org/) 2.x
- Playwright browser binaries (Chromium)

## Installation

```bash
# Install dependencies into a Poetry-managed virtualenv
poetry install

# Install the Chromium browser used by Playwright
poetry run playwright install chromium
```

## Configuration

### Input files

Place these in `resources/`:

| File                              | Purpose                                                            |
| --------------------------------- | ----------------------------------------------------------------- |
| `resources/profile_candidate.docx`| Candidate profile — must contain a JSON block after a `profile creation` marker. |
| `resources/resume.docx`           | Résumé text, converted to `resources/pdf_resume/resume.pdf`.      |

The PDF résumé is generated automatically on first run (and cached) by `helpers/docx_to_pdf.py`,
which downloads a DejaVuSans font for Cyrillic support.

### Target jobs

Edit `JOBS_URLS` in `resources/values.py` to list the Lever job URLs to apply to. The bot appends
`/apply` automatically when needed.

### Environment variables

| Variable   | Default | Description                                                       |
| ---------- | ------- | ----------------------------------------------------------------- |
| `DRY_RUN`  | `true`  | When not explicitly `false`, fills forms but never clicks Submit. |
| `HEADLESS` | `false` | Set to `true` to run the browser without a visible window.        |

## Usage

```bash
# Dry run (default) — fills forms, screenshots, no submission
poetry run python apply_bot.py

# Live submission, headless
DRY_RUN=false HEADLESS=true poetry run python apply_bot.py
```

### Outputs

- `results.json` — list of `{url, status}` results for the run.
- `*.png` — screenshots saved per job (dry-run, success, or error states).

## Project structure

```
apply_bot.py              # Entry point: orchestrates the apply flow over JOBS_URLS
helpers/
  parse_docx.py           # Loads candidate profile + résumé from .docx, builds candidate dict
  docx_to_pdf.py          # Renders résumé text to PDF (ReportLab + DejaVuSans)
resources/
  values.py               # Config: JOBS_URLS, USER_AGENT, file paths, font URL
  profile_candidate.docx  # Candidate profile source (input)
  resume.docx             # Résumé source (input)
  pdf_resume/resume.pdf   # Generated PDF résumé
```

## Development

```bash
# Lint
poetry run ruff check .

# Tests
poetry run pytest
```