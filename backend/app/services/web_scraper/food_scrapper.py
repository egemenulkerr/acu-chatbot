import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def scrape_daily_menu():
    """
    AÇÜ Yemek sayfasından günün menüsünü çeker.
    Website structure değişti: Artık menü resim olarak gösteriliyor.
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

        # Yeni yapı: Menü image-container içinde resim olarak saklanıyor
        # Örnek: <img src="/storage/yemekMenuResimleri/menu.jpg?v=1764370132" alt="menu" />
        image_container = soup.find("div", class_="image-container")
        
        if image_container:
            img = image_container.find("img")
            if img and img.get("src"):
                menu_image_url = img.get("src")
                
                # Eğer relative URL ise absolute URL yap
                if menu_image_url.startswith("/"):
                    menu_image_url = "https://www.artvin.edu.tr" + menu_image_url
                
                # Menü resmi URL'ini döndür (bot bu URL'i gösterebilir)
                today = datetime.now().strftime("%d.%m.%Y")
                response_text = f"""**Günün Menüsü** ({today})

Menü resmi: {menu_image_url}

*Not: Yemek menüsü artık resim formatında gösterilmektedir. 
Detaylı bilgi için lütfen: https://www.artvin.edu.tr/tr/yemek adresini ziyaret edin."""
                
                logger.info("Yemek menüsü resmi URL'i başarıyla elde edildi.")
                return response_text
        
        # Fallback: Eski yapı (tablo) hala varsa bunu dene
        tds = soup.find_all("td")
        if len(tds) > 1:
            raw_text = tds[1].text.strip()
            
            # Metni satırlara böl ve temizle
            lines = raw_text.split("\n")
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            
            # Listeyi birleştir
            menu_text = "\n".join(cleaned_lines)
            
            logger.info("Yemek listesi (tablo verisi) başarıyla çekildi.")
            return menu_text
        
        # Her iki yöntem de başarısız
        logger.warning("Yemek menüsü bulunamadı - website yapısı tamamen değişmiş olabilir.")
        return None

    except Exception as e:
        logger.error(f"Yemek Scraper Hatası: {e}")
        return None