# AI Travel Agent

A simple, modular, production-ready **AI Travel Agent** built with Python and FastAPI. It understands natural-language travel requests, extracts requirements, uses user memory, researches static/fallback travel data, compares options, creates realistic day-by-day itineraries, validates budgets, explains assumptions, and supports natural-language trip modifications.

The app is fully functional without external APIs. Integrations are isolated and default to clean deterministic fallbacks, so development and tests can run offline. Live providers can be added inside `integrations/` without hardcoding provider logic into the AI agent.

## Features

- Natural-language trip planning, e.g.:
  - `Plan 8 days in Japan under ₹1.5 lakh for two people. We love food, culture and nature.`
- Extracts and considers:
  - destination, dates/duration, origin, travelers, budget, interests, travel style, accommodation, transport, food, accessibility, constraints/preferences
- Research → compare → plan → validate → explain → adapt pipeline
- Realistic day-by-day itinerary structure with:
  - city routing, meals, rest buffers, travel-time estimates, opening-hour notes, weather fallback, budget estimates
- Natural-language modifications:
  - `Make it cheaper.`
  - `Remove museums.`
  - `Add two beach days.`
  - `It is going to rain tomorrow; change the plan.`
- User memory for preferences and trip history
- Local booking records and receipts without pretending to complete real purchases
- Complete web UI served from `/`
- API endpoints under `/api/*`
- SQLite persistence
- Tests for AI, travel parsing, itinerary building and API

## Important safety rule

The system **never invents live prices, availability, weather, bookings or search results**. Fallback data is clearly marked as estimates. Real booking or live-search behavior should be implemented only through provider-specific connectors in `integrations/`.

## Project structure

```text
AI-TRAVEL-AGENT/
├── main.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── app/
│   ├── api.py
│   ├── ui.py
│   ├── auth.py
│   ├── models.py
│   ├── database.py
│   ├── memory.py
│   ├── travel.py
│   ├── itinerary.py
│   ├── recommendations.py
│   ├── search.py
│   ├── bookings.py
│   ├── notifications.py
│   └── utils.py
│
├── ai/
│   ├── agent.py
│   ├── prompts.py
│   ├── tools.py
│   ├── planner.py
│   └── personalization.py
│
├── integrations/
│   ├── maps.py
│   ├── flights.py
│   ├── hotels.py
│   ├── weather.py
│   ├── places.py
│   └── currency.py
│
├── data/
│   ├── destinations.json
│   ├── countries.json
│   ├── airports.json
│   └── sample_data.json
│
└── tests/
    ├── test_ai.py
    ├── test_travel.py
    ├── test_itinerary.py
    └── test_api.py
```

## Quick start

### Recommended PC method

This project is now installable in **editable mode**, which fixes the common Windows/VS Code/PyCharm import errors.

```bash
cd AI-TRAVEL-AGENT
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python run.py
```

After `python -m pip install -e .`, imports like `from app.travel import ...` and `from ai.agent import ...` work even when your IDE is strict about package paths.

### Windows one-click/helper method

From Command Prompt or by double-clicking:

```bat
start_windows.bat
```

### Linux/macOS helper method

```bash
./start_unix.sh
```

`python main.py` also works, but `python run.py` or the installed command below is safer for local PC use:

```bash
ai-travel-agent
```

If your editor still shows import errors, make sure its selected interpreter is the same virtual environment where you ran `python -m pip install -e .`.


```bash
cd AI-TRAVEL-AGENT
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

`python main.py` also works, but `python run.py` is the most PC/IDE-friendly launcher.

If your editor shows import errors, make sure you open the `AI-TRAVEL-AGENT` folder itself as the workspace root, not its parent folder. The project includes `__init__.py` package files and `pytest.ini` with `pythonpath = .` so imports work consistently in VS Code, PyCharm and pytest.

Open:

- UI: <http://localhost:8000/>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

## Environment

Copy `.env.example` to `.env` and edit as needed.

```env
APP_NAME="AI Travel Agent"
ENVIRONMENT=development
SECRET_KEY=change-me-in-production
DATABASE_URL=sqlite:///./travel_agent.sqlite3
BASE_CURRENCY=INR
ALLOW_ANONYMOUS=true
API_KEY=
USE_LIVE_APIS=false
```

External API keys are optional. The current implementation uses deterministic fallback connectors. To add live data, implement it inside the relevant file in `integrations/` and keep the return models unchanged.

## API examples

### Plan a trip

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo" \
  -d '{"message":"Plan 8 days in Japan under ₹1.5 lakh for two people. We love food, culture and nature."}'
```

### Modify the latest trip

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo" \
  -d '{"message":"Make it cheaper."}'
```

### Modify a specific trip

```bash
curl -X POST http://localhost:8000/api/trips/TRIP_ID/modify \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo" \
  -d '{"instruction":"Remove museums."}'
```

### Search fallback travel data

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"food market", "destination":"Japan", "category":"activity"}'
```

## Running tests

```bash
pytest
```

## Development notes

- `ai/agent.py` is the central orchestrator.
- `ai/planner.py` converts typed requirements into a complete `TripPlan`.
- `app/travel.py` contains deterministic extraction and budget validation.
- `app/itinerary.py` builds and modifies day-by-day plans.
- `integrations/` contains all provider-facing logic and fallback connectors.
- `data/` contains curated development data.
- `app/database.py` persists JSON-serialised domain models in SQLite for simplicity and extensibility.

## Extending with live APIs

1. Add provider code only in the relevant `integrations/*.py` file.
2. Keep return types from `app.models` unchanged.
3. Mark responses with accurate `source` and `availability_live` / `is_live` flags.
4. Keep fallback behavior for tests and local development.
5. Never return unverified prices, availability, weather or bookings as live facts.
