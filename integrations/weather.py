"""Weather connector with clean fallback behaviour."""
from __future__ import annotations

from datetime import date

from app.models import WeatherInfo


class WeatherClient:
    """Return live weather when configured in the future, otherwise seasonal estimates."""

    def forecast(self, destination: str, target_date: date | None = None) -> WeatherInfo:
        month = target_date.month if target_date else None
        lower = destination.lower()
        summary = "Seasonal weather estimate unavailable; check a live forecast before departure."
        min_c, max_c, rain = None, None, None

        if "japan" in lower or any(city in lower for city in ["tokyo", "kyoto", "osaka", "nara", "hakone"]):
            if month in {6, 7}:
                summary, min_c, max_c, rain = "Warm and humid; rainy-season showers are common.", 22, 30, 0.55
            elif month in {12, 1, 2}:
                summary, min_c, max_c, rain = "Cool to cold; pack layers, especially for mornings and evenings.", 2, 12, 0.20
            elif month in {3, 4, 5, 10, 11}:
                summary, min_c, max_c, rain = "Generally pleasant shoulder-season conditions with occasional rain.", 10, 22, 0.30
            else:
                summary, min_c, max_c, rain = "Warm conditions; keep flexible indoor alternatives for wet days.", 20, 32, 0.40
        elif "thailand" in lower or any(city in lower for city in ["bangkok", "krabi", "chiang mai"]):
            if month in {5, 6, 7, 8, 9, 10}:
                summary, min_c, max_c, rain = "Hot and humid with frequent showers; plan morning outdoor time.", 25, 33, 0.65
            else:
                summary, min_c, max_c, rain = "Warm tropical weather; sun protection and hydration matter.", 23, 32, 0.30
        elif "france" in lower or "paris" in lower:
            if month in {12, 1, 2}:
                summary, min_c, max_c, rain = "Cool winter weather; indoor museum/cafe buffers are useful.", 2, 9, 0.35
            else:
                summary, min_c, max_c, rain = "Mild European city weather; carry a light rain layer.", 8, 24, 0.30
        elif "india" in lower or any(city in lower for city in ["delhi", "jaipur", "goa"]):
            if month in {6, 7, 8, 9}:
                summary, min_c, max_c, rain = "Monsoon risk in many regions; build road and rain buffers.", 24, 34, 0.60
            else:
                summary, min_c, max_c, rain = "Generally workable travel weather, varying strongly by region.", 12, 32, 0.25
        elif "dubai" in lower or "emirates" in lower or "abu dhabi" in lower:
            if month in {6, 7, 8, 9}:
                summary, min_c, max_c, rain = "Very hot; schedule outdoor activities at sunrise or after sunset.", 30, 42, 0.05
            else:
                summary, min_c, max_c, rain = "Warm and usually dry; evenings are pleasant in winter months.", 18, 30, 0.10

        return WeatherInfo(
            destination=destination,
            date=target_date,
            summary=summary,
            temperature_c_min=min_c,
            temperature_c_max=max_c,
            rain_probability=rain,
            source="seasonal climate fallback estimate; not a live forecast",
            is_live=False,
        )
