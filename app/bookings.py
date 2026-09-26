"""Booking records, confirmations, cancellations and receipts."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.database import Database, database
from app.models import Booking, BookingStatus, Money


class BookingService:
    """Record booking intentions without pretending to complete real purchases."""

    def __init__(self, db: Database | None = None):
        self.db = db or database
        self.db.initialize()

    def create_record(
        self,
        user_id: str,
        item_type: str,
        item_name: str,
        amount: Money | None = None,
        trip_id: str | None = None,
        provider: str = "manual/mock",
    ) -> Booking:
        booking = Booking(
            user_id=user_id,
            trip_id=trip_id,
            item_type=item_type,  # type: ignore[arg-type]
            item_name=item_name,
            status=BookingStatus.pending,
            amount=amount or Money(amount=0, currency="INR", note="Amount not provided"),
            confirmation_code=f"MOCK-{uuid4().hex[:8].upper()}",
            provider=provider,
            notes=[
                "This is a local booking record only; no external purchase has been made.",
                "Connect a booking provider integration before issuing real confirmations.",
            ],
        )
        self.db.save_booking(booking)
        return booking

    def confirm_record(self, booking_id: str, user_id: str) -> Booking | None:
        raw = self.db.get_booking(booking_id, user_id=user_id)
        if not raw:
            return None
        booking = Booking.model_validate(raw)
        booking.status = BookingStatus.confirmed
        booking.updated_at = datetime.now(timezone.utc)
        booking.notes.append("Manually marked confirmed in local records; verify provider status separately.")
        self.db.save_booking(booking)
        return booking

    def cancel_record(self, booking_id: str, user_id: str) -> Booking | None:
        raw = self.db.get_booking(booking_id, user_id=user_id)
        if not raw:
            return None
        booking = Booking.model_validate(raw)
        booking.status = BookingStatus.cancelled
        booking.updated_at = datetime.now(timezone.utc)
        booking.notes.append("Cancelled in local records only; contact provider for real cancellations/refunds.")
        self.db.save_booking(booking)
        return booking

    def receipt(self, booking_id: str, user_id: str) -> dict | None:
        raw = self.db.get_booking(booking_id, user_id=user_id)
        if not raw:
            return None
        booking = Booking.model_validate(raw)
        return {
            "booking_id": booking.id,
            "status": booking.status,
            "item": booking.item_name,
            "amount": booking.amount.model_dump(mode="json"),
            "provider": booking.provider,
            "confirmation_code": booking.confirmation_code,
            "important_note": "Receipt is generated from local records and is not proof of an external purchase.",
        }
