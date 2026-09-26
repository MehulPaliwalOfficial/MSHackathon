"""Maps connector for distance and travel-time estimates."""
from __future__ import annotations

from typing import Any

from app.models import Money, TransportLeg, TransportMode
from app.utils import haversine_km, load_json


class MapsClient:
    def __init__(self):
        self.destinations: list[dict[str, Any]] = load_json("destinations.json", []) or []
        self.airports: list[dict[str, Any]] = load_json("airports.json", []) or []

    def _lookup(self, place: str) -> tuple[float, float] | None:
        needle = place.lower()
        for destination in self.destinations:
            for city in destination.get("cities", []):
                if city.get("name", "").lower() in needle or needle in city.get("name", "").lower():
                    return float(city["lat"]), float(city["lon"])
        for airport in self.airports:
            if airport["city"].lower() in needle or airport["iata"].lower() == needle:
                return float(airport["lat"]), float(airport["lon"])
        return None

    def distance_km(self, origin: str, destination: str) -> float | None:
        a, b = self._lookup(origin), self._lookup(destination)
        if not a or not b:
            return None
        return round(haversine_km(a[0], a[1], b[0], b[1]), 1)

    def travel_time_minutes(self, origin: str, destination: str, mode: TransportMode = TransportMode.train) -> int:
        distance = self.distance_km(origin, destination)
        if distance is None:
            return 45
        if distance < 8:
            return max(15, int(distance / 18 * 60) + 10)
        speeds = {
            TransportMode.walk: 5,
            TransportMode.metro: 28,
            TransportMode.bus: 35,
            TransportMode.train: 95,
            TransportMode.taxi: 35,
            TransportMode.car: 55,
            TransportMode.ferry: 25,
            TransportMode.mixed: 45,
            TransportMode.flight: 500,
        }
        speed = speeds.get(mode, 45)
        buffer = 20 if mode in {TransportMode.metro, TransportMode.bus, TransportMode.taxi, TransportMode.mixed} else 45
        if distance > 150 and mode == TransportMode.train:
            speed = 170
            buffer = 50
        return int(distance / speed * 60 + buffer)

    def make_leg(self, origin: str, destination: str, mode: TransportMode = TransportMode.mixed) -> TransportLeg:
        minutes = self.travel_time_minutes(origin, destination, mode)
        distance = self.distance_km(origin, destination)
        cost = 250 if minutes < 60 else 1800
        if mode == TransportMode.train and distance and distance > 250:
            cost = int(distance * 9)
        return TransportLeg(
            from_place=origin,
            to_place=destination,
            mode=mode,
            estimated_minutes=minutes,
            estimated_cost=Money(amount=cost, currency="INR", note="Estimated from distance fallback"),
            notes=f"Approx. {distance} km" if distance is not None else "Distance unavailable; use live maps before travel.",
            source="maps fallback estimate; not live traffic",
        )
