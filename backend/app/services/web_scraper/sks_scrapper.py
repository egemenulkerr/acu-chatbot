# ============================================================================
# backend/app/services/web_scraper/sks_scrapper.py - SKS Scraper
# Öğrenci Kültür ve Spor Dairesi Başkanlığı
# ============================================================================

import logging
import requests
from bs4 import BeautifulSoup
from typing import Optional
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

SKS_BASE_URL = "https://www.artvin.edu.tr"
SKS_ETKINLIK_URL = f"{SKS_BASE_URL}/tr/sks"
SKS_KULUP_URL = f"{SKS_BASE_URL}/tr/ogrenci-topluluk"

HEADERS = {
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
def _fetch_page(url: str, timeout: int = 10):
    r = requests.get(url, timeout=timeout, headers=HEADERS)
    r.raise_for_status()
    return r


def scrape_sks_events() -> Optional[dict]:
    """
    SKS sayfasından öğrenci etkinliklerini ve topluluk bilgilerini çeker.
    Döner: {events: [...], clubs: [...], scraped_at: "..."}
    """
    result: dict = {
        "events": [],
        "clubs": [],
        "sports_facilities": [],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "sks_url": SKS_ETKINLIK_URL,
        "kulup_url": SKS_KULUP_URL,
    }

    # -- Etkinlikler --
    try:
        logger.info(f"SKS etkinlik sayfası taranıyor: {SKS_ETKINLIK_URL}")
        r = _fetch_page(SKS_ETKINLIK_URL)
        if r is not None:
            soup = BeautifulSoup(r.content, "html.parser")
            events = _parse_event_links(soup, SKS_BASE_URL)
            result["events"] = events
            logger.info(f"SKS: {len(events)} etkinlik bulundu.")
        else:
            logger.warning("SKS etkinlik sayfası alınamadı.")
    except Exception as e:
        logger.error(f"SKS etkinlik scrape hatası: {e}", exc_info=True)

    # -- Öğrenci toplulukları --
    try:
        logger.info(f"SKS kulüp sayfası taranıyor: {SKS_KULUP_URL}")
        r = _fetch_page(SKS_KULUP_URL)
        if r is not None:
            soup = BeautifulSoup(r.content, "html.parser")
            clubs = _parse_clubs(soup, SKS_BASE_URL)
            result["clubs"] = clubs
            logger.info(f"SKS: {len(clubs)} kulüp bulundu.")
        else:
            logger.warning("SKS kulüp sayfası alınamadı.")
    except Exception as e:
        logger.error(f"SKS kulüp scrape hatası: {e}", exc_info=True)

    if not result["events"] and not result["clubs"]:
        return None

    return result


def _parse_event_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Sayfa içindeki etkinlik linklerini çıkar."""
    events = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not title or len(title) < 8:
            continue
        if any(kw in href.lower() for kw in ["etkinlik", "faaliyet", "haber", "duyuru"]):
            if not href.startswith("http"):
                href = base_url.rstrip("/") + "/" + href.lstrip("/")
            if not any(e["url"] == href for e in events):
                events.append({"title": title, "url": href})
            if len(events) >= 7:
                break
    return events


def _parse_clubs(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Sayfa içindeki öğrenci kulübü / topluluk listesini çıkar."""
    clubs = []
    for tag in soup.find_all(["li", "div", "p", "td"]):
        text = tag.get_text(strip=True)
        if len(text) < 5 or len(text) > 120:
            continue
        if any(kw in text.lower() for kw in ["kulübü", "topluluğu", "derneği", "birliği"]):
            a = tag.find("a")
            url = ""
            if a and a.get("href"):
                url = a["href"]
                if not url.startswith("http"):
                    url = base_url.rstrip("/") + "/" + url.lstrip("/")
            if not any(c["name"] == text for c in clubs):
                clubs.append({"name": text, "url": url})
            if len(clubs) >= 20:
                break
    return clubs


def format_sks_response(info: Optional[dict]) -> str:
    """SKS bilgisini kullanıcı-dostu metne çevirir."""
    if not info:
        return (
            "🎭 Şu an SKS etkinlik bilgisi alınamıyor. "
            f"Lütfen SKS sayfasını ziyaret edin: {SKS_ETKINLIK_URL}"
        )

    lines = ["🎭 **Öğrenci Kültür ve Spor (SKS)**\n"]

    if info.get("events"):
        lines.append("📅 **Güncel Etkinlikler:**")
        for ev in info["events"][:5]:
            lines.append(f"• {ev['title']}\n  {ev['url']}")

    if info.get("clubs"):
        lines.append(f"\n🏫 **Öğrenci Toplulukları** ({len(info['clubs'])} topluluk):")
        for club in info["clubs"][:8]:
            if club.get("url"):
                lines.append(f"• {club['name']} — {club['url']}")
            else:
                lines.append(f"• {club['name']}")

    lines.append(f"\n🔗 SKS: {info['sks_url']}")

    return "\n".join(lines)
