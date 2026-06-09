"""Backward-compatible shim: the canonical list now lives in
``applyme.sample_data.DEFAULT_JOB_URLS``.
"""

from applyme.sample_data import DEFAULT_JOB_URLS as URLS

__all__ = ["URLS"]
