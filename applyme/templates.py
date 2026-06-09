"""Static HTML for the index page (kept tiny; no template engine dependency)."""

from __future__ import annotations

import html


def index_page(default_urls: list[str]) -> str:
    """Render the upload form, pre-filled with ``default_urls``."""
    urls_text = html.escape("\n".join(default_urls))
    return f"""<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ApplyMe Auto Submitter</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 640px;
            margin: 40px auto; padding: 0 16px; }}
    label {{ display: block; margin: 14px 0 4px; font-weight: 600; }}
    textarea, input[type=file] {{ width: 100%; box-sizing: border-box; }}
    textarea {{ height: 120px; font-family: monospace; }}
    .row {{ display: flex; align-items: center; gap: 8px; margin-top: 14px; }}
    button {{ margin-top: 20px; padding: 10px 20px; font-size: 15px; cursor: pointer; }}
    small {{ color: #666; font-weight: 400; }}
  </style>
</head>
<body>
  <h1>ApplyMe Auto Submitter</h1>
  <p>Подача заявок через офіційний Lever Postings API. Реальний сабміт потребує
     Postings API-ключа сайту (інакше вакансія позначається як
     <code>skipped:no_api_key</code>).</p>
  <form action="/apply" method="post" enctype="multipart/form-data">
    <label>Резюме <small>(.pdf, .docx, .txt, .md)</small></label>
    <input type="file" name="resume" accept=".pdf,.docx,.txt,.md" required>

    <label>Профіль кандидата <small>(.docx або .json)</small></label>
    <input type="file" name="profile" accept=".docx,.json" required>

    <label>URL вакансій <small>(по одному в рядку або через кому)</small></label>
    <textarea name="urls">{urls_text}</textarea>

    <div class="row">
      <input type="checkbox" id="dry_run" name="dry_run" value="true" checked>
      <label for="dry_run" style="margin:0;">
        Dry-run <small>(перевірити вакансію, але НЕ подавати)</small>
      </label>
    </div>

    <button type="submit">Запустити</button>
  </form>
</body>
</html>"""
