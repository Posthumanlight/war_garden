from __future__ import annotations

from dataclasses import dataclass, field

from game.board.board import Board, Graveyard
from game.board.deck import Deck
from game.board.hand import Hand
from game.cards.cards import CardInstance
from game.engine.ids import CardInstanceId, PlayerId
from game.engine.rng import RngContext


@dataclass(slots=True)
class Player:
    """Player-owned combat and card-zone state."""

    player_id: PlayerId
    name: str
    board: Board = field(default_factory=Board)
    hand: Hand = field(default_factory=Hand)
    deck: Deck = field(default_factory=Deck)
    graveyard: Graveyard = field(default_factory=Graveyard)
    _attack_cursor: int = 0

    def draw_card(self) -> CardInstance | None:
        card = self.deck.draw()
        if card is None:
            return None
        self.hand.add(card)
        return card

    def shuffle_deck(self, rng: RngContext) -> None:
        self.deck.shuffle(rng, purpose=f"player.{self.player_id}.deck.shuffle")

    def add_to_hand(self, card: CardInstance) -> None:
        self.hand.add(card)

    def summon_to_board(self, instance_id: CardInstanceId, position: int | None = None) -> CardInstance:
        card = self.hand.remove(instance_id)
        self.board.add(card, position=position)
        return card

    def remove_from_board(self, instance_id: CardInstanceId) -> CardInstance:
        return self.board.remove(instance_id)

    def destroy_on_board(self, instance_id: CardInstanceId) -> CardInstance:
        card = self.remove_from_board(instance_id)
        self.graveyard.add(card)
        return card

    def next_living_attacker(self) -> CardInstance | None:
        living = self.board.living_cards()
        if not living:
            return None

        for offset in range(len(self.board.cards)):
            index = (self._attack_cursor + offset) % len(self.board.cards)
            candidate = self.board.cards[index]
            if candidate.is_alive:
                self._attack_cursor = (index + 1) % len(self.board.cards)
                return candidate
        return None

    def reset_combat_cursor(self) -> None:
        self._attack_cursor = 0

