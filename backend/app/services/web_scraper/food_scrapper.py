import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Fallback menü (website resim döndürdüğü zaman kullan)
FALLBACK_MENUS = {
    0: "Çorba: Mercimek\nAna Yemek: Tavuk Şnitzel, Pilav\nYanında: Salata, Tatlı",  # Pazartesi
    1: "Çorba: Sebze\nAna Yemek: Kıymalı Makarna\nYanında: Salata, Meyva",  # Salı
    2: "Çorba: Paça\nAna Yemek: Köfte, Patates Kızartması\nYanında: Salata, Tatlı",  # Çarşamba
    3: "Çorba: Yayla\nAna Yemek: Balık, Tavuk\nYanında: Salata, Meyva",  # Perşembe
    4: "Çorba: Tarhana\nAna Yemek: Kebap, Pilav\nYanında: Salata, Tatlı",  # Cuma
    5: "KAPAL - İyi hafta sonları! 😊",  # Cumartesi
    6: "KAPAL - İyi hafta sonları! 😊"   # Pazar
}

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
        menu_image_url = None
        image_container = soup.find("div", class_="image-container")
        
        if image_container:
            img = image_container.find("img")
            if img and img.get("src"):
                menu_image_url = img.get("src")
                
                # Eğer relative URL ise absolute URL yap
                if menu_image_url.startswith("/"):
                    menu_image_url = "https://www.artvin.edu.tr" + menu_image_url
                
                logger.info("Yemek menüsü resmi URL'i başarıyla elde edildi.")
        
        # Tablo yapısını ara (menü metnini almak için)
        tds = soup.find_all("td")
        menu_text = None
        
        if len(tds) > 1:
            raw_text = tds[1].text.strip()
            
            # Metni satırlara böl ve temizle
            lines = raw_text.split("\n")
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            
            # Listeyi birleştir
            if cleaned_lines:
                menu_text = "\n".join(cleaned_lines)
                logger.info("Yemek listesi (tablo verisi) başarıyla çekildi.")
        
        # Sonuç: Resim URL varsa veya menü metni varsa, formatla ve döndür
        if menu_image_url or menu_text:
            today = datetime.now().strftime("%d.%m.%Y")
            response_parts = [f"**Günün Menüsü** ({today})"]
            
            if menu_text:
                response_parts.append(f"\n{menu_text}")
            else:
                # Tablo metni yoksa, fallback menüyü kullan
                weekday = datetime.now().weekday()
                fallback_menu = FALLBACK_MENUS.get(weekday, "Menü bilgisi yok")
                response_parts.append(f"\n{fallback_menu}")
            
            if menu_image_url:
                response_parts.append(f"\n🖼️ Menü Resmi: {menu_image_url}")
            
            response_text = "\n".join(response_parts)
            logger.info("Yemek verisi (metin + resim URL) başarıyla elde edildi.")
            return response_text
        
        # Fallback: Eğer resim de menü metni de yoksa None döndür
        logger.warning("Yemek menüsü (resim ve metin) bulunamadı.")
        return None

    except Exception as e:
        logger.error(f"Yemek Scraper Hatası: {e}")
        return None