"""Unified search layer for travel and web-like data."""
from __future__ import annotations

from app.models import SearchResult
from integrations.places import PlacesClient
from app.utils import load_json


class SearchService:
    def __init__(self, places: PlacesClient | None = None):
        self.places = places or PlacesClient()
        self.sample = load_json("sample_data.json", {}) or {}

    def search(self, query: str, category: str | None = None, destination: str | None = None, limit: int = 10) -> list[SearchResult]:
        query_l = query.lower()
        results: list[SearchResult] = []
        if category in {None, "destination", "all"}:
            results.extend(self.places.search_destinations(query, limit=limit))

        if category in {None, "activity", "activities", "all"}:
            destinations = [destination] if destination else [d["name"] for d in self.places.destinations_index()]
            for dest in destinations:
                for activity in self.places.list_activities(dest):
                    haystack = f"{activity.name} {activity.description} {activity.category} {activity.city}".lower()
                    if query_l in haystack or any(token in haystack for token in query_l.split()):
                        results.append(
                            SearchResult(
                                title=activity.name,
                                category="activity",
                                summary=activity.description,
                                source=activity.source,
                                score=0.82,
                                metadata={"city": activity.city, "cost": activity.estimated_cost.model_dump(mode="json")},
                            )
                        )

        if category in {None, "hotel", "hotels", "all"}:
            for hotel in self.sample.get("hotels", []):
                if destination and hotel.get("destination", "").lower() != destination.lower():
                    continue
                haystack = " ".join(str(v) for v in hotel.values()).lower()
                if query_l in haystack or any(token in haystack for token in query_l.split()):
                    results.append(
                        SearchResult(
                            title=hotel["name"],
                            category="hotel",
                            summary=f"{hotel.get('type', 'hotel')} in {hotel.get('city')}; estimated ₹{hotel.get('price_inr')}/night.",
                            source="static sample_data.json",
                            score=0.72,
                            metadata=hotel,
                        )
                    )
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]
