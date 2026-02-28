import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def scrape_daily_menu():
    """
    AÇÜ Yemek sayfasından günün menüsünü çeker.

    Site tablosunda satırlar: (tarih_td, menü_td) çiftleri olarak sıralanır.
    Bugünün tarihini tabloda bulup o güne ait menüyü döndürür.

    Hafta sonu: 'KAPAL' sentinel döner.
    Scraping başarısız olursa None döner — uydurma veri ASLA döndürülmez.
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=Pazartesi, 5=Cumartesi, 6=Pazar

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
        today_str = now.strftime("%d.%m.%Y")
        response_parts = [f"**Günün Menüsü** ({today_str})"]

        # -- Tablo yaklaşımı: (tarih, menü) çiftleri --
        tds = soup.find_all("td")
        menu_text = None

        # Önce bugünün tarihini tabloda ara, sonraki hücreyi menü olarak al
        for i, td in enumerate(tds):
            cell_text = td.text.strip()
            if today_str in cell_text and i + 1 < len(tds):
                candidate = tds[i + 1].text.strip()
                if candidate and "hafta sonu" not in candidate.lower():
                    menu_text = candidate
                    logger.info(f"Tarih eşleşmesi bulundu (td[{i}]): {cell_text}")
                break

        # Tarihe göre bulunamadıysa, ilk çifti dene (sitenin ilk satırı genellikle bugün)
        if not menu_text and len(tds) > 1:
            candidate = tds[1].text.strip()
            # Hafta sonu sentinel
            if "hafta sonu" in candidate.lower() or candidate.upper() == "HAFTA SONU":
                return "KAPAL"
            if candidate:
                menu_text = candidate
                logger.info("Tarih eşleşmesi yok, tds[1] kullanıldı.")

        if menu_text:
            lines = [line.strip() for line in menu_text.split("\n") if line.strip()]
            if lines:
                response_parts.append("\n" + "\n".join(lines))

        # -- Menü resim URL'i --
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

        logger.warning("Yemek menüsü (resim ve metin) bulunamadı.")
        return None

    except Exception as e:
        logger.error(f"Yemek Scraper Hatası: {e}")
        return None
