"""Central AI travel agent; understands, researches, plans, validates and responds."""
from __future__ import annotations

from typing import Any

from ai.personalization import PersonalizationEngine
from ai.planner import TravelPlanner
from ai.tools import TravelTools
from app.database import Database, database
from app.memory import MemoryStore
from app.models import AgentResponse, TripPlan
from app.notifications import NotificationService
from app.travel import TravelRequestExtractor, explain_request


class TravelAgent:
    def __init__(self, db: Database | None = None):
        self.db = db or database
        self.db.initialize()
        self.memory = MemoryStore(self.db)
        self.tools = TravelTools()
        self.personalization = PersonalizationEngine()
        self.planner = TravelPlanner(self.tools, notifications=NotificationService(self.db))
        self.extractor = TravelRequestExtractor(self.tools.catalog)

    def handle_message(self, message: str, user_id: str = "guest", trip_id: str | None = None) -> AgentResponse:
        if self._looks_like_modification(message):
            return self._handle_modification(message, user_id, trip_id)
        return self._handle_planning(message, user_id)

    def _handle_planning(self, message: str, user_id: str) -> AgentResponse:
        profile = self.memory.get_profile(user_id)
        request = self.extractor.extract(message, user_id=user_id, memory=profile)
        request = self.personalization.apply(request, profile)
        if request.must_ask:
            return AgentResponse(
                message="I can plan this, but I need a little more information first: " + " ".join(request.must_ask),
                questions=request.must_ask,
                assumptions=request.assumptions,
                confidence=0.55,
            )

        trip = self.planner.create_plan(request)
        self.db.save_trip(trip)
        self.memory.update_from_request(request)
        self.memory.record_trip(trip)
        return AgentResponse(
            message=self._trip_summary(trip),
            trip=trip,
            actions=self._next_actions(trip),
            assumptions=trip.itinerary.assumptions,
            warnings=trip.itinerary.warnings,
            confidence=0.86,
        )

    def _handle_modification(self, message: str, user_id: str, trip_id: str | None) -> AgentResponse:
        raw: dict[str, Any] | None = self.db.get_trip(trip_id, user_id=user_id) if trip_id else self.db.latest_trip(user_id)
        if not raw:
            return AgentResponse(
                message="I can modify a trip once one exists. Please create a trip first or provide a trip_id.",
                questions=["Which existing trip should I modify?"],
                confidence=0.45,
            )
        trip = TripPlan.model_validate(raw)
        before_version = trip.version
        updated = self.planner.modify_plan(trip, message)
        self.db.save_trip(updated)
        changed_note = updated.itinerary.assumptions[-1] if updated.itinerary.assumptions else "Updated the trip."
        return AgentResponse(
            message=(
                f"Updated {updated.title} from version {before_version} to {updated.version}. "
                f"{changed_note} Estimated total is now {updated.itinerary.total_estimated_cost.display()}."
            ),
            trip=updated,
            actions=self._next_actions(updated),
            assumptions=updated.itinerary.assumptions,
            warnings=updated.itinerary.warnings,
            confidence=0.82,
        )

    def _looks_like_modification(self, message: str) -> bool:
        lower = message.lower()
        keywords = [
            "make it",
            "cheaper",
            "more expensive",
            "remove",
            "skip",
            "add",
            "change the plan",
            "going to rain",
            "raining",
            "rain tomorrow",
            "replace",
            "modify",
            "update the trip",
        ]
        return any(keyword in lower for keyword in keywords) and not lower.strip().startswith(("plan", "create", "build"))

    def _trip_summary(self, trip: TripPlan) -> str:
        request_summary = explain_request(trip.request)
        route = " → ".join(dict.fromkeys(day.city for day in trip.itinerary.days))
        budget = trip.itinerary.total_estimated_cost.display()
        status = trip.itinerary.budget_status.replace("_", " ")
        live_note = "All prices, travel times and weather are fallback estimates unless marked live."
        first_day = trip.itinerary.days[0].summary if trip.itinerary.days else ""
        return (
            f"I built a {trip.title}: {request_summary}. Route: {route}. "
            f"Estimated total: {budget} ({status}). {first_day} {live_note}"
        )

    def _next_actions(self, trip: TripPlan) -> list[str]:
        actions = [
            "Verify live flight, hotel and attraction prices before booking.",
            "Tell me natural-language changes like 'make it cheaper', 'remove museums', or 'rain-proof tomorrow'.",
        ]
        if not trip.request.origin:
            actions.insert(0, "Add an origin city if you want flight estimates included.")
        if not trip.request.start_date:
            actions.append("Add travel dates for date-specific opening-hours/weather checks and reminders.")
        return actions
