"""Tools the AI can call: search, maps, flights, hotels, weather, currency, places."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.models import FlightOption, SearchResult
from app.search import SearchService
from app.travel import DestinationCatalog
from integrations.currency import CurrencyClient
from integrations.flights import FlightsClient
from integrations.hotels import HotelsClient
from integrations.maps import MapsClient
from integrations.places import PlacesClient
from integrations.weather import WeatherClient


class TravelTools:
    """Thin wrapper around isolated integrations."""

    def __init__(self):
        self.catalog = DestinationCatalog()
        self.places = PlacesClient()
        self.maps = MapsClient()
        self.flights = FlightsClient()
        self.hotels = HotelsClient()
        self.weather = WeatherClient()
        self.currency = CurrencyClient()
        self.search_service = SearchService(self.places)

    def destination_profile(self, destination: str | None) -> dict[str, Any] | None:
        return self.catalog.find(destination)

    def search(self, query: str, category: str | None = None, destination: str | None = None) -> list[SearchResult]:
        return self.search_service.search(query, category=category, destination=destination)

    def flight_options(
        self,
        origin: str | None,
        destination: str,
        depart_date: date | None,
        return_date: date | None,
        travelers: int,
    ) -> list[FlightOption]:
        return self.flights.search_round_trip(origin, destination, depart_date, return_date, travelers=travelers)
