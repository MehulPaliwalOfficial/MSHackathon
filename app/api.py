"""API endpoints and request/response handling."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from ai.agent import TravelAgent
from app.auth import AuthContext, get_auth_context
from app.bookings import BookingService
from app.database import Database, database
from app.memory import MemoryStore
from app.models import AgentResponse, Booking, Money, TripPlan, UserMemory
from app.search import SearchService
from app.ui import register_ui_routes
from config import settings


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str | None = None
    trip_id: str | None = None


class ModifyTripRequest(BaseModel):
    instruction: str = Field(min_length=1)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    category: str | None = None
    destination: str | None = None
    limit: int = Field(default=10, ge=1, le=30)


class BookingCreateRequest(BaseModel):
    trip_id: str | None = None
    item_type: str = "other"
    item_name: str
    amount: float = 0
    currency: str = "INR"
    provider: str = "manual/mock"


class MemoryFactRequest(BaseModel):
    key: str = Field(min_length=1)
    value: Any


def _user_id(payload_user_id: str | None, auth: AuthContext) -> str:
    return payload_user_id or auth.user_id


def create_app(db: Database | None = None) -> FastAPI:
    db = db or database
    db.initialize()
    agent = TravelAgent(db)
    booking_service = BookingService(db)
    memory_store = MemoryStore(db)
    search_service = SearchService()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Production-ready AI Travel Agent with deterministic fallback integrations.",
    )
    app.state.db = db
    app.state.agent = agent

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.environment,
            "live_apis_enabled": settings.use_live_apis,
            "fallbacks_enabled": True,
        }

    @app.post("/api/chat", response_model=AgentResponse)
    async def chat(payload: ChatRequest, auth: AuthContext = Depends(get_auth_context)) -> AgentResponse:
        user_id = _user_id(payload.user_id, auth)
        return agent.handle_message(payload.message, user_id=user_id, trip_id=payload.trip_id)

    @app.post("/api/trips/plan", response_model=AgentResponse)
    async def plan_trip(payload: ChatRequest, auth: AuthContext = Depends(get_auth_context)) -> AgentResponse:
        user_id = _user_id(payload.user_id, auth)
        return agent.handle_message(payload.message, user_id=user_id)

    @app.post("/api/trips/{trip_id}/modify", response_model=AgentResponse)
    async def modify_trip(trip_id: str, payload: ModifyTripRequest, auth: AuthContext = Depends(get_auth_context)) -> AgentResponse:
        return agent.handle_message(payload.instruction, user_id=auth.user_id, trip_id=trip_id)

    @app.get("/api/trips")
    async def list_trips(auth: AuthContext = Depends(get_auth_context)) -> list[dict[str, Any]]:
        return db.list_trips(auth.user_id)

    @app.get("/api/trips/{trip_id}", response_model=TripPlan)
    async def get_trip(trip_id: str, auth: AuthContext = Depends(get_auth_context)) -> TripPlan:
        raw = db.get_trip(trip_id, user_id=auth.user_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Trip not found")
        return TripPlan.model_validate(raw)

    @app.post("/api/search")
    async def search(payload: SearchRequest, auth: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        del auth  # access is validated by dependency; search itself is user-agnostic
        results = search_service.search(payload.query, category=payload.category, destination=payload.destination, limit=payload.limit)
        return {"results": results, "count": len(results), "live": False, "source_note": "Static fallback search data"}

    @app.get("/api/memory", response_model=UserMemory)
    async def get_memory(auth: AuthContext = Depends(get_auth_context)) -> UserMemory:
        return memory_store.get_profile(auth.user_id)

    @app.post("/api/memory/facts", response_model=UserMemory)
    async def remember_fact(payload: MemoryFactRequest, auth: AuthContext = Depends(get_auth_context)) -> UserMemory:
        return memory_store.remember_fact(auth.user_id, payload.key, payload.value)

    @app.post("/api/bookings", response_model=Booking)
    async def create_booking(payload: BookingCreateRequest, auth: AuthContext = Depends(get_auth_context)) -> Booking:
        return booking_service.create_record(
            user_id=auth.user_id,
            trip_id=payload.trip_id,
            item_type=payload.item_type,
            item_name=payload.item_name,
            amount=Money(amount=payload.amount, currency=payload.currency, note="User-entered amount"),
            provider=payload.provider,
        )

    @app.post("/api/bookings/{booking_id}/confirm", response_model=Booking)
    async def confirm_booking(booking_id: str, auth: AuthContext = Depends(get_auth_context)) -> Booking:
        booking = booking_service.confirm_record(booking_id, auth.user_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return booking

    @app.post("/api/bookings/{booking_id}/cancel", response_model=Booking)
    async def cancel_booking(booking_id: str, auth: AuthContext = Depends(get_auth_context)) -> Booking:
        booking = booking_service.cancel_record(booking_id, auth.user_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return booking

    @app.get("/api/bookings/{booking_id}/receipt")
    async def booking_receipt(booking_id: str, auth: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        receipt = booking_service.receipt(booking_id, auth.user_id)
        if not receipt:
            raise HTTPException(status_code=404, detail="Booking not found")
        return receipt

    register_ui_routes(app)
    return app
