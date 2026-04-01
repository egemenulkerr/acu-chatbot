# ============================================================================
# backend/app/services/web_scraper/library_site_scraper.py - Kütüphane Scraper
# ============================================================================

import logging
from typing import Optional

from bs4 import BeautifulSoup

from .http_utils import fetch_with_retry

logger = logging.getLogger(__name__)

LIBRARY_BASE_URL = "https://kutuphane.artvin.edu.tr"


def scrape_library_info() -> Optional[dict]:
    """
    AÇÜ Kütüphane sitesinden temel bilgileri çeker:
    - Çalışma saatleri
    - Katalog linki
    - Güncel duyurular/haberler

    Başarısız olursa None döner.
    """
    result: dict = {
        "catalog_url": f"{LIBRARY_BASE_URL}/yordam",
        "base_url": LIBRARY_BASE_URL,
        "hours": None,
        "announcements": [],
        "contact": None,
    }

    try:
        logger.info(f"Kütüphane sitesi taranıyor: {LIBRARY_BASE_URL}")
        r = fetch_with_retry(LIBRARY_BASE_URL, timeout=10)
        if r is None:
            logger.error("Kütüphane sitesi 3 denemede de alınamadı.")
            return None

        soup = BeautifulSoup(r.content, "html.parser")

        # -- Çalışma saatleri: metin içinde "saat" veya "çalışma" geçen blokları ara --
        hours_text: Optional[str] = None
        for tag in soup.find_all(["p", "div", "span", "li"]):
            text = tag.get_text(strip=True)
            if any(kw in text.lower() for kw in ["çalışma saati", "mesai", "açık", "kapalı"]):
                if len(text) < 200:
                    hours_text = text
                    break

        if hours_text:
            result["hours"] = hours_text
            logger.info(f"Çalışma saatleri bulundu: {hours_text[:60]}")

        # -- Duyurular: haber/duyuru linkleri --
        announcements = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if not title or len(title) < 8:
                continue
            if any(kw in href.lower() for kw in ["haber", "duyuru", "etkinlik", "news"]):
                if not href.startswith("http"):
                    href = LIBRARY_BASE_URL.rstrip("/") + "/" + href.lstrip("/")
                announcements.append({"title": title, "url": href})
                if len(announcements) >= 5:
                    break

        result["announcements"] = announcements

        # -- İletişim: telefon numarası --
        for tag in soup.find_all(["p", "div", "span", "li"]):
            text = tag.get_text(strip=True)
            if any(kw in text.lower() for kw in ["tel:", "telefon", "0466", "0 466"]):
                if len(text) < 100:
                    result["contact"] = text
                    break

        logger.info(
            f"Kütüphane scrape tamamlandı: "
            f"hours={'var' if result['hours'] else 'yok'}, "
            f"duyurular={len(announcements)}"
        )
        return result

    except Exception as e:
        logger.error(f"Kütüphane scraper hatası: {e}", exc_info=True)
        return None


def format_library_response(info: Optional[dict]) -> str:
    """Kütüphane bilgisini kullanıcı-dostu metne çevirir."""
    if not info:
        return (
            "📚 Şu an kütüphane bilgisi alınamıyor. "
            f"Lütfen kütüphane sitesini ziyaret edin: {LIBRARY_BASE_URL}"
        )

    lines = ["📚 **AÇÜ Kütüphanesi**\n"]

    if info.get("hours"):
        lines.append(f"🕐 **Çalışma Saatleri:** {info['hours']}\n")

    if info.get("catalog_url"):
        lines.append(f"🔍 **Online Katalog:** {info['catalog_url']}")

    if info.get("contact"):
        lines.append(f"📞 **İletişim:** {info['contact']}")

    if info.get("announcements"):
        lines.append("\n📢 **Son Duyurular:**")
        for item in info["announcements"][:3]:
            lines.append(f"• {item['title']}\n  {item['url']}")

    lines.append(f"\n🌐 Web: {info['base_url']}")

    return "\n".join(lines)
