import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def scrape_daily_menu():
    """
    AÇÜ Yemek sayfasından günün menüsünü çeker.

    Hafta sonu kontrol edilir ve 'KAPAL' sentinel döndürülür.
    Scraping başarısız olursa None döner — uydurma veri ASLA döndürülmez.
    """
    # Hafta sonu kontrolü (0=Pazartesi, 5=Cumartesi, 6=Pazar)
    weekday = datetime.now().weekday()
    if weekday >= 5:
        return "KAPAL"

    url = "https://www.artvin.edu.tr/tr/yemek"

    try:
        logger.info("Yemek listesi taranıyor...")
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            logger.error(f"Siteye ulaşılamadı. Kod: {r.status_code}")
            return None

        soup = BeautifulSoup(r.content, "html.parser")
        today = datetime.now().strftime("%d.%m.%Y")
        response_parts = [f"**Günün Menüsü** ({today})"]

        # Menü tablo metni
        tds = soup.find_all("td")
        if len(tds) > 1:
            raw_text = tds[1].text.strip()
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
            if lines:
                response_parts.append("\n" + "\n".join(lines))
                logger.info("Yemek listesi (tablo verisi) başarıyla çekildi.")

        # Menü resim URL'i
        image_container = soup.find("div", class_="image-container")
        if image_container:
            img = image_container.find("img")
            if img and img.get("src"):
                src = img.get("src")
                if src.startswith("/"):
                    src = "https://www.artvin.edu.tr" + src
                response_parts.append(f"\n🖼️ Menü Resmi: {src}")
                logger.info("Yemek menüsü resmi URL'i elde edildi.")

        if len(response_parts) > 1:
            return "\n".join(response_parts)

        # Ne tablo metni ne resim bulundu — dürüstçe None döndür
        logger.warning("Yemek menüsü (resim ve metin) bulunamadı.")
        return None

    except Exception as e:
        logger.error(f"Yemek Scraper Hatası: {e}")
        return None
