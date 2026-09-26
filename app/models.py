"""Typed domain models for the AI Travel Agent."""
from __future__ import annotations

from datetime import date as DateType, datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TravelStyle(str, Enum):
    budget = "budget"
    balanced = "balanced"
    comfort = "comfort"
    luxury = "luxury"
    family = "family"
    romantic = "romantic"
    backpacker = "backpacker"


class BookingStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class TransportMode(str, Enum):
    walk = "walk"
    metro = "metro"
    bus = "bus"
    train = "train"
    taxi = "taxi"
    car = "car"
    flight = "flight"
    ferry = "ferry"
    mixed = "mixed"


class Money(BaseModel):
    amount: float = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    note: str | None = None

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    def display(self) -> str:
        rounded = int(round(self.amount))
        symbol = {"INR": "₹", "USD": "$", "EUR": "€", "JPY": "¥", "GBP": "£"}.get(self.currency, f"{self.currency} ")
        if self.currency == "INR":
            return f"{symbol}{rounded:,}"
        return f"{symbol}{rounded:,}" if len(symbol) == 1 else f"{symbol}{rounded:,}"


class BudgetBreakdown(BaseModel):
    accommodation: Money = Field(default_factory=lambda: Money(amount=0))
    food: Money = Field(default_factory=lambda: Money(amount=0))
    activities: Money = Field(default_factory=lambda: Money(amount=0))
    local_transport: Money = Field(default_factory=lambda: Money(amount=0))
    intercity_transport: Money = Field(default_factory=lambda: Money(amount=0))
    flights: Money = Field(default_factory=lambda: Money(amount=0))
    contingency: Money = Field(default_factory=lambda: Money(amount=0))
    total: Money = Field(default_factory=lambda: Money(amount=0))
    notes: list[str] = Field(default_factory=list)


class TravelerGroup(BaseModel):
    adults: int = Field(default=1, ge=1)
    children: int = Field(default=0, ge=0)
    rooms: int = Field(default=1, ge=1)

    @property
    def total(self) -> int:
        return self.adults + self.children


class TravelPreferences(BaseModel):
    interests: list[str] = Field(default_factory=list)
    travel_style: TravelStyle = TravelStyle.balanced
    accommodation: str | None = None
    food_preferences: list[str] = Field(default_factory=list)
    accessibility: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"


class User(BaseModel):
    id: str = Field(default_factory=lambda: f"user_{uuid4().hex[:10]}")
    email: str | None = None
    name: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class UserMemory(BaseModel):
    user_id: str
    favorite_destinations: list[str] = Field(default_factory=list)
    favorite_interests: list[str] = Field(default_factory=list)
    preferred_style: TravelStyle = TravelStyle.balanced
    accommodation: str | None = None
    food_preferences: list[str] = Field(default_factory=list)
    accessibility: list[str] = Field(default_factory=list)
    saved_facts: dict[str, Any] = Field(default_factory=dict)
    trip_history: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class TripRequest(BaseModel):
    """Parsed natural-language travel requirements."""

    text: str = ""
    user_id: str = "guest"
    destination: str | None = None
    origin: str | None = None
    start_date: DateType | None = None
    end_date: DateType | None = None
    duration_days: int | None = Field(default=None, ge=1, le=90)
    travelers: TravelerGroup = Field(default_factory=TravelerGroup)
    budget: Money | None = None
    preferences: TravelPreferences = Field(default_factory=TravelPreferences)
    constraints: list[str] = Field(default_factory=list)
    must_ask: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Activity(BaseModel):
    name: str
    category: str = "sightseeing"
    city: str | None = None
    location: str | None = None
    description: str = ""
    start_time: str | None = None
    end_time: str | None = None
    duration_hours: float = Field(default=1.5, ge=0)
    opening_hours: str | None = None
    estimated_cost: Money = Field(default_factory=lambda: Money(amount=0))
    booking_required: bool = False
    rain_friendly: bool = True
    accessibility_notes: str | None = None
    source: str = "static fallback data"


class MealSuggestion(BaseModel):
    meal: Literal["breakfast", "lunch", "dinner", "snack"]
    name: str
    cuisine: str | None = None
    city: str | None = None
    description: str = ""
    estimated_cost: Money = Field(default_factory=lambda: Money(amount=0))
    dietary_notes: list[str] = Field(default_factory=list)
    source: str = "static fallback data"


class TransportLeg(BaseModel):
    from_place: str
    to_place: str
    mode: TransportMode = TransportMode.mixed
    estimated_minutes: int = Field(default=30, ge=0)
    estimated_cost: Money = Field(default_factory=lambda: Money(amount=0))
    notes: str | None = None
    source: str = "estimated fallback"


class WeatherInfo(BaseModel):
    destination: str
    date: DateType | None = None
    summary: str
    temperature_c_min: float | None = None
    temperature_c_max: float | None = None
    rain_probability: float | None = None
    source: str = "seasonal climate fallback estimate"
    is_live: bool = False


class DayPlan(BaseModel):
    day: int = Field(ge=1)
    date: DateType | None = None
    city: str
    theme: str
    summary: str
    activities: list[Activity] = Field(default_factory=list)
    meals: list[MealSuggestion] = Field(default_factory=list)
    transport: list[TransportLeg] = Field(default_factory=list)
    weather: WeatherInfo | None = None
    estimated_cost: Money = Field(default_factory=lambda: Money(amount=0))
    notes: list[str] = Field(default_factory=list)


class Accommodation(BaseModel):
    name: str
    city: str
    type: str = "hotel"
    rating: float | None = None
    price_per_night: Money = Field(default_factory=lambda: Money(amount=0))
    total_estimated: Money = Field(default_factory=lambda: Money(amount=0))
    amenities: list[str] = Field(default_factory=list)
    location_notes: str | None = None
    source: str = "static fallback estimate"
    availability_live: bool = False


class FlightOption(BaseModel):
    origin: str
    destination: str
    airline: str = "Multiple carriers"
    depart_date: DateType | None = None
    return_date: DateType | None = None
    stops: int | None = None
    duration_hours: float | None = None
    estimated_price: Money = Field(default_factory=lambda: Money(amount=0))
    baggage_notes: str | None = None
    source: str = "mock estimate; not live availability"
    availability_live: bool = False


class SearchResult(BaseModel):
    title: str
    category: str
    summary: str
    url: str | None = None
    source: str
    score: float = Field(default=0.5, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecommendationSet(BaseModel):
    destinations: list[SearchResult] = Field(default_factory=list)
    hotels: list[Accommodation] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
    restaurants: list[MealSuggestion] = Field(default_factory=list)
    transport_tips: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Itinerary(BaseModel):
    destination: str
    duration_days: int
    travelers: TravelerGroup
    start_date: DateType | None = None
    end_date: DateType | None = None
    days: list[DayPlan] = Field(default_factory=list)
    total_estimated_cost: Money = Field(default_factory=lambda: Money(amount=0))
    budget_breakdown: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    budget_status: Literal["unknown", "within_budget", "tight", "over_budget"] = "unknown"
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class Booking(BaseModel):
    id: str = Field(default_factory=lambda: f"booking_{uuid4().hex[:10]}")
    user_id: str
    trip_id: str | None = None
    item_type: Literal["flight", "hotel", "activity", "transport", "other"] = "other"
    item_name: str
    status: BookingStatus = BookingStatus.pending
    amount: Money = Field(default_factory=lambda: Money(amount=0))
    confirmation_code: str | None = None
    provider: str = "manual/mock"
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Notification(BaseModel):
    id: str = Field(default_factory=lambda: f"note_{uuid4().hex[:10]}")
    user_id: str
    trip_id: str | None = None
    title: str
    message: str
    trigger_at: datetime | None = None
    channel: Literal["in_app", "email", "sms"] = "in_app"
    sent: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class TripPlan(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: f"trip_{uuid4().hex[:12]}")
    user_id: str = "guest"
    title: str
    request: TripRequest
    itinerary: Itinerary
    flights: list[FlightOption] = Field(default_factory=list)
    hotels: list[Accommodation] = Field(default_factory=list)
    recommendations: RecommendationSet = Field(default_factory=RecommendationSet)
    bookings: list[Booking] = Field(default_factory=list)
    notifications: list[Notification] = Field(default_factory=list)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentResponse(BaseModel):
    message: str
    trip: TripPlan | None = None
    questions: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)


class APIError(BaseModel):
    detail: str
    code: str = "error"
