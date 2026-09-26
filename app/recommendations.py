"""Personalized destination, hotel, activity, food and transport recommendations."""
from __future__ import annotations

from app.models import Accommodation, Activity, MealSuggestion, Money, RecommendationSet, SearchResult, TripRequest
from app.utils import load_json
from integrations.hotels import HotelsClient
from integrations.places import PlacesClient


class RecommendationEngine:
    def __init__(self, places: PlacesClient | None = None, hotels: HotelsClient | None = None):
        self.places = places or PlacesClient()
        self.hotels = hotels or HotelsClient()
        self.sample = load_json("sample_data.json", {}) or {}

    def recommend_destinations(self, request: TripRequest, limit: int = 5) -> list[SearchResult]:
        if request.destination:
            return self.places.search_destinations(request.destination, limit=limit)
        interests = set(request.preferences.interests)
        results: list[SearchResult] = []
        for destination in self.places.destinations_index():
            activity_categories = {
                category
                for activity in destination.get("activities", [])
                for category in activity.get("categories", [])
            }
            overlap = len(interests.intersection(activity_categories))
            score = min(0.95, 0.45 + overlap * 0.15)
            if overlap or not interests:
                results.append(
                    SearchResult(
                        title=destination["name"],
                        category="destination",
                        summary=f"Matches {overlap} stated interests; best months include {', '.join(destination.get('best_months', [])[:3])}.",
                        source="static destinations.json",
                        score=score,
                        metadata={"currency": destination.get("currency")},
                    )
                )
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

    def recommend_activities(self, destination: str, cities: list[str], interests: list[str], limit: int = 12) -> list[Activity]:
        activities: list[Activity] = []
        for city in cities:
            activities.extend(self.places.list_activities(destination, city=city, interests=interests))
        if len(activities) < limit:
            existing = {activity.name for activity in activities}
            for city in cities:
                for activity in self.places.list_activities(destination, city=city):
                    if activity.name not in existing:
                        activities.append(activity)
                        existing.add(activity.name)
        return activities[:limit]

    def recommend_hotels(self, request: TripRequest, cities: list[str], nights: int) -> list[Accommodation]:
        if not request.destination:
            return []
        style = request.preferences.travel_style.value if hasattr(request.preferences.travel_style, "value") else str(request.preferences.travel_style)
        if style in {"backpacker", "family", "romantic"}:
            style = "budget" if style == "backpacker" else "balanced"
        return self.hotels.search(
            request.destination,
            cities=sorted(set(cities), key=cities.index),
            style=style,
            nights=nights,
            rooms=request.travelers.rooms,
        )

    def recommend_restaurants(self, destination: str, cities: list[str], food_preferences: list[str] | None = None) -> list[MealSuggestion]:
        food_preferences = food_preferences or []
        restaurants: list[MealSuggestion] = []
        for item in self.sample.get("restaurants", []):
            if item.get("destination", "").lower() != destination.lower():
                continue
            if cities and item.get("city") not in cities:
                continue
            dietary_notes = item.get("dietary_notes", [])
            restaurants.append(
                MealSuggestion(
                    meal=item.get("meal", "lunch"),
                    name=item["name"],
                    cuisine=item.get("cuisine"),
                    city=item.get("city"),
                    description="Fallback meal idea; check hours, reservations and dietary details before going.",
                    estimated_cost=Money(amount=float(item.get("price_inr", 0)), currency="INR", note="Fallback meal estimate"),
                    dietary_notes=[*dietary_notes, *food_preferences],
                    source="static sample_data.json",
                )
            )
        return restaurants

    def transport_tips(self, destination: str) -> list[str]:
        return list((self.sample.get("transport_tips", {}) or {}).get(destination, []))

    def build_set(self, request: TripRequest, cities: list[str], nights: int) -> RecommendationSet:
        destination = request.destination or ""
        return RecommendationSet(
            destinations=self.recommend_destinations(request),
            hotels=self.recommend_hotels(request, cities, nights),
            activities=self.recommend_activities(destination, cities, request.preferences.interests),
            restaurants=self.recommend_restaurants(destination, cities, request.preferences.food_preferences),
            transport_tips=self.transport_tips(destination),
            notes=[
                "Recommendations use static fallback data unless a live integration is configured.",
                "Always verify opening hours, closures, prices and reservation rules before booking.",
            ],
        )
