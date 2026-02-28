# ============================================================================
# backend/app/services/web_scraper/duyurular_scraper.py - Duyurular Scraper
# ============================================================================

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)

DUYURULAR_URL = "https://www.artvin.edu.tr/tr/duyurular"
MAX_DUYURU = 5


def scrape_announcements() -> str | None:
    """
    AÇÜ duyurular sayfasından son MAX_DUYURU kadar duyuruyu çeker.
    Hata durumunda None döner.
    """
    try:
        logger.info("Duyurular sayfası taranıyor...")
        r = requests.get(DUYURULAR_URL, timeout=10)
        if r.status_code != 200:
            logger.error(f"Duyurular sayfasına ulaşılamadı: {r.status_code}")
            return None

        soup = BeautifulSoup(r.content, "html.parser")

        # Tipik AÇÜ site yapısı: duyurular liste veya article elemanlarında
        items = []

        # Yöntem 1: ul/li yapısındaki duyurular
        news_list = soup.find("ul", class_=lambda c: c and "news" in c.lower())
        if news_list:
            for li in news_list.find_all("li")[:MAX_DUYURU]:
                a = li.find("a")
                if a:
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://www.artvin.edu.tr" + href
                    if title:
                        items.append((title, href))

        # Yöntem 2: article/div yapısı
        if not items:
            for article in soup.find_all(["article", "div"], class_=lambda c: c and any(
                k in c.lower() for k in ["duyuru", "news", "haber", "item", "post"]
            ))[:MAX_DUYURU]:
                a = article.find("a")
                if a:
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://www.artvin.edu.tr" + href
                    if title and len(title) > 5:
                        items.append((title, href))

        # Yöntem 3: Sayfa genelinde link listesi
        if not items:
            for a in soup.find_all("a", href=True)[:30]:
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if (
                    "duyuru" in href.lower() or "haber" in href.lower()
                ) and title and len(title) > 10:
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
        for i, (title, href) in enumerate(items[:MAX_DUYURU], 1):
            lines.append(f"{i}. {title}\n   {href}")

        lines.append(f"\n🔗 Tüm duyurular: {DUYURULAR_URL}")
        logger.info(f"{len(items)} duyuru çekildi.")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Duyurular scraper hatası: {e}", exc_info=True)
        return None
