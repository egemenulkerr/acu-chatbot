import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
import re

logger = logging.getLogger(__name__)

def scrape_all_calendars():
    """
    AÇÜ ÖİDB sayfasını tarar ve BULDUĞU TÜM akademik takvimleri yıllara göre haritalar.
    """
    base_url = "https://www.artvin.edu.tr/akademik-takvim"
    calendar_map = {}
    
    try:
        logger.info(f"{base_url} adresinden takvim arşivi taranıyor...")
        response = requests.get(base_url, timeout=10, verify=False)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Tüm linkleri al
        links = soup.find_all("a", href=True)
        
        for link in links:
            text = link.get_text().strip()
            href = link.get("href")
            full_url = urljoin(base_url, href)
            
            # "Akademik Takvim" içeren linkleri filtrele
            if "akademik takvim" in text.lower():
                # Yıl formatını yakala (Örn: 2023-2024, 2021-2022)
                match = re.search(r'(\d{4})[\s\-\/]+(\d{4})', text)
                
                if match:
                    # Standardize edilmiş yıl anahtarı oluştur
                    year_key = f"{match.group(1)}-{match.group(2)}"
                    calendar_map[year_key] = full_url
                    logger.info(f"Takvim Bulundu: {year_key} -> {full_url}")

        # En güncel takvimi belirle
        if calendar_map:
            sorted_years = sorted(calendar_map.keys(), reverse=True)
            calendar_map["current"] = calendar_map[sorted_years[0]]
            
        return calendar_map

    except Exception as e:
        logger.error(f"Scraper Hatası: {e}")
        return {}