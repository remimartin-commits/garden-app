"""Shim: pool quote enquiries live in ``app.pool.quote_enquiries``."""

from __future__ import annotations

import app.pool.quote_enquiries as _impl
from app.pool.quote_enquiries import *  # noqa: F403

RATE_LIMIT_BUCKET = _impl.RATE_LIMIT_BUCKET
_RATE_LIMIT_BUCKET = RATE_LIMIT_BUCKET

gst_rate = 0.15  # Default GST rate