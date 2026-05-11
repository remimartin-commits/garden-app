"""Outbound connectivity probe (cheap HEAD request)."""

from __future__ import annotations

import logging
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def probe_online(url: str, *, timeout_seconds: float = 3.0) -> bool:
    if not url or not url.strip():
        return False
    target = url.strip()
    if sys.version_info >= (3, 10):
        req = Request(target, method="HEAD")
    else:
        req = Request(target)
        req.get_method = lambda: "HEAD"
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            return 200 <= (resp.status or 0) < 500
    except URLError as e:
        logger.debug("Connectivity probe failed: %s", e)
        return False
    except Exception as e:
        logger.debug("Connectivity probe error: %s", e)
        return False
