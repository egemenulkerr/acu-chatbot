import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
import re

logger = logging.getLogger(__name__)

BASE_URL = "https://www.artvin.edu.tr/akademik-takvim"

# Anahtar dönem ifadeleri — HTML tablosundan parse edilecek
_KEY_TERMS = [
    ("Güz Dönemi Başlangıç", ["güz dönemi başlangıç", "güz yarıyılı başlangıç", "öğretim yılı başlangıç"]),
    ("Bahar Dönemi Başlangıç", ["bahar dönemi başlangıç", "bahar yarıyılı başlangıç"]),
    ("Ara Tatil", ["ara tatil", "sömestr tatil", "yarıyıl tatil"]),
    ("Vize Sınavları", ["vize sınav", "ara sınav", "midterm"]),
    ("Final Sınavları", ["final sınav", "yarıyıl sonu sınav"]),
    ("Bütünleme Sınavları", ["bütünleme", "mazeret sınav"]),
    ("Kayıt Yenileme", ["kayıt yenileme", "ders kaydı"]),
    ("Yaz Tatili", ["yaz tatil", "öğretim yılı sonu"]),
]


def _parse_key_dates_from_html(soup: BeautifulSoup) -> dict[str, str]:
    """
    Akademik takvim sayfasındaki HTML tablosundan önemli tarihleri çıkar.
    Döner: {"Güz Dönemi Başlangıç": "16 Eylül 2024", ...}
    """
    key_dates: dict[str, str] = {}
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            cell_text = cells[0].get_text(strip=True).lower()
            date_text = cells[-1].get_text(strip=True)

            for label, keywords in _KEY_TERMS:
                if label in key_dates:
                    continue
                if any(kw in cell_text for kw in keywords):
                    key_dates[label] = date_text
                    break

    return key_dates


def scrape_all_calendars() -> dict:
    """
    AÇÜ akademik takvim sayfasını tarar:
    1. Yıl bazlı PDF linklerini toplar
    2. Güncel sayfadaki HTML tablosundan önemli tarihleri parse eder
    """
    calendar_map: dict = {}

    try:
        logger.info(f"Takvim arşivi taranıyor: {BASE_URL}")
        response = requests.get(BASE_URL, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # -- PDF linkleri --
        for link in soup.find_all("a", href=True):
            text = link.get_text().strip()
            href = link.get("href", "")
            full_url = urljoin(BASE_URL, href)

            if "akademik takvim" in text.lower():
                match = re.search(r'(\d{4})[\s\-\/]+(\d{4})', text)
                if match:
                    year_key = f"{match.group(1)}-{match.group(2)}"
                    calendar_map[year_key] = full_url
                    logger.info(f"Takvim bulundu: {year_key}")

        if calendar_map:
            sorted_years = sorted(calendar_map.keys(), reverse=True)
            calendar_map["current"] = calendar_map[sorted_years[0]]

        # -- Önemli tarihler (HTML tablodan) --
        key_dates = _parse_key_dates_from_html(soup)
        if key_dates:
            calendar_map["key_dates"] = key_dates
            logger.info(f"✅ {len(key_dates)} önemli tarih parse edildi: {list(key_dates.keys())}")
        else:
            logger.info("HTML tablosunda tarih bulunamadı (PDF'e yönlendirilecek).")

        return calendar_map

    except Exception as e:
        logger.error(f"Takvim scraper hatası: {e}", exc_info=True)
        return {}