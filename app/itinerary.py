"""Practical day-by-day itinerary creation and modification."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from app.models import Activity, DayPlan, Itinerary, MealSuggestion, Money, TransportMode, TripPlan, TripRequest
from app.recommendations import RecommendationEngine
from app.travel import DestinationCatalog
from integrations.maps import MapsClient
from integrations.places import PlacesClient
from integrations.weather import WeatherClient


class ItineraryBuilder:
    def __init__(
        self,
        catalog: DestinationCatalog | None = None,
        places: PlacesClient | None = None,
        maps: MapsClient | None = None,
        weather: WeatherClient | None = None,
        recommendations: RecommendationEngine | None = None,
    ):
        self.catalog = catalog or DestinationCatalog()
        self.places = places or PlacesClient()
        self.maps = maps or MapsClient()
        self.weather = weather or WeatherClient()
        self.recommendations = recommendations or RecommendationEngine(self.places)

    def build(
        self,
        request: TripRequest,
        destination_profile: dict[str, Any] | None,
        budget_breakdown: Any,
        budget_status: str,
        warnings: list[str] | None = None,
    ) -> Itinerary:
        if not request.destination or not request.duration_days:
            raise ValueError("Destination and duration are required to build an itinerary.")
        route = self.catalog.route_for_duration(request.destination, request.duration_days)
        start_date = request.start_date
        days: list[DayPlan] = []
        used_activities: set[str] = set()
        pace_count = {"relaxed": 2, "balanced": 3, "packed": 4}.get(request.preferences.pace, 3)
        base_daily_cost = max(
            0,
            (budget_breakdown.total.amount - budget_breakdown.flights.amount - budget_breakdown.contingency.amount)
            / max(request.duration_days, 1),
        )

        for index, city in enumerate(route, start=1):
            current_date = start_date + timedelta(days=index - 1) if start_date else None
            city_changed = index > 1 and route[index - 2] != city
            weather = self.weather.forecast(f"{city}, {request.destination}", current_date)
            activities = self._pick_activities(
                request=request,
                city=city,
                count=max(1, pace_count - (1 if city_changed or index == 1 else 0)),
                used=used_activities,
            )
            self._assign_times(activities, city_changed=city_changed, day_number=index)
            meals = self._meals_for_day(request, city)
            transport = []
            if city_changed:
                previous_city = route[index - 2]
                transport.append(self.maps.make_leg(previous_city, city, TransportMode.train))
            if activities:
                transport.append(
                    self.maps.make_leg(
                        f"{city} accommodation",
                        activities[0].location or activities[0].name,
                        TransportMode.metro,
                    )
                )
            notes = [
                "Verify live opening hours and transit before the day starts.",
                "Keep 60-90 minutes buffer for meals, queues and rest.",
            ]
            if city_changed:
                notes.append("This is a city-transfer day, so sightseeing is intentionally lighter.")
            if weather.rain_probability and weather.rain_probability >= 0.5:
                notes.append("Rain risk is elevated; keep listed indoor/rain-friendly alternatives ready.")
            if request.preferences.accessibility:
                notes.append("Accessibility preference noted: " + ", ".join(request.preferences.accessibility))

            day = DayPlan(
                day=index,
                date=current_date,
                city=city,
                theme=self._theme_for_day(city, activities, index),
                summary=self._summary_for_day(city, activities, city_changed),
                activities=activities,
                meals=meals,
                transport=transport,
                weather=weather,
                estimated_cost=Money(amount=round(base_daily_cost), currency="INR", note="Daily share of planning estimate excluding flights buffer"),
                notes=notes,
            )
            days.append(day)

        assumptions = list(request.assumptions)
        assumptions.extend(
            [
                "Activity costs, meal costs and travel times are estimates from fallback data.",
                "The plan avoids claiming live prices, availability, weather or confirmed bookings.",
            ]
        )
        end_date = start_date + timedelta(days=request.duration_days - 1) if start_date else None
        sources = [
            "data/destinations.json",
            "data/sample_data.json",
            "fallback maps/weather/flight/hotel connectors",
        ]
        return Itinerary(
            destination=request.destination,
            duration_days=request.duration_days,
            travelers=request.travelers,
            start_date=start_date,
            end_date=end_date,
            days=days,
            total_estimated_cost=budget_breakdown.total,
            budget_breakdown=budget_breakdown,
            budget_status=budget_status,  # type: ignore[arg-type]
            assumptions=assumptions,
            warnings=warnings or [],
            sources=sources,
        )

    def _pick_activities(self, request: TripRequest, city: str, count: int, used: set[str]) -> list[Activity]:
        assert request.destination is not None
        all_activities = self.places.list_activities(request.destination, city=city, interests=request.preferences.interests)
        if len(all_activities) < count:
            all_activities = self.places.list_activities(request.destination, city=city)
        constraints = " ".join([*request.constraints, *request.preferences.constraints]).lower()
        filtered: list[Activity] = []
        for activity in all_activities:
            haystack = f"{activity.name} {activity.category}".lower()
            if "avoid museum" in constraints and "museum" in haystack:
                continue
            if activity.name in used:
                continue
            filtered.append(activity)
        if not filtered and all_activities:
            filtered = [a for a in all_activities if a.name not in used] or all_activities
        chosen = filtered[:count]
        for activity in chosen:
            used.add(activity.name)
        if not chosen:
            chosen = [
                Activity(
                    name=f"Explore {city} local neighborhood",
                    category="culture",
                    city=city,
                    description="Flexible self-guided fallback block. Replace with live place search results in production.",
                    duration_hours=2,
                    opening_hours="Flexible",
                    estimated_cost=Money(amount=500, currency="INR", note="Fallback estimate"),
                    rain_friendly=True,
                    source="generated fallback activity estimate",
                )
            ]
        return chosen

    def _assign_times(self, activities: list[Activity], city_changed: bool, day_number: int) -> None:
        slots = ["09:30", "13:30", "18:00", "20:00"]
        if city_changed:
            slots = ["13:30", "17:00", "20:00"]
        if day_number == 1:
            slots = ["10:30", "15:00", "18:30"]
        for activity, start in zip(activities, slots):
            activity.start_time = start
            hour, minute = map(int, start.split(":"))
            total_minutes = hour * 60 + minute + int(activity.duration_hours * 60)
            activity.end_time = f"{(total_minutes // 60) % 24:02d}:{total_minutes % 60:02d}"

    def _meals_for_day(self, request: TripRequest, city: str) -> list[MealSuggestion]:
        assert request.destination is not None
        restaurant_pool = self.recommendations.recommend_restaurants(
            request.destination,
            cities=[city],
            food_preferences=request.preferences.food_preferences,
        )
        meals: list[MealSuggestion] = [
            MealSuggestion(
                meal="breakfast",
                name="Simple local breakfast near accommodation",
                cuisine="local/cafe",
                city=city,
                description="Keep breakfast close to reduce morning transit and cost.",
                estimated_cost=Money(amount=500 * request.travelers.total, currency="INR", note="Fallback breakfast estimate"),
                dietary_notes=request.preferences.food_preferences,
                source="generated fallback meal estimate",
            )
        ]
        if restaurant_pool:
            lunch = restaurant_pool[0]
            lunch.meal = "lunch"
            lunch.estimated_cost.amount *= request.travelers.total
            meals.append(lunch)
        else:
            meals.append(
                MealSuggestion(
                    meal="lunch",
                    name=f"Affordable lunch in {city}",
                    cuisine="local",
                    city=city,
                    description="Use current reviews and proximity on the day.",
                    estimated_cost=Money(amount=900 * request.travelers.total, currency="INR", note="Fallback lunch estimate"),
                    dietary_notes=request.preferences.food_preferences,
                    source="generated fallback meal estimate",
                )
            )
        dinner = restaurant_pool[1] if len(restaurant_pool) > 1 else None
        if dinner:
            dinner.meal = "dinner"
            dinner.estimated_cost.amount *= request.travelers.total
            meals.append(dinner)
        else:
            meals.append(
                MealSuggestion(
                    meal="dinner",
                    name=f"Casual dinner in {city}",
                    cuisine="local",
                    city=city,
                    description="Pick a nearby restaurant after the final activity to avoid backtracking.",
                    estimated_cost=Money(amount=1200 * request.travelers.total, currency="INR", note="Fallback dinner estimate"),
                    dietary_notes=request.preferences.food_preferences,
                    source="generated fallback meal estimate",
                )
            )
        return meals

    def _theme_for_day(self, city: str, activities: list[Activity], day_number: int) -> str:
        categories = []
        for activity in activities:
            if activity.category not in categories:
                categories.append(activity.category)
        if not categories:
            return f"Day {day_number}: Flexible {city} day"
        return f"{city}: " + ", ".join(category.title() for category in categories[:3])

    def _summary_for_day(self, city: str, activities: list[Activity], city_changed: bool) -> str:
        if city_changed:
            prefix = f"Transfer to {city}, then keep the rest of the day lighter."
        else:
            prefix = f"Explore {city} with a realistic mix of sightseeing, meals and rest."
        if activities:
            names = ", ".join(activity.name for activity in activities[:2])
            return f"{prefix} Key stops: {names}."
        return prefix


class ItineraryModifier:
    """Modify only affected itinerary pieces while preserving the rest."""

    def __init__(self, places: PlacesClient | None = None):
        self.places = places or PlacesClient()

    def modify(self, trip: TripPlan, instruction: str) -> TripPlan:
        lower = instruction.lower()
        changed: list[str] = []
        warnings: list[str] = []

        if any(word in lower for word in ["cheaper", "cheap", "reduce budget", "less expensive", "save money"]):
            self._make_cheaper(trip)
            changed.append("reduced estimated costs and replaced expensive blocks where possible")

        if any(word in lower for word in ["remove museum", "remove museums", "no museums", "skip museums", "avoid museums"]):
            removed = self._remove_category(trip, "museum")
            changed.append(f"removed {removed} museum-related activity block(s)")

        if "rain" in lower or "raining" in lower:
            affected_day = 2 if "tomorrow" in lower and len(trip.itinerary.days) >= 2 else 1
            replaced = self._rainproof_day(trip, affected_day)
            changed.append(f"rain-proofed day {affected_day} with {replaced} indoor/rain-friendly replacement(s)")

        beach_match = re.search(r"add\s+(\d+|one|two|three)\s+beach\s+days?", lower)
        if beach_match or "add beach" in lower:
            count = {"one": 1, "two": 2, "three": 3}.get(beach_match.group(1), None) if beach_match else None
            if count is None:
                count = int(beach_match.group(1)) if beach_match and beach_match.group(1).isdigit() else 1
            added, warning = self._add_beach_days(trip, int(count))
            changed.append(f"added {added} beach/rest day(s)")
            if warning:
                warnings.append(warning)

        if not changed:
            trip.itinerary.warnings.append(
                "Modification request was understood, but no targeted rule matched. Try: make it cheaper, remove museums, add two beach days, or rain-proof tomorrow."
            )
        else:
            trip.itinerary.assumptions.append("Modification applied: " + "; ".join(changed) + ".")
            trip.itinerary.warnings.extend(warnings)

        trip.version += 1
        trip.updated_at = datetime.now(timezone.utc)
        return trip

    def _make_cheaper(self, trip: TripPlan) -> None:
        for day in trip.itinerary.days:
            day.estimated_cost.amount = round(day.estimated_cost.amount * 0.85)
            day.notes.append("Cheaper version: prioritize public transport, free viewpoints and convenience-store/simple meals.")
            for activity in day.activities:
                if activity.estimated_cost.amount > 2000:
                    activity.description += " (Budget tweak: consider a self-guided or shorter alternative.)"
                    activity.estimated_cost.amount = round(activity.estimated_cost.amount * 0.65)
        for hotel in trip.hotels:
            hotel.price_per_night.amount = round(hotel.price_per_night.amount * 0.9)
            hotel.total_estimated.amount = round(hotel.total_estimated.amount * 0.9)
        trip.itinerary.budget_breakdown.total.amount = round(trip.itinerary.budget_breakdown.total.amount * 0.88)
        trip.itinerary.total_estimated_cost = trip.itinerary.budget_breakdown.total
        if trip.request.budget:
            budget_amount = trip.request.budget.amount
            if trip.request.budget.currency != "INR":
                from integrations.currency import CurrencyClient

                budget_amount = CurrencyClient().convert(trip.request.budget, "INR").amount
            if trip.itinerary.total_estimated_cost.amount <= budget_amount * 0.92:
                trip.itinerary.budget_status = "within_budget"
            elif trip.itinerary.total_estimated_cost.amount <= budget_amount:
                trip.itinerary.budget_status = "tight"
            else:
                trip.itinerary.budget_status = "over_budget"

    def _remove_category(self, trip: TripPlan, category: str) -> int:
        removed = 0
        for day in trip.itinerary.days:
            kept = []
            for activity in day.activities:
                if category in activity.category.lower() or category in activity.name.lower():
                    removed += 1
                    continue
                kept.append(activity)
            if len(kept) != len(day.activities):
                replacement = self._replacement_activity(trip.itinerary.destination, day.city, avoid=category)
                if replacement:
                    kept.append(replacement)
                day.activities = kept
                day.summary = f"Updated to avoid {category}; preserved the rest of the day structure."
        trip.request.constraints.append(f"avoid {category}")
        return removed

    def _rainproof_day(self, trip: TripPlan, day_number: int) -> int:
        if day_number < 1 or day_number > len(trip.itinerary.days):
            return 0
        day = trip.itinerary.days[day_number - 1]
        replacements = self.places.rainy_day_alternatives(trip.itinerary.destination, day.city)
        used = {activity.name for activity in day.activities}
        replaced = 0
        for index, activity in enumerate(list(day.activities)):
            if activity.rain_friendly:
                continue
            replacement = next((candidate for candidate in replacements if candidate.name not in used), None)
            if replacement:
                replacement.start_time = activity.start_time
                replacement.end_time = activity.end_time
                day.activities[index] = replacement
                used.add(replacement.name)
                replaced += 1
        day.notes.append("Rain adjustment: outdoor/non-rain-friendly blocks were swapped where alternatives existed.")
        return replaced

    def _add_beach_days(self, trip: TripPlan, count: int) -> tuple[int, str | None]:
        destination = trip.itinerary.destination
        all_beaches: list[Activity] = []
        for day in trip.itinerary.days:
            all_beaches.extend(
                [activity for activity in self.places.list_activities(destination, city=day.city, interests=["beach"]) if activity.category == "beach"]
            )
        warning = None
        if not all_beaches:
            warning = f"No beach activities exist in fallback data for {destination}; added generic waterfront/rest days instead."
        start_index = len(trip.itinerary.days) + 1
        for offset in range(count):
            source_city = trip.itinerary.days[-1].city if trip.itinerary.days else destination
            activity = all_beaches[offset % len(all_beaches)] if all_beaches else Activity(
                name=f"Waterfront or rest day near {source_city}",
                category="relaxation",
                city=source_city,
                description="Fallback beach/rest block. Confirm an actual beach or waterfront option with live search for this destination.",
                duration_hours=4,
                opening_hours="Daylight hours",
                estimated_cost=Money(amount=1000 * trip.request.travelers.total, currency="INR", note="Fallback estimate"),
                rain_friendly=False,
                source="generated fallback beach/rest estimate",
            )
            day_date = None
            if trip.itinerary.start_date:
                day_date = trip.itinerary.start_date + timedelta(days=start_index + offset - 1)
            new_day = DayPlan(
                day=start_index + offset,
                date=day_date,
                city=activity.city or source_city,
                theme=f"{activity.city or source_city}: Beach/rest day",
                summary="A lower-intensity day added without changing earlier itinerary days.",
                activities=[activity],
                meals=[],
                transport=[],
                estimated_cost=Money(amount=2500 * trip.request.travelers.total, currency="INR", note="Fallback added-day estimate"),
                notes=["Added by modification request; verify actual beach logistics before booking."],
            )
            trip.itinerary.days.append(new_day)
        trip.itinerary.duration_days += count
        trip.request.duration_days = trip.itinerary.duration_days
        if trip.itinerary.end_date:
            trip.itinerary.end_date = trip.itinerary.end_date + timedelta(days=count)
        return count, warning

    def _replacement_activity(self, destination: str, city: str, avoid: str) -> Activity | None:
        for activity in self.places.list_activities(destination, city=city):
            if avoid not in activity.category.lower() and avoid not in activity.name.lower():
                return activity
        return None
