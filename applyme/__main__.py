"""Run the API server via ``python -m applyme``."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("APPLYME_HOST", "127.0.0.1")
    port = int(os.environ.get("APPLYME_PORT", "8000"))
    uvicorn.run("applyme.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
