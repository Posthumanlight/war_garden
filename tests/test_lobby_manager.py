from __future__ import annotations

import pytest

from db.terminated_games import get_archived_session, list_archived_session_ids, reset_archived_terminated_games_for_tests
from middleware import GameManager, LobbyManager, LobbyManagerError, get_lobby_manager, reset_lobby_manager_for_tests


def setup_function() -> None:
    reset_lobby_manager_for_tests()
    reset_archived_terminated_games_for_tests()


def test_singleton_accessor_returns_same_app_instance() -> None:
    first = get_lobby_manager()
    second = get_lobby_manager()

    assert first is second


def test_isolated_lobby_manager_launches_game_managers_with_deterministic_ids() -> None:
    lobby = LobbyManager()

    first = lobby.launch_game(seed=1)
    second = lobby.launch_game(seed=2)

    assert isinstance(first, GameManager)
    assert str(first.session_id) == "session-1"
    assert str(second.session_id) == "session-2"
    assert lobby.list_games() == (first, second)


def test_duplicate_explicit_session_id_raises() -> None:
    lobby = LobbyManager()
    lobby.launch_game(seed=1, session_id="dupe")

    with pytest.raises(LobbyManagerError, match="already exists"):
        lobby.launch_game(seed=2, session_id="dupe")


def test_unknown_lookup_raises() -> None:
    lobby = LobbyManager()

    with pytest.raises(LobbyManagerError, match="Unknown session"):
        lobby.get_game("missing")


def test_terminate_game_removes_active_game_and_archives_final_snapshot() -> None:
    lobby = LobbyManager()
    game = lobby.launch_game(seed=3)
    game.add_player("Alice")

    terminated = lobby.terminate_game(str(game.session_id))

    assert terminated is game
    assert not lobby.has_game(str(game.session_id))
    assert list_archived_session_ids() == (str(game.session_id),)
    archived = get_archived_session(str(game.session_id))
    assert archived is not None
    assert archived.snapshot_metadata["player_count"] == 1

