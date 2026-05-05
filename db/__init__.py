"""Persistence stubs for future database-backed game state."""

from db.terminated_games import (
    ArchivedTerminatedGame,
    archive_terminated_game,
    get_archived_session,
    list_archived_session_ids,
    reset_archived_terminated_games_for_tests,
)

__all__ = [
    "ArchivedTerminatedGame",
    "archive_terminated_game",
    "get_archived_session",
    "list_archived_session_ids",
    "reset_archived_terminated_games_for_tests",
]
