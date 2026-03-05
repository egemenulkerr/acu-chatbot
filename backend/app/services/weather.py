# ============================================================================
# backend/app/services/weather.py - Hava Durumu Servisi
# ============================================================================
# OpenWeatherMap API kullanarak Artvin hava durumunu çeker.
# OPENWEATHER_API_KEY env var gerektirir (ücretsiz plan yeterli).
# ============================================================================

import logging
import requests
from typing import Optional
from ..config import settings


logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY: Optional[str] = settings.openweather_api_key or ""

CITY_ID = "321895"        # Artvin, TR (OpenWeatherMap city ID)
CITY_NAME = "Artvin,TR"
API_URL = "https://api.openweathermap.org/data/2.5/weather"

WEATHER_ICONS = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "🌦️",
    "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️", "Fog": "🌫️",
    "Haze": "🌫️", "Smoke": "🌫️", "Dust": "🌪️", "Sand": "🌪️",
    "Ash": "🌋", "Squall": "🌬️", "Tornado": "🌪️",
}

WEATHER_TR = {
    "clear sky": "açık", "few clouds": "az bulutlu", "scattered clouds": "parçalı bulutlu",
    "broken clouds": "çok bulutlu", "overcast clouds": "kapalı", "light rain": "hafif yağmurlu",
    "moderate rain": "orta yağmurlu", "heavy intensity rain": "yoğun yağmurlu",
    "light snow": "hafif karlı", "moderate snow": "orta karlı", "heavy snow": "yoğun karlı",
    "mist": "sisli", "fog": "yoğun sisli", "thunderstorm": "fırtınalı",
}


def get_weather() -> str:
    """
    Artvin hava durumunu OpenWeatherMap'ten çek ve Türkçe formatla.
    API key yoksa veya hata olursa açıklayıcı mesaj döndür.
    """
    if not OPENWEATHER_API_KEY:
        return (
            "🌤️ Hava durumu servisi şu an aktif değil.\n"
            "Artvin hava durumu için: https://www.mgm.gov.tr"
        )

    try:
        resp = requests.get(
            API_URL,
            params={
                "q": CITY_NAME,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric",
                "lang": "tr",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        main = data["main"]
        weather = data["weather"][0]
        wind = data.get("wind", {})
        clouds = data.get("clouds", {})

        condition_en = weather.get("description", "").lower()
        condition_tr = WEATHER_TR.get(condition_en, weather.get("description", ""))
        icon = WEATHER_ICONS.get(weather.get("main", ""), "🌡️")

        temp = round(main["temp"])
        feels_like = round(main["feels_like"])
        humidity = main["humidity"]
        wind_speed = round(wind.get("speed", 0) * 3.6)  # m/s → km/h
        cloud_pct = clouds.get("all", 0)

        return (
            f"{icon} **Artvin Hava Durumu**\n\n"
            f"🌡️ Sıcaklık: **{temp}°C** (Hissedilen: {feels_like}°C)\n"
            f"🌤️ Durum: {condition_tr.capitalize()}\n"
            f"💧 Nem: %{humidity}\n"
            f"💨 Rüzgar: {wind_speed} km/s\n"
            f"☁️ Bulutluluk: %{cloud_pct}\n\n"
            f"📊 Detaylı tahmin: https://www.mgm.gov.tr"
        )

    except requests.exceptions.Timeout:
        logger.warning("Hava durumu API zaman aşımı.")
        return "⏱️ Hava durumu bilgisi alınamadı. Lütfen daha sonra tekrar deneyin."
    except Exception as e:
        logger.error(f"Hava durumu hatası: {e}", exc_info=True)
        return (
            "🌤️ Hava durumu bilgisi alınamadı.\n"
            "Artvin için: https://www.mgm.gov.tr"
        )
