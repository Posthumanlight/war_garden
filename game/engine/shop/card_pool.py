from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from game.cards.catalog import CardCatalog
from game.cards.cards import Card, CardInstance
from game.engine.ids import IdFactory, PlayerId
from game.engine.rng import RngContext


DEFAULT_OFFER_SIZE = 6
DEFAULT_TIER_WEIGHTS: dict[int, int] = {1: 100}


class CardPoolError(ValueError):
    """Raised when the shop card pool cannot produce an offer."""


@dataclass(slots=True)
class ShopOffer:
    player_id: PlayerId
    cards: list[CardInstance] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def get(self, offer_index: int) -> CardInstance:
        try:
            return self.cards[offer_index]
        except IndexError as exc:
            raise CardPoolError(f"Invalid shop offer index: {offer_index}.") from exc

    def remove(self, offer_index: int) -> CardInstance:
        try:
            return self.cards.pop(offer_index)
        except IndexError as exc:
            raise CardPoolError(f"Invalid shop offer index: {offer_index}.") from exc


@dataclass(slots=True)
class CardPool:
    card_catalog: CardCatalog
    rng: RngContext
    id_factory: IdFactory
    offer_size: int = DEFAULT_OFFER_SIZE
    tier_weights: Mapping[int, int] = field(default_factory=lambda: dict(DEFAULT_TIER_WEIGHTS))

    def create_offer(self, player_id: PlayerId) -> ShopOffer:
        if self.offer_size <= 0:
            raise CardPoolError("Offer size must be positive.")

        cards = [
            CardInstance(
                instance_id=self.id_factory.next_card_instance_id(),
                definition=self._select_card_definition(),
                owner_id=player_id,
                zone="shop",
            )
            for _ in range(self.offer_size)
        ]
        return ShopOffer(player_id=player_id, cards=cards)

    def _select_card_definition(self) -> Card:
        tier = self._select_tier()
        eligible_cards = tuple(card for card in self.card_catalog.all() if card.tier == tier)
        if not eligible_cards:
            raise CardPoolError(f"No eligible cards for tier {tier}.")
        if len(eligible_cards) == 1:
            return eligible_cards[0]
        index = self.rng.choice_index(len(eligible_cards), purpose=f"shop.card_pool.card.tier.{tier}")
        return eligible_cards[index]

    def _select_tier(self) -> int:
        positive_weights = tuple((tier, weight) for tier, weight in self.tier_weights.items() if weight > 0)
        if not positive_weights:
            raise CardPoolError("Card pool has no positive tier weights.")
        if len(positive_weights) == 1:
            return positive_weights[0][0]

        total_weight = sum(weight for _, weight in positive_weights)
        roll = self.rng.randint(1, total_weight + 1, purpose="shop.card_pool.tier")
        cumulative = 0
        for tier, weight in positive_weights:
            cumulative += weight
            if roll <= cumulative:
                return tier
        raise CardPoolError("Failed to select a card tier.")

