"""User preferences, travel history and saved information."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.database import Database, database
from app.models import TripPlan, TripRequest, TravelStyle, UserMemory
from app.utils import unique_preserve_order


class MemoryStore:
    """High-level access to durable user travel memory."""

    PROFILE_KEY = "profile"

    def __init__(self, db: Database | None = None):
        self.db = db or database
        self.db.initialize()

    def get_profile(self, user_id: str) -> UserMemory:
        raw = self.db.get_memory(user_id, self.PROFILE_KEY)
        if not raw:
            return UserMemory(user_id=user_id)
        return UserMemory.model_validate(raw)

    def save_profile(self, profile: UserMemory) -> UserMemory:
        profile.updated_at = datetime.now(timezone.utc)
        self.db.save_memory(profile.user_id, self.PROFILE_KEY, profile)
        return profile

    def update_from_request(self, request: TripRequest) -> UserMemory:
        profile = self.get_profile(request.user_id)
        if request.destination:
            profile.favorite_destinations = unique_preserve_order([request.destination, *profile.favorite_destinations])[:10]
        if request.preferences.interests:
            profile.favorite_interests = unique_preserve_order([*request.preferences.interests, *profile.favorite_interests])[:20]
        if request.preferences.travel_style:
            profile.preferred_style = request.preferences.travel_style
        if request.preferences.accommodation:
            profile.accommodation = request.preferences.accommodation
        if request.preferences.food_preferences:
            profile.food_preferences = unique_preserve_order(
                [*request.preferences.food_preferences, *profile.food_preferences]
            )[:20]
        if request.preferences.accessibility:
            profile.accessibility = unique_preserve_order([*request.preferences.accessibility, *profile.accessibility])[:20]
        return self.save_profile(profile)

    def record_trip(self, trip: TripPlan) -> UserMemory:
        profile = self.get_profile(trip.user_id)
        summary: dict[str, Any] = {
            "trip_id": trip.id,
            "title": trip.title,
            "destination": trip.itinerary.destination,
            "duration_days": trip.itinerary.duration_days,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        profile.trip_history = [summary, *profile.trip_history[:19]]
        return self.save_profile(profile)

    def remember_fact(self, user_id: str, key: str, value: Any) -> UserMemory:
        profile = self.get_profile(user_id)
        profile.saved_facts[key] = value
        return self.save_profile(profile)
