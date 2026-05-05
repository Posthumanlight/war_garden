from __future__ import annotations

import pytest

from game.cards import load_card_catalog
from game.engine.events import EventLog
from game.engine.ids import CardInstanceId, IdFactory, SessionId
from game.engine.rng import RngContext
from game.engine.shop import PlayerEconomy, ShopActionError
from game.session import GameSession, ShopManager, StateManager


def test_shop_phase_start_gives_active_players_gold_and_offer() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    player = session.state_manager.add_player("Alice")

    session.shop_manager.start_shop_phase(_context(session.state_manager))

    assert session.shop_manager.economies[player.player_id].gold == 10
    assert len(session.shop_manager.offers[player.player_id]) == 6


def test_defeated_players_do_not_receive_gold_or_offers() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    defeated = session.state_manager.add_player("Defeated")
    session.state_manager.mark_defeated(defeated.player_id)

    session.shop_manager.start_shop_phase(_context(session.state_manager))

    assert defeated.player_id not in session.shop_manager.economies
    assert defeated.player_id not in session.shop_manager.offers


def test_offer_generation_is_deterministic_for_same_seed() -> None:
    first = GameSession(seed=3, session_id=SessionId("session"))
    second = GameSession(seed=3, session_id=SessionId("session"))
    first_player = first.state_manager.add_player("Alice")
    second_player = second.state_manager.add_player("Alice")

    first.shop_manager.start_shop_phase(_context(first.state_manager))
    second.shop_manager.start_shop_phase(_context(second.state_manager))

    first_offer = first.shop_manager.offers[first_player.player_id]
    second_offer = second.shop_manager.offers[second_player.player_id]
    assert [card.definition.card_id for card in first_offer.cards] == [
        card.definition.card_id for card in second_offer.cards
    ]
    assert [card.instance_id for card in first_offer.cards] == [card.instance_id for card in second_offer.cards]


def test_initial_offers_only_contain_tier_one_shop_instances() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    player = session.state_manager.add_player("Alice")

    session.shop_manager.start_shop_phase(_context(session.state_manager))

    offer = session.shop_manager.offers[player.player_id]
    assert {card.definition.tier for card in offer.cards} == {1}
    assert {card.zone for card in offer.cards} == {"shop"}
    assert {card.owner_id for card in offer.cards} == {player.player_id}


def test_buy_costs_gold_moves_card_to_hand_and_removes_from_offer() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    player = session.state_manager.add_player("Alice")
    session.shop_manager.start_shop_phase(_context(session.state_manager))
    offer = session.shop_manager.offers[player.player_id]
    card = offer.cards[0]

    bought = session.shop_manager.buy(player, 0)

    assert bought is card
    assert session.shop_manager.economies[player.player_id].gold == 7
    assert bought in player.hand.cards
    assert bought.zone == "hand"
    assert len(offer) == 5


def test_buy_with_insufficient_gold_raises() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    player = session.state_manager.add_player("Alice")
    session.shop_manager.start_shop_phase(_context(session.state_manager))
    session.shop_manager.economies[player.player_id].gold = 2

    with pytest.raises(ValueError, match="Not enough gold"):
        session.shop_manager.buy(player, 0)


def test_sell_from_hand_refunds_gold_and_moves_to_graveyard() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    player = session.state_manager.add_player("Alice")
    session.shop_manager.start_shop_phase(_context(session.state_manager))
    card = session.shop_manager.buy(player, 0)

    sold = session.shop_manager.sell_from_hand(player, card.instance_id)

    assert sold is card
    assert session.shop_manager.economies[player.player_id].gold == 8
    assert card not in player.hand.cards
    assert card in player.graveyard.cards
    assert card.zone == "graveyard"


def test_sell_from_board_refunds_gold_and_moves_to_graveyard() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    player = session.state_manager.add_player("Alice")
    session.shop_manager.start_shop_phase(_context(session.state_manager))
    card = session.shop_manager.buy(player, 0)
    player.hand.remove(card.instance_id)
    player.board.add(card)

    sold = session.shop_manager.sell_from_board(player, card.instance_id)

    assert sold is card
    assert session.shop_manager.economies[player.player_id].gold == 8
    assert card not in player.board.cards
    assert card in player.graveyard.cards


def test_selling_another_players_card_raises() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))
    player = session.state_manager.add_player("Alice")
    other_player = session.state_manager.add_player("Bob")
    session.shop_manager.start_shop_phase(_context(session.state_manager))
    other_card = session.shop_manager.buy(other_player, 0)
    player.hand.add(other_card)

    with pytest.raises(ShopActionError, match="another player"):
        session.shop_manager.sell_from_hand(player, other_card.instance_id)


def test_no_manual_refresh_api_exists() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))

    assert not hasattr(session.shop_manager, "refresh_shop")


def test_player_economy_refresh_spend_and_gain() -> None:
    economy = PlayerEconomy()

    economy.start_shop_round()
    economy.spend(3)
    economy.gain(1)

    assert economy.gold == 8


def _context(state_manager: StateManager):
    from game.session.state_manager import PhaseContext

    return PhaseContext(state_manager=state_manager)
