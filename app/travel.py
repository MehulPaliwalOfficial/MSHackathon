"""Core travel logic, constraints, destinations and trip calculations."""
from __future__ import annotations

from datetime import timedelta
import re
from typing import Any

from app.models import BudgetBreakdown, Money, TravelerGroup, TravelPreferences, TravelStyle, TripRequest, FlightOption
from app.utils import (
    compact_sentence,
    date_range_from_start,
    load_json,
    parse_budget,
    parse_duration_days,
    parse_iso_or_slash_date,
    unique_preserve_order,
    word_or_number_to_int,
)

INTEREST_KEYWORDS: dict[str, list[str]] = {
    "food": ["food", "street food", "restaurants", "eat", "culinary", "cuisine", "coffee", "cafes"],
    "culture": ["culture", "cultural", "temple", "shrines", "heritage", "local life", "tradition"],
    "nature": ["nature", "parks", "mountains", "forest", "scenery", "landscape", "outdoors"],
    "history": ["history", "historical", "fort", "castle", "old town", "ancient"],
    "museum": ["museum", "museums", "gallery", "art"],
    "beach": ["beach", "island", "sea", "snorkel", "coast"],
    "shopping": ["shopping", "market", "souks", "bazaars"],
    "nightlife": ["nightlife", "bars", "clubs", "late night"],
    "adventure": ["adventure", "hike", "hiking", "rafting", "diving"],
    "relaxation": ["relax", "spa", "wellness", "slow", "rest"],
}

FOOD_KEYWORDS = ["vegetarian", "vegan", "halal", "kosher", "gluten-free", "seafood", "no pork", "no beef"]
ACCESSIBILITY_KEYWORDS = ["wheelchair", "step-free", "mobility", "accessible", "stroller", "senior friendly"]


class DestinationCatalog:
    def __init__(self):
        self.destinations: list[dict[str, Any]] = load_json("destinations.json", []) or []

    def all(self) -> list[dict[str, Any]]:
        return self.destinations

    def find(self, query: str | None) -> dict[str, Any] | None:
        if not query:
            return None
        needle = query.strip().lower()
        for destination in self.destinations:
            aliases = [destination.get("name", ""), *destination.get("aliases", [])]
            if any(needle == alias.lower() for alias in aliases):
                return destination
        for destination in self.destinations:
            aliases = [destination.get("name", ""), *destination.get("aliases", [])]
            if any(needle in alias.lower() or alias.lower() in needle for alias in aliases):
                return destination
        return None

    def infer_destination(self, text: str) -> str | None:
        lower = text.lower()
        for destination in self.destinations:
            aliases = [destination.get("name", ""), *destination.get("aliases", [])]
            if any(re.search(rf"\b{re.escape(alias.lower())}\b", lower) for alias in aliases if alias):
                return destination["name"]
        # Fallback: capture common "to/in/visit" phrase and title-case it.
        match = re.search(r"\b(?:to|in|visit|visiting|for)\s+([A-Z][A-Za-z\s]{2,40})(?:\s+for|\s+under|\s+with|[,.]|$)", text)
        if match:
            return match.group(1).strip()
        return None

    def route_for_duration(self, destination_name: str, duration_days: int) -> list[str]:
        profile = self.find(destination_name)
        if not profile:
            return [destination_name] * duration_days
        routes = profile.get("suggested_routes", [])
        selected = None
        for route in routes:
            if route.get("min_days", 1) <= duration_days <= route.get("max_days", 90):
                selected = route
                break
        if not selected and routes:
            selected = min(routes, key=lambda route: abs(route.get("max_days", 1) - duration_days))
        city_days = selected.get("cities", []) if selected else []
        if not city_days:
            cities = profile.get("cities", [])
            city = cities[0]["name"] if cities else destination_name
            return [city] * duration_days
        planned: list[str] = []
        for entry in city_days:
            planned.extend([entry["name"]] * int(entry.get("days", 1)))
        # Scale route to exact duration while preserving order.
        while len(planned) < duration_days:
            # Add extra days to the city with the largest existing allocation.
            counts = {city: planned.count(city) for city in set(planned)}
            city = max(counts, key=counts.get)
            insert_at = max(i for i, c in enumerate(planned) if c == city) + 1
            planned.insert(insert_at, city)
        return planned[:duration_days]


class TravelRequestExtractor:
    """Rule-based NLU for travel requirements.

    It is deterministic, testable and safe for production fallback. An LLM parser
    can be layered on top later, but should still output this typed model.
    """

    def __init__(self, catalog: DestinationCatalog | None = None):
        self.catalog = catalog or DestinationCatalog()

    def extract(self, text: str, user_id: str = "guest", memory: Any | None = None) -> TripRequest:
        duration = parse_duration_days(text)
        destination = self.catalog.infer_destination(text)
        origin = self._extract_origin(text)
        start_date = parse_iso_or_slash_date(text)
        end_date = None
        if start_date and duration:
            _, end_date = date_range_from_start(start_date, duration)
        budget = parse_budget(text)
        travelers = self._extract_travelers(text)
        preferences = self._extract_preferences(text)

        if memory:
            if not preferences.interests:
                preferences.interests = list(getattr(memory, "favorite_interests", []) or [])[:5]
            if preferences.travel_style == TravelStyle.balanced and getattr(memory, "preferred_style", None):
                preferences.travel_style = getattr(memory, "preferred_style")
            if not preferences.accommodation:
                preferences.accommodation = getattr(memory, "accommodation", None)
            if not preferences.food_preferences:
                preferences.food_preferences = list(getattr(memory, "food_preferences", []) or [])
            if not preferences.accessibility:
                preferences.accessibility = list(getattr(memory, "accessibility", []) or [])

        assumptions: list[str] = []
        if not start_date:
            assumptions.append("Dates were not provided, so the itinerary is date-flexible and uses seasonal weather estimates only.")
        if not origin:
            assumptions.append("Origin city was not provided; international flights are excluded unless a generic fallback estimate is explicitly available.")
        if not budget:
            assumptions.append("No total budget was provided, so costs are planning estimates rather than a constraint.")
        if not preferences.interests:
            preferences.interests = ["culture", "food", "nature"]
            assumptions.append("No interests were provided; using culture, food and nature as balanced defaults.")

        request = TripRequest(
            text=text,
            user_id=user_id,
            destination=destination,
            origin=origin,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration,
            travelers=travelers,
            budget=budget,
            preferences=preferences,
            constraints=self._extract_constraints(text),
            assumptions=assumptions,
        )
        request.must_ask = validate_request(request)
        return request

    def _extract_origin(self, text: str) -> str | None:
        match = re.search(
            r"\bfrom\s+([A-Za-z][A-Za-z\s]{1,35}?)(?:\s+(?:to|for|under|with|on|between|in)\b|[,.]|$)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip().title()
        match = re.search(r"\borigin\s*[:=]?\s*([A-Za-z][A-Za-z\s]{1,35})", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
        return None

    def _extract_travelers(self, text: str) -> TravelerGroup:
        lower = text.lower()
        if re.search(r"\bsolo\b|\balone\b", lower):
            return TravelerGroup(adults=1, rooms=1)
        if re.search(r"\bcouple\b|\btwo of us\b", lower):
            return TravelerGroup(adults=2, rooms=1)
        patterns = [
            r"\bfor\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:people|persons|travelers|travellers|adults)\b",
            r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:people|persons|travelers|travellers|adults)\b",
            r"\bfamily\s+of\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                total = word_or_number_to_int(match.group(1)) or 1
                rooms = max(1, (total + 1) // 2)
                return TravelerGroup(adults=total, rooms=rooms)
        return TravelerGroup(adults=1, rooms=1)

    def _extract_preferences(self, text: str) -> TravelPreferences:
        lower = text.lower()
        interests: list[str] = []
        for interest, keywords in INTEREST_KEYWORDS.items():
            if any(keyword in lower for keyword in keywords):
                interests.append(interest)

        style = TravelStyle.balanced
        pace = "balanced"
        if any(word in lower for word in ["cheap", "cheaper", "budget", "shoestring", "under ₹", "under rs", "under inr"]):
            style = TravelStyle.budget
        if any(word in lower for word in ["luxury", "5 star", "five star", "premium"]):
            style = TravelStyle.luxury
        elif any(word in lower for word in ["comfortable", "comfort", "nice hotels"]):
            style = TravelStyle.comfort
        elif any(word in lower for word in ["backpack", "hostel"]):
            style = TravelStyle.backpacker
        elif any(word in lower for word in ["honeymoon", "romantic"]):
            style = TravelStyle.romantic
        elif "family" in lower:
            style = TravelStyle.family
        if any(word in lower for word in ["relaxed", "slow", "easy pace", "not hectic"]):
            pace = "relaxed"
        if any(word in lower for word in ["packed", "cover a lot", "fast paced"]):
            pace = "packed"

        accommodation = None
        for keyword in ["hostel", "guesthouse", "hotel", "apartment", "resort", "ryokan", "villa"]:
            if keyword in lower:
                accommodation = keyword
                break

        food_preferences = [keyword for keyword in FOOD_KEYWORDS if keyword in lower]
        accessibility = [keyword for keyword in ACCESSIBILITY_KEYWORDS if keyword in lower]
        return TravelPreferences(
            interests=unique_preserve_order(interests),
            travel_style=style,
            accommodation=accommodation,
            food_preferences=unique_preserve_order(food_preferences),
            accessibility=unique_preserve_order(accessibility),
            pace=pace,  # type: ignore[arg-type]
        )

    def _extract_constraints(self, text: str) -> list[str]:
        lower = text.lower()
        constraints: list[str] = []
        no_patterns = re.findall(r"\b(?:no|avoid|remove|skip)\s+([a-z\s]{3,30})(?:[,.]|\band\b|$)", lower)
        for item in no_patterns:
            constraints.append(f"avoid {item.strip()}")
        if "not too much walking" in lower or "less walking" in lower:
            constraints.append("limit walking")
        if "rain" in lower:
            constraints.append("weather flexibility")
        return unique_preserve_order(constraints)


def validate_request(request: TripRequest) -> list[str]:
    questions: list[str] = []
    if not request.destination:
        questions.append("Where would you like to travel?")
    if not request.duration_days:
        questions.append("How many days or nights should the trip cover?")
    if request.travelers.total < 1:
        questions.append("How many travelers are going?")
    return questions


def estimate_budget(
    request: TripRequest,
    destination_profile: dict[str, Any] | None,
    flights: list[FlightOption] | None = None,
) -> tuple[BudgetBreakdown, str, list[str]]:
    """Estimate trip costs and compare against user budget.

    All figures are planning estimates. Live inventory must come from provider
    integrations before a user makes purchases.
    """
    warnings: list[str] = []
    days = request.duration_days or 1
    travelers = request.travelers.total
    style_key = request.preferences.travel_style.value if hasattr(request.preferences.travel_style, "value") else str(request.preferences.travel_style)
    if style_key in {"family", "romantic", "backpacker"}:
        style_key = "balanced" if style_key != "backpacker" else "budget"
    profile_budgets = (destination_profile or {}).get("daily_budget_inr", {})
    daily_pp = float(profile_budgets.get(style_key, profile_budgets.get("balanced", 6000)))
    local_total = daily_pp * days * travelers
    nights = max(days - 1, 1)

    accommodation = local_total * 0.42
    food = local_total * 0.22
    activities = local_total * 0.18
    local_transport = local_total * 0.10
    intercity_transport = local_total * 0.08 if days >= 4 else local_total * 0.03
    flight_total = flights[0].estimated_price.amount if flights else 0
    subtotal = accommodation + food + activities + local_transport + intercity_transport + flight_total
    contingency = subtotal * 0.06
    total = subtotal + contingency
    if not flights and not request.origin:
        warnings.append("Flight costs are excluded because origin city was not provided.")
    if request.origin and not flights:
        warnings.append("Flight estimate is unavailable for the given origin/destination in fallback data.")
    if nights < days - 1:
        warnings.append("Accommodation nights could not be fully inferred; verify check-in/check-out dates.")

    breakdown = BudgetBreakdown(
        accommodation=Money(amount=round(accommodation), currency="INR", note="Planning estimate"),
        food=Money(amount=round(food), currency="INR", note="Planning estimate"),
        activities=Money(amount=round(activities), currency="INR", note="Planning estimate"),
        local_transport=Money(amount=round(local_transport), currency="INR", note="Planning estimate"),
        intercity_transport=Money(amount=round(intercity_transport), currency="INR", note="Planning estimate"),
        flights=Money(amount=round(flight_total), currency="INR", note="Fallback estimate; not live" if flight_total else "Excluded"),
        contingency=Money(amount=round(contingency), currency="INR", note="6% planning buffer"),
        total=Money(amount=round(total), currency="INR", note="Estimated total; verify live prices before booking"),
        notes=[
            "Budget uses static fallback cost bands and does not represent live availability.",
            f"Style cost band: {style_key}; travelers: {travelers}; duration: {days} days.",
        ],
    )

    if not request.budget:
        status = "unknown"
    else:
        budget_amount_inr = request.budget.amount
        if request.budget.currency != "INR":
            from integrations.currency import CurrencyClient

            budget_amount_inr = CurrencyClient().convert(request.budget, "INR").amount
            warnings.append("Budget comparison converted the stated budget to INR using static fallback FX rates.")
        if total <= budget_amount_inr * 0.92:
            status = "within_budget"
        elif total <= budget_amount_inr:
            status = "tight"
        else:
            status = "over_budget"
            warnings.append(
                f"Estimated total {breakdown.total.display()} is above the stated budget {request.budget.display()}."
            )
    return breakdown, status, warnings


def explain_request(request: TripRequest) -> str:
    parts = []
    if request.destination:
        parts.append(request.destination)
    if request.duration_days:
        parts.append(f"{request.duration_days} days")
    if request.budget:
        parts.append(f"budget {request.budget.display()}")
    parts.append(f"{request.travelers.total} traveler{'s' if request.travelers.total != 1 else ''}")
    if request.preferences.interests:
        parts.append("interests: " + compact_sentence(request.preferences.interests))
    return "; ".join(parts)
