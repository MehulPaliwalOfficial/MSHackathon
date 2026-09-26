from app.travel import TravelRequestExtractor, validate_request


def test_extracts_japan_budget_travelers_and_interests():
    extractor = TravelRequestExtractor()
    request = extractor.extract(
        "Plan 8 days in Japan under ₹1.5 lakh for two people. We love food, culture and nature.",
        user_id="test",
    )

    assert request.destination == "Japan"
    assert request.duration_days == 8
    assert request.travelers.total == 2
    assert request.budget is not None
    assert request.budget.amount == 150000
    assert {"food", "culture", "nature"}.issubset(set(request.preferences.interests))
    assert validate_request(request) == []


def test_missing_destination_and_duration_are_required():
    extractor = TravelRequestExtractor()
    request = extractor.extract("I want a cheap trip with beaches", user_id="test")
    questions = validate_request(request)
    assert "Where would you like to travel?" in questions
    assert "How many days or nights should the trip cover?" in questions
