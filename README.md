# ApplyMe Auto Submitter
Submit job applications to [Lever](https://www.lever.co/) on behalf of a
candidate **through Lever's official, public Postings API** — not via browser
automation, CAPTCHA solving, or anti-bot evasion.
## How it works
For every posting URL the service:
1. Parses the URL into `site` + `posting_id`.
2. `GET`s the posting JSON to confirm it is published and read its title.
3. In `dry_run` mode, stops there (status `dry_run`).
4. Otherwise submits the application via
   `POST /v0/postings/{site}/{id}?key={api_key}` and records `success`
   (with `applicationId`), `failed:<detail>`, or — when no Postings API key is
   configured for that site — `skipped:no_api_key`.
The apply endpoint requires a Postings API key that the **site owner** generates
in Lever (Settings → Integrations and API → API Credentials → Postings API) and
shares with the integration. That is by design: it is the sanctioned way to
submit applications programmatically.
## Layout
```
applyme/
  api.py          FastAPI app (routes, lifespan-managed HTTP client)
  service.py      orchestration: apply to a list of postings, record results
  lever.py        official Lever Postings API client (httpx)
  profile.py      profile/resume parsing + resume-PDF generation
  models.py       Pydantic models (Candidate, JobPosting, results)
  config.py       env-based settings (Postings API keys, timeouts, delays)
  cli.py          `python -m applyme.cli` runner -> results.json
  templates.py    minimal HTML upload form
tests/            pytest suite (profile, lever client, API)
```
## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # runtime
pip install -r requirements-dev.txt        # + tests/lint
cp .env.example .env                       # add Postings API key(s) if you have them
```
## Run
```bash
uvicorn app:app --reload                   # http://127.0.0.1:8000  (docs at /docs)
python -m applyme                          # same server
python -m applyme.cli                      # CLI dry-run over the bundled sample -> results.json
```
## Test & lint
```bash
pytest
ruff check .
```
## Configuration (env, prefix `APPLYME_`)
- `APPLYME_LEVER_API_KEY` — default Postings API key.
- `APPLYME_LEVER_API_KEYS` — JSON map `{"<site>": "<key>"}` for per-site keys.
- `APPLYME_SILENT` — suppress Lever's confirmation email (`true`/`false`).
- `APPLYME_REQUEST_TIMEOUT`, `APPLYME_MAX_RETRIES`, `APPLYME_MIN_DELAY`,
  `APPLYME_MAX_DELAY` — HTTP and politeness-delay tuning.
See [`REPORT.md`](REPORT.md) for the approach, the requests the frontend/API
makes, limitations, and what is needed to scale to ~1000s of applications.
