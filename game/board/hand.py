from __future__ import annotations

from dataclasses import dataclass, field

from game.cards.cards import CardInstance
from game.engine.ids import CardInstanceId


@dataclass(slots=True)
class Hand:
    """Cards currently held by a player."""

    cards: list[CardInstance] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def add(self, card: CardInstance) -> None:
        card.move_to("hand")
        self.cards.append(card)

    def remove(self, instance_id: CardInstanceId) -> CardInstance:
        for index, card in enumerate(self.cards):
            if card.instance_id == instance_id:
                return self.cards.pop(index)
        raise KeyError(f"Card instance {instance_id!s} is not in this hand.")

