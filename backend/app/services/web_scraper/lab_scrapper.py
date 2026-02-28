import logging
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

# Scraping başarılı sayılabilmesi için minimum beklenen cihaz sayısı
MIN_EXPECTED_DEVICES = 10


def scrape_lab_devices():
    url = 'https://www.artvin.edu.tr/laboratuvar-cihazlari'
    device_db = {}

    logger.info("Laboratuvar cihazları taranıyor (Selenium)...")

    browser = None
    try:
        opsiyonlar = Options()
        opsiyonlar.add_argument("--headless")
        opsiyonlar.add_argument("--no-sandbox")
        opsiyonlar.add_argument("--disable-dev-shm-usage")
        opsiyonlar.binary_location = "/usr/bin/firefox-esr"

        geckodriver_path = "/usr/local/bin/geckodriver"
        if not os.path.exists(geckodriver_path):
            geckodriver_path = "geckodriver"

        service = Service(geckodriver_path)
        browser = webdriver.Firefox(service=service, options=opsiyonlar)
        browser.get(url)

        # Tabloyu genişlet: absolute XPath yerine CSS/attribute-based selectors kullan
        try:
            wait = WebDriverWait(browser, 10)
            # DataTables "Göster" dropdown butonu — class tabanlı, DOM değişiminden etkilenmez
            show_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div.dataTables_length button, .dt-buttons button")
                )
            )
            show_btn.click()
            time.sleep(1)

            # "Tümünü Göster" seçeneği — text tabanlı arama
            all_option = browser.find_element(
                By.XPATH, "//ul[contains(@class,'dropdown-menu')]//a[contains(text(),'Tüm') or contains(text(),'All') or contains(text(),'-1')]"
            )
            all_option.click()
            logger.info("Tablo genişletiliyor...")
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Tablo genişletme uyarısı (devam ediliyor): {e}")

        # Veri çekme
        rows = browser.find_elements(By.XPATH, "//table[@id='datatable_ajax']/tbody/tr")
        logger.info(f"Toplam {len(rows)} satır bulundu.")

        for row in rows:
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 8:
                    cihaz_adi = cols[0].text.strip()
                    if not cihaz_adi:
                        continue

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
            except Exception as e:
                logger.warning(f"Satır parse hatası (atlanıyor): {e}")
                continue

        # Veri kalite kontrolü — minimum cihaz sayısını kontrol et
        if len(device_db) < MIN_EXPECTED_DEVICES:
            logger.warning(
                f"⚠️  Beklenen minimum cihaz sayısına ({MIN_EXPECTED_DEVICES}) ulaşılamadı. "
                f"Bulunan: {len(device_db)}. Eski veri korunacak."
            )
            return {}

        logger.info(f"✅ {len(device_db)} cihaz başarıyla tarandı.")
        return device_db

    except Exception as e:
        logger.error(f"Selenium Kritik Hata: {e}", exc_info=True)
        return {}

    finally:
        if browser:
            browser.quit()
