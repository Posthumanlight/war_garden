from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from game.cards.catalog import CardCatalog
from game.engine.events import EngineEvent
from game.engine.ids import IdFactory, PlayerId
from game.engine.rng import RngContext
from game.engine.shop import CardPool, PlayerEconomy, ShopCardActions, ShopOffer
from game.players.player import Player
from game.session.state_manager import PhaseContext


@dataclass(slots=True)
class ShopManager:
    event_recorder: Callable[[str, dict[str, Any]], EngineEvent | None]
    card_catalog: CardCatalog | None = None
    rng: RngContext | None = None
    id_factory: IdFactory | None = None
    economies: dict[PlayerId, PlayerEconomy] = field(default_factory=dict)
    offers: dict[PlayerId, ShopOffer] = field(default_factory=dict)
    card_pool: CardPool | None = field(init=False, default=None)
    actions: ShopCardActions = field(init=False)

    def __post_init__(self) -> None:
        if self.card_catalog is not None and self.rng is not None and self.id_factory is not None:
            self.card_pool = CardPool(
                card_catalog=self.card_catalog,
                rng=self.rng,
                id_factory=self.id_factory,
            )
        self.actions = ShopCardActions(
            economies=self.economies,
            offers=self.offers,
            event_recorder=self.event_recorder,
        )

    def start_shop_phase(self, context: PhaseContext) -> None:
        self.event_recorder(
            "shop.phase.started",
            {
                "round_number": context.round_number,
                "turn_number": context.turn_number,
            },
        )
        for player in context.state_manager.active_players():
            self.start_player_shop_round(player)

    def end_shop_phase(self, context: PhaseContext) -> None:
        self.event_recorder(
            "shop.phase.ended",
            {
                "round_number": context.round_number,
                "turn_number": context.turn_number,
            },
        )

    def start_player_shop_round(self, player: Player) -> None:
        economy = self.economies.setdefault(player.player_id, PlayerEconomy())
        economy.start_shop_round()
        self.event_recorder(
            "shop.economy.refreshed",
            {
                "player_id": player.player_id,
                "gold": economy.gold,
                "gold_per_round": economy.gold_per_round,
            },
        )
        offer = self._card_pool().create_offer(player.player_id)
        self.offers[player.player_id] = offer
        self.event_recorder(
            "shop.offer.refreshed",
            {
                "player_id": player.player_id,
                "instance_ids": tuple(card.instance_id for card in offer.cards),
                "card_ids": tuple(card.definition.card_id for card in offer.cards),
            },
        )

    def buy(self, player: Player, offer_index: int):
        return self.actions.buy(player, offer_index)

    def sell_from_hand(self, player: Player, instance_id):
        return self.actions.sell_from_hand(player, instance_id)

    def sell_from_board(self, player: Player, instance_id):
        return self.actions.sell_from_board(player, instance_id)

    def create_phase_node(self) -> ShopPhaseNode:
        return ShopPhaseNode(shop_manager=self)

    def _card_pool(self) -> CardPool:
        if self.card_pool is None:
            raise ValueError("ShopManager requires card_catalog, rng, and id_factory to create offers.")
        return self.card_pool


@dataclass(slots=True)
class ShopPhaseNode:
    shop_manager: ShopManager
    node_id: str = "shop"

    def enter(self, context: PhaseContext) -> None:
        self.shop_manager.start_shop_phase(context)

    def execute(self, context: PhaseContext) -> None:
        return None

    def exit(self, context: PhaseContext) -> None:
        self.shop_manager.end_shop_phase(context)
