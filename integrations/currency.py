"""Currency conversion connector.

This module deliberately defaults to static fallback rates. Live providers can be
added here without changing the AI or planning logic.
"""
from __future__ import annotations

from app.models import Money

# Approximate static development rates. They are marked as estimates wherever used.
INR_PER_UNIT = {
    "INR": 1.0,
    "USD": 83.0,
    "EUR": 90.0,
    "GBP": 105.0,
    "JPY": 0.56,
    "THB": 2.35,
    "AED": 22.6,
    "IDR": 0.0054,
}


class CurrencyClient:
    def __init__(self, base_currency: str = "INR"):
        self.base_currency = base_currency.upper()

    def convert(self, money: Money, to_currency: str) -> Money:
        to_currency = to_currency.upper()
        from_currency = money.currency.upper()
        if from_currency not in INR_PER_UNIT or to_currency not in INR_PER_UNIT:
            return Money(
                amount=money.amount,
                currency=money.currency,
                note="Currency unavailable in static fallback rates; returned original amount.",
            )
        value_in_inr = money.amount * INR_PER_UNIT[from_currency]
        converted = value_in_inr / INR_PER_UNIT[to_currency]
        return Money(
            amount=round(converted, 2),
            currency=to_currency,
            note="Estimated using static development exchange rates, not live FX.",
        )

    def to_base(self, money: Money) -> Money:
        return self.convert(money, self.base_currency)

    def supported_currencies(self) -> list[str]:
        return sorted(INR_PER_UNIT)
