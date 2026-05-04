from __future__ import annotations

from dataclasses import dataclass, field

from game.cards.cards import CardInstance
from game.engine.ids import CardInstanceId


MAX_BOARD_SIZE = 7


@dataclass(slots=True)
class Board:
    """Left-to-right creature board owned by one player."""

    cards: list[CardInstance] = field(default_factory=list)
    max_size: int = MAX_BOARD_SIZE

    def __len__(self) -> int:
        return len(self.cards)

    def add(self, card: CardInstance, position: int | None = None) -> None:
        if not card.is_creature:
            raise TypeError("Only creature cards can be placed on the board.")
        if len(self.cards) >= self.max_size:
            raise ValueError("Board is full.")

        insert_at = len(self.cards) if position is None else position
        if insert_at < 0 or insert_at > len(self.cards):
            raise IndexError("Board position is out of range.")

        card.move_to("board")
        self.cards.insert(insert_at, card)

    def remove(self, instance_id: CardInstanceId) -> CardInstance:
        for index, card in enumerate(self.cards):
            if card.instance_id == instance_id:
                return self.cards.pop(index)
        raise KeyError(f"Card instance {instance_id!s} is not on this board.")

    def living_cards(self) -> list[CardInstance]:
        return [card for card in self.cards if card.is_alive]

    def living_indices(self) -> list[int]:
        return [index for index, card in enumerate(self.cards) if card.is_alive]

    def get(self, instance_id: CardInstanceId) -> CardInstance:
        for card in self.cards:
            if card.instance_id == instance_id:
                return card
        raise KeyError(f"Card instance {instance_id!s} is not on this board.")


@dataclass(slots=True)
class Graveyard:
    """Destroyed, discarded, or consumed card instances."""

    cards: list[CardInstance] = field(default_factory=list)

    def add(self, card: CardInstance) -> None:
        card.move_to("graveyard")
        self.cards.append(card)

    def __len__(self) -> int:
        return len(self.cards)

