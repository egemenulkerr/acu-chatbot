# ============================================================================
# backend/app/services/web_scraper/duyurular_scraper.py - Duyurular Scraper
# ============================================================================

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

DUYURULAR_URL = "https://www.artvin.edu.tr/tr/duyuru/tumu"
MAX_DUYURU = 7

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


@retry(
    retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=False,
)
def _fetch_announcements_page(url: str, headers: dict, timeout: int = 12):
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r


def scrape_announcements() -> Optional[str]:
    """
    AÇÜ duyurular sayfasından son MAX_DUYURU kadar duyuruyu çeker.
    Hata durumunda None döner.
    """
    try:
        logger.info("Duyurular sayfası taranıyor...")
        r = _fetch_announcements_page(DUYURULAR_URL, HEADERS)
        if r is None:
            logger.error("Duyurular sayfası 3 denemede de alınamadı.")
            return None

        soup = BeautifulSoup(r.content, "html.parser")
        items = []

        # Birincil: div.duyuruMetni > a yapısı (artvin.edu.tr/tr/duyuru/tumu)
        for div in soup.find_all("div", class_="duyuruMetni"):
            a = div.find("a")
            if a:
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://www.artvin.edu.tr" + href
                if title and len(title) > 5:
                    items.append((title, href))
                    if len(items) >= MAX_DUYURU:
                        break

        # Yedek: genel duyuru linklerini tara
        if not items:
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if "/duyuru/" in href and title and len(title) > 10:
                    if not href.startswith("http"):
                        href = "https://www.artvin.edu.tr" + href
                    items.append((title, href))
                    if len(items) >= MAX_DUYURU:
                        break

        if not items:
            logger.warning("Duyuru bulunamadı.")
            return None

        today = datetime.now().strftime("%d.%m.%Y")
        lines = [f"📢 **Son Duyurular** ({today})\n"]
        for i, (title, href) in enumerate(items, 1):
            lines.append(f"{i}. {title}\n   {href}")

        lines.append(f"\n🔗 Tüm duyurular: {DUYURULAR_URL}")
        logger.info(f"{len(items)} duyuru çekildi.")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Duyurular scraper hatası: {e}", exc_info=True)
        return None
