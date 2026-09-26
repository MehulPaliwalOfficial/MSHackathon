"""Converts requirements into realistic travel plans."""
from __future__ import annotations

from app.itinerary import ItineraryBuilder, ItineraryModifier
from app.models import TripPlan, TripRequest
from app.notifications import NotificationService
from app.recommendations import RecommendationEngine
from app.travel import estimate_budget
from ai.tools import TravelTools


class TravelPlanner:
    def __init__(self, tools: TravelTools | None = None, notifications: NotificationService | None = None):
        self.tools = tools or TravelTools()
        self.recommendations = RecommendationEngine(self.tools.places, self.tools.hotels)
        self.itinerary_builder = ItineraryBuilder(
            catalog=self.tools.catalog,
            places=self.tools.places,
            maps=self.tools.maps,
            weather=self.tools.weather,
            recommendations=self.recommendations,
        )
        self.modifier = ItineraryModifier(self.tools.places)
        self.notifications = notifications

    def create_plan(self, request: TripRequest) -> TripPlan:
        if request.must_ask:
            raise ValueError("Cannot create plan until required questions are answered: " + "; ".join(request.must_ask))
        assert request.destination is not None
        assert request.duration_days is not None
        profile = self.tools.destination_profile(request.destination)
        route = self.tools.catalog.route_for_duration(request.destination, request.duration_days)
        unique_cities = sorted(set(route), key=route.index)
        nights = max(request.duration_days - 1, 1)

        flights = self.tools.flight_options(
            request.origin,
            request.destination,
            request.start_date,
            request.end_date,
            travelers=request.travelers.total,
        )
        budget_breakdown, budget_status, budget_warnings = estimate_budget(request, profile, flights)
        recommendation_set = self.recommendations.build_set(request, unique_cities, nights)
        itinerary = self.itinerary_builder.build(
            request,
            profile,
            budget_breakdown=budget_breakdown,
            budget_status=budget_status,
            warnings=budget_warnings,
        )
        title = f"{request.duration_days}-day {request.destination} trip"
        trip = TripPlan(
            user_id=request.user_id,
            title=title,
            request=request,
            itinerary=itinerary,
            flights=flights,
            hotels=recommendation_set.hotels,
            recommendations=recommendation_set,
        )
        if self.notifications:
            trip.notifications = self.notifications.generate_trip_reminders(trip)
        return trip

    def modify_plan(self, trip: TripPlan, instruction: str) -> TripPlan:
        return self.modifier.modify(trip, instruction)
