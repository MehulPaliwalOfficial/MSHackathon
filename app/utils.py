"""Small reusable utilities only."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import re
import unicodedata
from typing import Any

from config import DATA_DIR, settings
from app.models import Money

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_json(filename: str, default: Any | None = None) -> Any:
    path = DATA_DIR / filename
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def model_to_data(value: Any) -> Any:
    """Return JSON-serialisable data for Pydantic models, datetimes and collections."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: model_to_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [model_to_data(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def parse_duration_days(text: str) -> int | None:
    lower = text.lower()
    match = re.search(r"\b(\d{1,2})\s*(?:days?|nights?)\b", lower)
    if match:
        days = int(match.group(1))
        # Common travel phrasing: 7 nights is usually 8 days.
        if "night" in match.group(0):
            return min(days + 1, 90)
        return days
    match = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(?:days?|nights?)\b", lower)
    if match:
        days = NUMBER_WORDS[match.group(1)]
        if "night" in match.group(0):
            return min(days + 1, 90)
        return days
    match = re.search(r"\b(\d+)\s*weeks?\b", lower)
    if match:
        return min(int(match.group(1)) * 7, 90)
    return None


def word_or_number_to_int(value: str) -> int | None:
    value = value.strip().lower()
    if value.isdigit():
        return int(value)
    return NUMBER_WORDS.get(value)


def parse_budget(text: str, default_currency: str | None = None) -> Money | None:
    """Extract a budget amount from natural language.

    The parser intentionally requires either a budget keyword/currency marker or
    an Indian-style magnitude word such as "lakh" so that durations like "8 days"
    are not misread as money.
    """
    default_currency = (default_currency or settings.base_currency).upper()
    original = text
    lower = text.lower().replace(",", "")
    currency_map = {
        "₹": "INR",
        "rs": "INR",
        "rs.": "INR",
        "inr": "INR",
        "$": "USD",
        "usd": "USD",
        "€": "EUR",
        "eur": "EUR",
        "¥": "JPY",
        "jpy": "JPY",
    }
    multipliers = {
        "k": 1_000,
        "thousand": 1_000,
        "lakh": 100_000,
        "lac": 100_000,
        "lakhs": 100_000,
        "lacs": 100_000,
        "crore": 10_000_000,
        "million": 1_000_000,
    }
    keywords = ("budget", "under", "within", "upto", "up to", "less than", "max", "maximum", "around", "approx")
    pattern = re.compile(
        r"(?P<currency>₹|rs\.?|inr|\$|usd|€|eur|¥|jpy)?\s*"
        r"(?P<amount>\d+(?:\.\d+)?)\s*"
        r"(?P<multiplier>k|thousand|lakh|lac|lakhs|lacs|crore|million)?"
    )
    candidates: list[tuple[float, str, str]] = []
    for match in pattern.finditer(lower):
        amount = float(match.group("amount"))
        currency_token = (match.group("currency") or "").replace(".", "")
        multiplier_token = match.group("multiplier") or ""
        context = lower[max(0, match.start() - 25) : min(len(lower), match.end() + 20)]
        has_context = bool(currency_token or multiplier_token or any(k in context for k in keywords))
        if not has_context:
            continue
        if amount < 1 and not multiplier_token:
            continue
        multiplier = multipliers.get(multiplier_token, 1)
        currency = currency_map.get(currency_token, default_currency)
        candidates.append((amount * multiplier, currency, context))
    if not candidates:
        return None
    # Pick the largest contextual amount because phrases often include traveler
    # counts or days alongside the budget.
    amount, currency, _ = max(candidates, key=lambda item: item[0])
    return Money(amount=amount, currency=currency, note=f"Parsed from: {original[:80]}")


def parse_iso_or_slash_date(text: str) -> date | None:
    patterns = [
        r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b",
        r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            if pattern.startswith("\\b(20"):
                year, month, day = map(int, match.groups())
            else:
                day, month, year = map(int, match.groups())
            return date(year, month, day)
        except ValueError:
            return None
    return None


def date_range_from_start(start: date | None, duration_days: int | None) -> tuple[date | None, date | None]:
    if start and duration_days:
        return start, start + timedelta(days=duration_days - 1)
    return start, None


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "item"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def compact_sentence(items: list[str], fallback: str = "") -> str:
    clean = [item for item in items if item]
    if not clean:
        return fallback
    if len(clean) == 1:
        return clean[0]
    return ", ".join(clean[:-1]) + f" and {clean[-1]}"


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normal = item.strip().lower()
        if not normal or normal in seen:
            continue
        seen.add(normal)
        output.append(item.strip())
    return output
