"""Flight search connector.

Defaults to deterministic fare estimates and explicitly does not claim live
availability. A provider such as Amadeus can be implemented behind this class.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.models import FlightOption, Money
from app.utils import load_json


class FlightsClient:
    def __init__(self):
        self.airports: list[dict[str, Any]] = load_json("airports.json", []) or []
        self.destinations: list[dict[str, Any]] = load_json("destinations.json", []) or []

    def _airport_for(self, query: str | None) -> dict[str, Any] | None:
        if not query:
            return None
        needle = query.strip().lower()
        for airport in self.airports:
            if needle in {airport["iata"].lower(), airport["city"].lower(), airport["country"].lower()}:
                return airport
            if needle in airport["city"].lower() or airport["city"].lower() in needle:
                return airport
        return None

    def _destination_profile(self, destination: str) -> dict[str, Any] | None:
        lower = destination.lower()
        for item in self.destinations:
            aliases = [item.get("name", ""), *item.get("aliases", [])]
            if any(alias.lower() in lower or lower in alias.lower() for alias in aliases):
                return item
        return None

    def search_round_trip(
        self,
        origin: str | None,
        destination: str,
        depart_date: date | None,
        return_date: date | None,
        travelers: int = 1,
    ) -> list[FlightOption]:
        if not origin:
            return []
        origin_airport = self._airport_for(origin)
        profile = self._destination_profile(destination)
        if not profile:
            return []
        origin_country = origin_airport["country"] if origin_airport else "default"
        estimate_map = profile.get("international_flight_estimate_inr", {})
        per_person = float(estimate_map.get(origin_country, estimate_map.get("default", 65000)))
        destination_city = profile.get("cities", [{}])[0].get("name", destination)
        destination_airport = self._airport_for(destination_city)
        dest_code = destination_airport["iata"] if destination_airport else destination_city
        origin_code = origin_airport["iata"] if origin_airport else origin

        saver = FlightOption(
            origin=origin_code,
            destination=dest_code,
            airline="Multiple carriers saver estimate",
            depart_date=depart_date,
            return_date=return_date,
            stops=1,
            duration_hours=10.5,
            estimated_price=Money(amount=per_person * travelers, currency="INR", note="Round-trip estimate for all travelers"),
            baggage_notes="Check baggage and change fees before purchase.",
            source="static fallback fare estimate; not live price or availability",
            availability_live=False,
        )
        flexible = FlightOption(
            origin=origin_code,
            destination=dest_code,
            airline="Flexible timing estimate",
            depart_date=depart_date,
            return_date=return_date,
            stops=0 if per_person < 30000 else 1,
            duration_hours=8.0 if per_person < 30000 else 11.0,
            estimated_price=Money(amount=round(per_person * 1.18 * travelers), currency="INR", note="Higher buffer estimate for better timings"),
            baggage_notes="Use this as a planning buffer, not a quote.",
            source="static fallback fare estimate; not live price or availability",
            availability_live=False,
        )
        return [saver, flexible]
