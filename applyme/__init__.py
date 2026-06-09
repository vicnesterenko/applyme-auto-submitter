"""ApplyMe — submit job applications to Lever via the official Postings API.

This package replaces the previous browser-automation / stealth approach with a
client for Lever's public, documented Postings API
(https://github.com/lever/postings-api). No CAPTCHA solving or anti-bot evasion
is performed: applications are submitted through the sanctioned
``POST /v0/postings/{site}/{id}`` endpoint, which requires a Postings API key
issued by the site owner.
"""

from __future__ import annotations

__version__ = "2.0.0"

__all__ = ["__version__"]
