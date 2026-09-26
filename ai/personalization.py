"""Adapts plans to the individual user."""
from __future__ import annotations

from app.models import TripRequest, UserMemory
from app.utils import unique_preserve_order


class PersonalizationEngine:
    def apply(self, request: TripRequest, memory: UserMemory | None) -> TripRequest:
        if not memory:
            return request
        if not request.preferences.interests and memory.favorite_interests:
            request.preferences.interests = memory.favorite_interests[:5]
            request.assumptions.append("Used saved interests from memory because none were provided.")
        if not request.preferences.food_preferences and memory.food_preferences:
            request.preferences.food_preferences = memory.food_preferences[:]
            request.assumptions.append("Used saved food preferences from memory.")
        if not request.preferences.accessibility and memory.accessibility:
            request.preferences.accessibility = memory.accessibility[:]
            request.assumptions.append("Used saved accessibility preferences from memory.")
        if not request.preferences.accommodation and memory.accommodation:
            request.preferences.accommodation = memory.accommodation
            request.assumptions.append("Used saved accommodation preference from memory.")
        request.preferences.interests = unique_preserve_order(request.preferences.interests)
        return request

    def explanation(self, memory: UserMemory | None) -> str | None:
        if not memory:
            return None
        details = []
        if memory.favorite_interests:
            details.append("interests " + ", ".join(memory.favorite_interests[:3]))
        if memory.preferred_style:
            details.append(f"style {memory.preferred_style}")
        if not details:
            return None
        return "Personalized using saved " + "; ".join(details) + "."
