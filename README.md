# applyme-auto-submitter

A [SeleniumBase](https://seleniumbase.io/) (UC / undetected-chromedriver mode) automation bot that
opens [Lever](https://www.lever.co/) job-application pages, fills them out from a candidate profile,
and (optionally) submits them. It builds the candidate data and a PDF résumé from `.docx` sources,
mimics human-like mouse/typing behavior to reduce bot detection, attempts to answer custom/required
fields automatically, solves hCaptcha via the 2Captcha API when needed, and writes a run report to
`resources/result_report/results.json`.

> ⚠️ Use responsibly. Automating form submissions on third-party sites may violate their Terms of
> Service. Keep `DRY_RUN` enabled while testing.

## Features

- **Human-like interaction** — randomized delays, scroll-into-view, `uc_click`, and per-character
  typing delays instead of fixed `sleep` calls.
- **Stealth** — runs Chrome through SeleniumBase UC mode, which masks `navigator.webdriver` and other
  common automation signals and manages a persistent Chrome profile.
- **Profile-driven** — reads a candidate profile and résumé from `.docx`, generates a Cyrillic-capable
  PDF résumé via ReportLab, and maps everything to the form fields.
- **Smart field filling** — heuristics for salary, sponsorship, relocation, work authorization,
  experience, cover-letter/motivation text, plus required radios, selects, and checkboxes, with
  per-company overrides for forms that need tailored handling.
- **CAPTCHA handling** — detects hCaptcha, extracts the `data-sitekey`, and solves it through the
  2Captcha API (when `TWO_CAPTCHA_API_KEY` is configured), then injects the token and submits.
- **Dry-run mode** — fills the form and screenshots it without clicking Submit.
- **Reporting** — per-URL status in a JSON report plus screenshots for the filled form, success, and
  error/timeout states.

## Requirements

- Python **3.13+**
- [Poetry](https://python-poetry.org/) 2.x
- Google Chrome (SeleniumBase downloads a matching ChromeDriver automatically on first run)

## Installation

```bash
# Install dependencies into a Poetry-managed virtualenv
poetry install
```

SeleniumBase manages the ChromeDriver binary automatically in UC mode, so no separate browser-install
step is required.

## Configuration

### Input files

Place these in `resources/`:

| File                               | Purpose                                                                          |
| ---------------------------------- | -------------------------------------------------------------------------------- |
| `resources/profile_candidate.docx` | Candidate profile — must contain a JSON block after a `profile creation` marker. |
| `resources/resume.docx`            | Résumé text, converted to `resources/pdf_resume/resume.pdf`.                     |

The PDF résumé is generated automatically on first run (and cached) by `helpers/docx_to_pdf.py`,
which downloads a DejaVuSans font (cached at `resources/DejaVuSans.ttf`) for Cyrillic support.

### Target jobs

Edit `JOBS_URLS` in `resources/values.py` to list the Lever job URLs to apply to. The bot appends
`/apply` automatically when needed.

### Environment variables

| Variable              | Default | Description                                                                  |
| --------------------- | ------- | ---------------------------------------------------------------------------- |
| `TWO_CAPTCHA_API_KEY` | _empty_ | 2Captcha API key. When unset, hCaptcha solving is skipped (manual fallback). |

### Run-mode toggles

`DRY_RUN` and the browser `headless` flag are constants in `apply_bot.py` rather than environment
variables:

- `DRY_RUN` (top of `apply_bot.py`) — when `True`, forms are filled and screenshotted but never
  submitted. Default is `False` (live submission).
- `headless` (in `main()`'s `DriverContext(...)`) — left `False`, since UC mode is most reliable with
  a visible browser window.

## Usage

```bash
# Run the apply flow over JOBS_URLS
poetry run python apply_bot.py

# With automated hCaptcha solving
TWO_CAPTCHA_API_KEY=your_key poetry run python apply_bot.py

# Alternative entry point: prints the parsed candidate JSON and regenerates the
# résumé PDF, then runs the same flow
poetry run python main.py
```

To do a safe test run without submitting, set `DRY_RUN = True` at the top of `apply_bot.py`.

### Outputs

- `resources/result_report/results.json` — list of `{url, status[, reason]}` results for the run.
- `resources/screenshots_auto_apply/*.png` — screenshots saved per job: `filled_form_*` (before
  submit), `success_sbase_*`, and `error_sbase_*` / `exception_sbase_*`.

## Project structure

```
apply_bot.py              # Entry point: orchestrates the apply flow over JOBS_URLS (SeleniumBase UC)
main.py                   # Alternate entry point: prints candidate JSON + rebuilds the résumé PDF, then runs
helpers/
  parse_docx.py           # Loads candidate profile + résumé from .docx, builds candidate dict
  docx_to_pdf.py          # Renders résumé text to PDF (ReportLab + DejaVuSans)
resources/
  values.py               # Config: JOBS_URLS, USER_AGENT, file paths, font URL, TWO_CAPTCHA_API_KEY
  profile_candidate.docx  # Candidate profile source (input)
  resume.docx             # Résumé source (input)
  pdf_resume/resume.pdf   # Generated PDF résumé
  result_report/          # results.json run report
  screenshots_auto_apply/ # Per-job screenshots
answers.md                # Written report answering the test-task questions
```

## Development

```bash
# Lint
poetry run ruff check .

# Tests
poetry run pytest
```
