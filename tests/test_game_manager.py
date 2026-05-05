from __future__ import annotations

import pytest

from game.engine.ids import SessionId
from middleware import GameManager, GameManagerError


def test_game_manager_wraps_one_session_and_exposes_catalog_events_and_rng() -> None:
    game = GameManager.create(seed=5, session_id=SessionId("session"))

    knight = game.get_catalog_card("creature.knight")

    assert game.session.seed == 5
    assert knight.name == "Knight"
    assert game.list_catalog_cards()
    assert game.event_log().events == []
    assert game.snapshot_metadata()["rng_algorithm"] == "PCG64DXSM"
    assert game.export_rng_state()["bit_generator"] == "PCG64DXSM"


def test_player_shop_summon_sell_and_combat_flow_goes_through_game_manager() -> None:
    game = GameManager.create(seed=7, session_id=SessionId("session"))
    alice = game.add_player("Alice")
    bob = game.add_player("Bob")

    game.start_shop()
    alice_card = game.buy_shop_card(str(alice.player_id), 0)
    bob_card = game.buy_shop_card(str(bob.player_id), 0)
    game.summon_card(str(alice.player_id), str(alice_card.instance_id))
    game.summon_card(str(bob.player_id), str(bob_card.instance_id))

    result = game.resolve_combat_round()

    assert result.pair_results
    assert game.event_log().events


def test_sell_from_hand_and_board_goes_through_game_manager() -> None:
    game = GameManager.create(seed=8, session_id=SessionId("session"))
    player = game.add_player("Alice")

    game.start_shop()
    hand_card = game.buy_shop_card(str(player.player_id), 0)
    game.sell_from_hand(str(player.player_id), str(hand_card.instance_id))
    board_card = game.buy_shop_card(str(player.player_id), 0)
    game.summon_card(str(player.player_id), str(board_card.instance_id))
    game.sell_from_board(str(player.player_id), str(board_card.instance_id))

    assert len(player.graveyard.cards) == 2


def test_phase_actions_go_through_game_manager() -> None:
    game = GameManager.create(seed=9, session_id=SessionId("session"))

    game.transition_phase("shop")
    result = game.advance_phase()

    assert result.executed_node_id == "shop"
    assert result.next_node_id == "combat"


def test_unknown_player_and_card_errors_are_centralized() -> None:
    game = GameManager.create(seed=10, session_id=SessionId("session"))

    with pytest.raises(GameManagerError, match="Unknown player"):
        game.player("missing")

    with pytest.raises(GameManagerError, match="Unknown card id"):
        game.get_catalog_card("missing")

