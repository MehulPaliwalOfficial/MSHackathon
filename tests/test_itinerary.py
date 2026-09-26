from ai.planner import TravelPlanner
from app.travel import TravelRequestExtractor


def test_itinerary_builds_exact_day_count_and_budget():
    request = TravelRequestExtractor().extract(
        "Plan 8 days in Japan from Delhi under ₹1.5 lakh for two people. We love food, culture and nature.",
        user_id="test",
    )
    trip = TravelPlanner().create_plan(request)

    assert len(trip.itinerary.days) == 8
    assert trip.itinerary.duration_days == 8
    assert trip.itinerary.total_estimated_cost.amount > 0
    assert trip.itinerary.days[0].activities
    assert trip.flights, "Origin should enable fallback flight estimates"


def test_itinerary_modification_removes_museums():
    request = TravelRequestExtractor().extract("Plan 5 days in France for two people with museums and food", user_id="test")
    trip = TravelPlanner().create_plan(request)
    updated = TravelPlanner().modify_plan(trip, "Remove museums")

    assert updated.version == 2
    for day in updated.itinerary.days:
        assert all("museum" not in (activity.category + activity.name).lower() for activity in day.activities)
