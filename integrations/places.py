"""Places connector backed by curated fallback destination data."""
from __future__ import annotations

from typing import Any

from app.models import Activity, Money, SearchResult
from app.utils import load_json


class PlacesClient:
    def __init__(self):
        self.destinations: list[dict[str, Any]] = load_json("destinations.json", []) or []

    def destinations_index(self) -> list[dict[str, Any]]:
        return self.destinations

    def find_destination(self, query: str | None) -> dict[str, Any] | None:
        if not query:
            return None
        needle = query.strip().lower()
        for destination in self.destinations:
            aliases = [destination.get("name", ""), *destination.get("aliases", [])]
            if any(needle == alias.lower() or needle in alias.lower() or alias.lower() in needle for alias in aliases):
                return destination
        return None

    def search_destinations(self, query: str, limit: int = 5) -> list[SearchResult]:
        needle = query.lower()
        results: list[SearchResult] = []
        for destination in self.destinations:
            aliases = " ".join([destination.get("name", ""), *destination.get("aliases", [])]).lower()
            score = 0.95 if needle in aliases else 0.45
            if needle in aliases or any(token in aliases for token in needle.split()):
                city_names = ", ".join(city["name"] for city in destination.get("cities", [])[:3])
                results.append(
                    SearchResult(
                        title=destination["name"],
                        category="destination",
                        summary=f"Known fallback destination with route support for {city_names}.",
                        source="static destinations.json",
                        score=score,
                        metadata={"country_code": destination.get("country_code"), "currency": destination.get("currency")},
                    )
                )
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

    def list_cities(self, destination_name: str) -> list[dict[str, Any]]:
        destination = self.find_destination(destination_name)
        return destination.get("cities", []) if destination else []

    def list_activities(
        self,
        destination_name: str,
        city: str | None = None,
        interests: list[str] | None = None,
    ) -> list[Activity]:
        destination = self.find_destination(destination_name)
        if not destination:
            return []
        interests_l = {interest.lower() for interest in (interests or [])}
        activities: list[Activity] = []
        for item in destination.get("activities", []):
            if city and item.get("city", "").lower() != city.lower():
                continue
            categories = [c.lower() for c in item.get("categories", [])]
            if interests_l and not interests_l.intersection(categories):
                # Keep some broad culture/nature defaults if exact interests are scarce.
                if not {"culture", "nature", "food"}.intersection(categories):
                    continue
            activities.append(
                Activity(
                    name=item["name"],
                    category=item.get("categories", ["sightseeing"])[0],
                    city=item.get("city"),
                    description=item.get("description", ""),
                    duration_hours=float(item.get("duration_hours", 1.5)),
                    opening_hours=item.get("opening_hours"),
                    estimated_cost=Money(amount=float(item.get("cost_inr", 0)), currency="INR", note="Static fallback estimate"),
                    rain_friendly=bool(item.get("rain_friendly", True)),
                    source="static destinations.json",
                )
            )
        return activities

    def rainy_day_alternatives(self, destination_name: str, city: str | None = None) -> list[Activity]:
        return [activity for activity in self.list_activities(destination_name, city=city) if activity.rain_friendly]
