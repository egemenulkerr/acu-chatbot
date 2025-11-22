import logging
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager # <-- YENİ KAHRAMANIMIZ

logger = logging.getLogger(__name__)

def scrape_lab_devices():
    url = 'https://www.artvin.edu.tr/laboratuvar-cihazlari'
    device_db = {}

    logger.info("Laboratuvar cihazları taranıyor (Selenium)...")

    browser = None
    try:
        # 1. Tarayıcı Ayarları
        opsiyonlar = Options()
        opsiyonlar.add_argument("--headless") 
        opsiyonlar.add_argument("--no-sandbox")
        opsiyonlar.add_argument("--disable-dev-shm-usage")
        
        # Docker içinde Firefox ESR'nin standart yolu
        opsiyonlar.binary_location = "/usr/bin/firefox-esr"

        # 2. Sürücüyü OTOMATİK Kur ve Başlat
        # Bu satır, işletim sistemine uygun driver'ı bulur, indirir ve yolu ayarlar.
        service = Service(GeckoDriverManager().install())
        
        browser = webdriver.Firefox(service=service, options=opsiyonlar)
        browser.get(url)

        # 3. Tabloyu Genişletme
        try:
            click_button = browser.find_element(By.XPATH, "/html/body/div[1]/section/div/div/div/div[2]/div[3]/div/span/div/button")
            click_button.click()
            time.sleep(1)
            click_button1 = browser.find_element(By.XPATH, "/html/body/div[1]/section/div/div/div/div[2]/div[3]/div/span/div/div/ul/li[4]/a")
            click_button1.click()
            logger.info("Tablo genişletiliyor...")
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Tablo genişletme uyarısı: {e}")

        # 4. Veriyi Çekme
        rows = browser.find_elements(By.XPATH, "//table[@id='datatable_ajax']/tbody/tr")
        logger.info(f"Toplam {len(rows)} cihaz bulundu.")

        for i in range(len(rows)):
            try:
                cols = rows[i].find_elements(By.TAG_NAME, "td")
                if len(cols) >= 8:
                    cihaz_adi = cols[0].text.strip()
                    # Diğer sütunlar...
                    birimi = cols[1].text.strip()
                    lab = cols[2].text.strip()
                    adet = cols[3].text.strip()
                    marka = cols[4].text.strip()
                    sorumlu = cols[7].text.strip()

                    device_key = cihaz_adi.lower()
                    
                    device_db[device_key] = {
                        "original_name": cihaz_adi,
                        "description": f"Birim: {birimi}, Lab: {lab}, Marka: {marka}, Sorumlu: {sorumlu}",
                        "price": "Fiyat bilgisi yok",
                        "stock": f"Adet: {adet}"
                    }
            except:
                continue

        return device_db

    except Exception as e:
        logger.error(f"Selenium Kritik Hata: {e}")
        return {}
        
    finally:
        if browser:
            browser.quit()