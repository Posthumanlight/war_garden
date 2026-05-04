from __future__ import annotations

from dataclasses import dataclass, field

from game.cards.cards import CardInstance
from game.engine.rng import RngContext


@dataclass(slots=True)
class Deck:
    """Ordered draw pile."""

    cards: list[CardInstance] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def add_to_bottom(self, card: CardInstance) -> None:
        card.move_to("deck")
        self.cards.append(card)

    def add_to_top(self, card: CardInstance) -> None:
        card.move_to("deck")
        self.cards.insert(0, card)

    def draw(self) -> CardInstance | None:
        if not self.cards:
            return None
        return self.cards.pop(0)

    def shuffle(self, rng: RngContext, *, purpose: str = "deck.shuffle") -> None:
        rng.shuffle(self.cards, purpose=purpose)

