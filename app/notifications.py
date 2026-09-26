"""Reminders, alerts and travel updates."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.database import Database, database
from app.models import Notification, TripPlan


class NotificationService:
    def __init__(self, db: Database | None = None):
        self.db = db or database
        self.db.initialize()

    def generate_trip_reminders(self, trip: TripPlan) -> list[Notification]:
        reminders: list[Notification] = []
        if trip.itinerary.start_date:
            start_dt = datetime.combine(trip.itinerary.start_date, datetime.min.time())
            reminders.append(
                Notification(
                    user_id=trip.user_id,
                    trip_id=trip.id,
                    title="Verify live travel details",
                    message="Re-check flights, hotel availability, attraction hours, visas and weather before booking.",
                    trigger_at=start_dt - timedelta(days=21),
                )
            )
            reminders.append(
                Notification(
                    user_id=trip.user_id,
                    trip_id=trip.id,
                    title="Pack and download offline maps",
                    message="Download maps, translation packs, tickets and emergency contacts.",
                    trigger_at=start_dt - timedelta(days=3),
                )
            )
        else:
            reminders.append(
                Notification(
                    user_id=trip.user_id,
                    trip_id=trip.id,
                    title="Add dates for better reminders",
                    message="Trip dates are not set, so reminders are generic. Add dates to schedule precise alerts.",
                    trigger_at=None,
                )
            )
        for reminder in reminders:
            self.db.save_notification(reminder)
        return reminders

    def alert_weather_change(self, trip: TripPlan, day_number: int, message: str) -> Notification:
        note = Notification(
            user_id=trip.user_id,
            trip_id=trip.id,
            title=f"Weather update for day {day_number}",
            message=message,
            trigger_at=None,
        )
        self.db.save_notification(note)
        return note
