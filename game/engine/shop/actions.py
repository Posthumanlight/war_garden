from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from game.cards.cards import CardInstance
from game.engine.events import EngineEvent
from game.engine.ids import CardInstanceId, PlayerId
from game.engine.shop.card_pool import ShopOffer
from game.engine.shop.economy import PlayerEconomy
from game.players.player import Player


SHOP_BUY_COST = 3
SHOP_SELL_REFUND = 1


class ShopActionError(ValueError):
    """Raised when a shop action is invalid."""


@dataclass(slots=True)
class ShopCardActions:
    economies: dict[PlayerId, PlayerEconomy]
    offers: dict[PlayerId, ShopOffer]
    event_recorder: Callable[[str, dict[str, Any]], EngineEvent | None]
    buy_cost: int = SHOP_BUY_COST
    sell_refund: int = SHOP_SELL_REFUND

    def buy(self, player: Player, offer_index: int) -> CardInstance:
        economy = self._economy_for(player)
        offer = self._offer_for(player)
        card = offer.get(offer_index)
        economy.spend(self.buy_cost)
        self._record(
            "shop.economy.spent",
            {
                "player_id": player.player_id,
                "amount": self.buy_cost,
                "gold": economy.gold,
            },
        )
        removed_card = offer.remove(offer_index)
        self._record(
            "shop.offer.card.removed",
            {
                "player_id": player.player_id,
                "instance_id": removed_card.instance_id,
                "offer_index": offer_index,
            },
        )
        player.hand.add(removed_card)
        self._record(
            "shop.card.bought",
            {
                "player_id": player.player_id,
                "instance_id": removed_card.instance_id,
                "card_id": removed_card.definition.card_id,
                "cost": self.buy_cost,
            },
        )
        return removed_card

    def sell_from_hand(self, player: Player, instance_id: CardInstanceId) -> CardInstance:
        card = self._card_from_player_hand(player, instance_id)
        removed_card = player.hand.remove(instance_id)
        return self._sell(player, removed_card, from_zone="hand")

    def sell_from_board(self, player: Player, instance_id: CardInstanceId) -> CardInstance:
        card = player.board.get(instance_id)
        if card.owner_id != player.player_id:
            raise ShopActionError("Cannot sell a card owned by another player.")
        removed_card = player.board.remove(instance_id)
        return self._sell(player, removed_card, from_zone="board")

    def _sell(self, player: Player, card: CardInstance, *, from_zone: str) -> CardInstance:
        economy = self._economy_for(player)
        player.graveyard.add(card)
        economy.gain(self.sell_refund)
        self._record(
            "shop.economy.gained",
            {
                "player_id": player.player_id,
                "amount": self.sell_refund,
                "gold": economy.gold,
            },
        )
        self._record(
            "shop.card.sold",
            {
                "player_id": player.player_id,
                "instance_id": card.instance_id,
                "card_id": card.definition.card_id,
                "from_zone": from_zone,
                "refund": self.sell_refund,
            },
        )
        return card

    def _card_from_player_hand(self, player: Player, instance_id: CardInstanceId) -> CardInstance:
        for card in player.hand.cards:
            if card.instance_id == instance_id:
                if card.owner_id != player.player_id:
                    raise ShopActionError("Cannot sell a card owned by another player.")
                return card
        raise ShopActionError(f"Card instance {instance_id!s} is not in this player's hand.")

    def _economy_for(self, player: Player) -> PlayerEconomy:
        try:
            return self.economies[player.player_id]
        except KeyError as exc:
            raise ShopActionError(f"Player has no economy state: {player.player_id}.") from exc

    def _offer_for(self, player: Player) -> ShopOffer:
        try:
            return self.offers[player.player_id]
        except KeyError as exc:
            raise ShopActionError(f"Player has no active shop offer: {player.player_id}.") from exc

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        self.event_recorder(event_type, payload)

