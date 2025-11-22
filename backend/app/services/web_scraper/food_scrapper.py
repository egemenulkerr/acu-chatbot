import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def scrape_daily_menu():
    """
    AÇÜ Yemek sayfasından günün menüsünü çeker.
    """
    url = "https://www.artvin.edu.tr/tr/yemek"
    
    try:
        logger.info("Yemek listesi taranıyor...")
        
        # İstek at (Timeout ekledik ki sunucu takılmasın)
        r = requests.get(url, timeout=10)
        
        if r.status_code != 200:
            logger.error(f"Siteye ulaşılamadı. Kod: {r.status_code}")
            return None

        soup = BeautifulSoup(r.content, "html.parser")

        # Sizin mantığınız: 2. td etiketi (index 1) genelde o günün yemeğidir
        # Ancak bazen tablo boş olabilir, kontrol edelim.
        tds = soup.find_all("td")
        
        if len(tds) > 1:
            raw_text = tds[1].text.strip()
            
            # Metni satırlara böl ve temizle
            lines = raw_text.split("\n")
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            
            # Listeyi birleştir
            menu_text = "\n".join(cleaned_lines)
            
            logger.info("Yemek listesi başarıyla çekildi.")
            return menu_text
        else:
            logger.warning("Tablo yapısı değişmiş veya liste boş.")
            return None

    except Exception as e:
        logger.error(f"Yemek Scraper Hatası: {e}")
        return None