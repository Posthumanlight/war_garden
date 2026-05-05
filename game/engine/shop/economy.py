from __future__ import annotations

from dataclasses import dataclass


DEFAULT_GOLD_PER_ROUND = 10


class PlayerEconomyError(ValueError):
    """Raised when a player's shop economy cannot perform an action."""


@dataclass(slots=True)
class PlayerEconomy:
    gold: int = 0
    gold_per_round: int = DEFAULT_GOLD_PER_ROUND

    def __post_init__(self) -> None:
        if self.gold < 0:
            raise PlayerEconomyError("Gold cannot be negative.")
        if self.gold_per_round < 0:
            raise PlayerEconomyError("Gold per round cannot be negative.")

    def start_shop_round(self) -> None:
        self.gold = self.gold_per_round

    def spend(self, amount: int) -> None:
        if amount < 0:
            raise PlayerEconomyError("Spend amount cannot be negative.")
        if self.gold < amount:
            raise PlayerEconomyError("Not enough gold.")
        self.gold -= amount

    def gain(self, amount: int) -> None:
        if amount < 0:
            raise PlayerEconomyError("Gain amount cannot be negative.")
        self.gold += amount

