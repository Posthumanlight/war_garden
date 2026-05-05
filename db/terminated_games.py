from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ArchivedTerminatedGame:
    session_id: str
    snapshot_metadata: dict[str, Any]


_ARCHIVED_TERMINATED_GAMES: dict[str, ArchivedTerminatedGame] = {}


def archive_terminated_game(game) -> None:
    session_id = str(game.session_id)
    _ARCHIVED_TERMINATED_GAMES[session_id] = ArchivedTerminatedGame(
        session_id=session_id,
        snapshot_metadata=dict(game.snapshot_metadata()),
    )


def list_archived_session_ids() -> tuple[str, ...]:
    return tuple(_ARCHIVED_TERMINATED_GAMES)


def get_archived_session(session_id: str) -> ArchivedTerminatedGame | None:
    return _ARCHIVED_TERMINATED_GAMES.get(session_id)


def reset_archived_terminated_games_for_tests() -> None:
    _ARCHIVED_TERMINATED_GAMES.clear()
