# ============================================================================
# backend/app/services/web_scraper/duyurular_scraper.py - Duyurular Scraper
# ============================================================================

import logging
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from .http_utils import fetch_with_retry

logger = logging.getLogger(__name__)

DUYURULAR_URL = "https://www.artvin.edu.tr/tr/duyuru/tumu"
MAX_DUYURU = 7


def scrape_announcements() -> Optional[str]:
    """
    AÇÜ duyurular sayfasından son MAX_DUYURU kadar duyuruyu çeker.
    Hata durumunda None döner.
    """
    try:
        logger.info("Duyurular sayfası taranıyor...")
        r = fetch_with_retry(DUYURULAR_URL)
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
