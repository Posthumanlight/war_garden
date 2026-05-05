from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from db.terminated_games import archive_terminated_game
from game.engine.ids import SessionId
from middleware.game_manager import GameManager


class LobbyManagerError(ValueError):
    """Raised when a lobby lifecycle operation is invalid."""


@dataclass(slots=True)
class LobbyManager:
    """Application-level lifecycle owner for active games."""

    active_games: dict[SessionId, GameManager] = field(default_factory=dict)
    _next_session_number: int = 1
    _catalog_game: GameManager | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def launch_game(self, *, seed: int, session_id: str | None = None) -> GameManager:
        with self._lock:
            new_session_id = SessionId(session_id or self._next_session_id())
            if new_session_id in self.active_games:
                raise LobbyManagerError(f"Session already exists: {new_session_id}.")
            game = GameManager.create(seed=seed, session_id=new_session_id)
            self.active_games[new_session_id] = game
            return game

    def get_game(self, session_id: str) -> GameManager:
        normalized_id = SessionId(session_id)
        try:
            return self.active_games[normalized_id]
        except KeyError as exc:
            raise LobbyManagerError(f"Unknown session: {session_id}.") from exc

    def list_games(self) -> tuple[GameManager, ...]:
        return tuple(self.active_games.values())

    def terminate_game(self, session_id: str) -> GameManager:
        normalized_id = SessionId(session_id)
        with self._lock:
            try:
                game = self.active_games.pop(normalized_id)
            except KeyError as exc:
                raise LobbyManagerError(f"Unknown session: {session_id}.") from exc
            archive_terminated_game(game)
            return game

    def has_game(self, session_id: str) -> bool:
        return SessionId(session_id) in self.active_games

    def catalog_game(self) -> GameManager:
        if self._catalog_game is None:
            self._catalog_game = GameManager.create(seed=0, session_id=SessionId("catalog-preview"))
        return self._catalog_game

    def _next_session_id(self) -> str:
        session_id = f"session-{self._next_session_number}"
        self._next_session_number += 1
        return session_id


_LOBBY_MANAGER: LobbyManager | None = None


def get_lobby_manager() -> LobbyManager:
    global _LOBBY_MANAGER
    if _LOBBY_MANAGER is None:
        _LOBBY_MANAGER = LobbyManager()
    return _LOBBY_MANAGER


def reset_lobby_manager_for_tests() -> None:
    global _LOBBY_MANAGER
    _LOBBY_MANAGER = None
