from ai.agent import TravelAgent
from app.database import Database


def test_agent_plans_and_modifies_trip(tmp_path):
    agent = TravelAgent(Database(tmp_path / "agent.sqlite3"))
    response = agent.handle_message(
        "Plan 8 days in Japan under ₹1.5 lakh for two people. We love food, culture and nature.",
        user_id="demo",
    )

    assert response.trip is not None
    assert response.trip.itinerary.destination == "Japan"
    assert len(response.trip.itinerary.days) == 8
    assert "fallback estimates" in response.message.lower()

    modified = agent.handle_message("Make it cheaper.", user_id="demo")
    assert modified.trip is not None
    assert modified.trip.version == 2
    assert modified.trip.itinerary.total_estimated_cost.amount < response.trip.itinerary.total_estimated_cost.amount


def test_agent_asks_only_for_required_planning_info(tmp_path):
    agent = TravelAgent(Database(tmp_path / "agent2.sqlite3"))
    response = agent.handle_message("I love food and nature and have ₹50000", user_id="demo")

    assert response.trip is None
    assert "Where would you like to travel?" in response.questions
    assert "How many days or nights should the trip cover?" in response.questions
