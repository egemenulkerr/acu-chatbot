# ============================================================================
# backend/app/services/web_scraper/main_site_scrapper.py - Ana Site Scraper
# ============================================================================

import logging
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from .http_utils import fetch_with_retry

logger = logging.getLogger(__name__)

MAIN_SITE_URL = "https://www.artvin.edu.tr"
MAX_NEWS = 8


def scrape_main_site_news() -> Optional[list[dict]]:
    """
    artvin.edu.tr ana sayfasından güncel haber başlıklarını çeker.
    Döner: [{"title": str, "url": str}, ...] | None
    """
    try:
        logger.info(f"Ana site haberleri taranıyor: {MAIN_SITE_URL}")
        r = fetch_with_retry(MAIN_SITE_URL)
        if r is None:
            logger.error("Ana site 3 denemede de alınamadı.")
            return None

        soup = BeautifulSoup(r.content, "html.parser")
        news: list[dict] = []
        seen_titles: set[str] = set()

        # Öncelikli: haber/duyuru href'li anchor'lar
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            title = a.get_text(strip=True)

            if not title or len(title) < 10 or len(title) > 200:
                continue
            if title in seen_titles:
                continue
            if not any(kw in href.lower() for kw in ["haber", "duyuru", "etkinlik", "tr/"]):
                continue

            if not href.startswith("http"):
                href = MAIN_SITE_URL.rstrip("/") + "/" + href.lstrip("/")

            # Navigasyon linklerini filtrele
            nav_words = ["anasayfa", "iletişim", "hakkımızda", "künye", "site haritası"]
            if any(w in title.lower() for w in nav_words):
                continue

            news.append({"title": title, "url": href})
            seen_titles.add(title)

            if len(news) >= MAX_NEWS:
                break

        if not news:
            logger.warning("Ana siteden haber bulunamadı.")
            return None

        logger.info(f"{len(news)} haber çekildi.")
        return news

    except Exception as e:
        logger.error(f"Ana site scraper hatası: {e}", exc_info=True)
        return None


def format_main_news_response(news: Optional[list[dict]]) -> str:
    """Haber listesini kullanıcı-dostu formata çevirir."""
    if not news:
        return (
            "📰 Şu an güncel haber bilgisi alınamıyor. "
            f"Lütfen üniversite web sitesini ziyaret edin: {MAIN_SITE_URL}"
        )

    today = datetime.now().strftime("%d.%m.%Y")
    lines = [f"📰 **Güncel Haberler** ({today})\n"]

    for i, item in enumerate(news, 1):
        lines.append(f"{i}. {item['title']}\n   {item['url']}")

    lines.append(f"\n🔗 Tüm haberler: {MAIN_SITE_URL}")
    return "\n".join(lines)
