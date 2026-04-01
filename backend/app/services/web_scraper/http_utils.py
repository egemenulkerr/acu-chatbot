"""Ortak HTTP fetch utility — tüm scraper'lar tarafından kullanılır."""

import logging
from typing import Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


@retry(
    retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=False,
)
def fetch_with_retry(
    url: str,
    *,
    timeout: int = 12,
    headers: Optional[dict] = None,
) -> Optional[requests.Response]:
    """GET isteği yap, 3 denemeye kadar tekrar et; tüm denemeler başarısızsa None döner."""
    r = requests.get(url, timeout=timeout, headers=headers or DEFAULT_HEADERS)
    r.raise_for_status()
    return r
