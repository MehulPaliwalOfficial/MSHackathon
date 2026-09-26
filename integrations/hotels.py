"""Hotel connector with static fallback development data."""
from __future__ import annotations

from app.models import Accommodation, Money
from app.utils import load_json


class HotelsClient:
    def __init__(self):
        self.sample_data = load_json("sample_data.json", {}) or {}
        self.destinations = load_json("destinations.json", []) or []

    def search(
        self,
        destination: str,
        cities: list[str],
        style: str = "balanced",
        nights: int = 1,
        rooms: int = 1,
        limit: int = 5,
    ) -> list[Accommodation]:
        style = style or "balanced"
        hotels = []
        for item in self.sample_data.get("hotels", []):
            if item.get("destination", "").lower() != destination.lower():
                continue
            if cities and item.get("city") not in cities:
                continue
            # Prefer matching style but still allow nearby options.
            if item.get("style") != style and len(hotels) >= 2:
                continue
            per_night = float(item.get("price_inr", 0)) * rooms
            hotels.append(
                Accommodation(
                    name=item["name"],
                    city=item["city"],
                    type=item.get("type", "hotel"),
                    rating=item.get("rating"),
                    price_per_night=Money(amount=per_night, currency="INR", note="Fallback per-night estimate"),
                    total_estimated=Money(amount=per_night * max(nights, 1), currency="INR", note="Fallback stay estimate"),
                    amenities=item.get("amenities", []),
                    location_notes=item.get("location_notes"),
                    source="static sample_data.json estimate; verify live availability before booking",
                    availability_live=False,
                )
            )
        if not hotels:
            profile = next((d for d in self.destinations if d.get("name", "").lower() == destination.lower()), None)
            daily = (profile or {}).get("daily_budget_inr", {}).get(style, 6000)
            for city in cities[:limit] or [destination]:
                per_night = float(daily) * 0.55 * rooms
                hotels.append(
                    Accommodation(
                        name=f"{city} {style.title()} Stay Estimate",
                        city=city,
                        type="development estimate",
                        rating=None,
                        price_per_night=Money(amount=round(per_night), currency="INR", note="Generated fallback estimate"),
                        total_estimated=Money(amount=round(per_night * max(nights, 1)), currency="INR", note="Generated fallback estimate"),
                        amenities=["verify live amenities", "not a real listing"],
                        location_notes="Placeholder estimate only; connect a hotel provider for live inventory.",
                        source="generated fallback estimate; not a real hotel or availability",
                        availability_live=False,
                    )
                )
        return hotels[:limit]
