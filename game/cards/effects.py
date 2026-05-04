from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class CardEffect(Protocol):
    """Marker protocol for future Python-backed card effects."""

    key: str


@dataclass(slots=True)
class EffectRegistry:
    _effects: dict[str, CardEffect] = field(default_factory=dict)

    def register(self, key: str, effect: CardEffect) -> None:
        if not key:
            raise ValueError("Effect key cannot be empty.")
        if key in self._effects:
            raise ValueError(f"Effect key is already registered: {key}.")
        self._effects[key] = effect

    def has(self, key: str) -> bool:
        return key in self._effects

    def get(self, key: str) -> CardEffect:
        try:
            return self._effects[key]
        except KeyError as exc:
            raise KeyError(f"Unknown effect key: {key}.") from exc

