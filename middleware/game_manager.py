from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from game.cards.cards import Card, CardInstance
from game.engine.events import EventLog
from game.engine.ids import CardId, CardInstanceId, PlayerId, SessionId
from game.session import GameSession
from game.session.combat_manager import CombatRoundResult
from game.session.state_manager import PhaseContext, PhaseTransitionResult
from game.players.player import Player


class GameManagerError(ValueError):
    """Raised when an application-level game action is invalid."""


@dataclass(slots=True)
class GameManager:
    """Per-session application boundary around an input-agnostic GameSession."""

    session: GameSession

    @classmethod
    def create(cls, *, seed: int, session_id: SessionId) -> GameManager:
        return cls(session=GameSession(seed=seed, session_id=session_id))

    @property
    def session_id(self) -> SessionId:
        return self.session.session_id

    @property
    def seed(self) -> int:
        return self.session.seed

    def snapshot_metadata(self) -> dict[str, Any]:
        return self.session.snapshot_metadata()

    def list_catalog_cards(self) -> tuple[Card, ...]:
        return self.session.card_catalog.all()

    def get_catalog_card(self, card_id: str) -> Card:
        try:
            return self.session.card_catalog.get(CardId(card_id))
        except KeyError as exc:
            raise GameManagerError(f"Unknown card id: {card_id}.") from exc

    def event_log(self) -> EventLog:
        return self.session.event_log

    def export_rng_state(self) -> dict[str, Any]:
        return self.session.export_rng_state()

    def add_player(self, name: str, *, max_health: int = 50) -> Player:
        return self.session.state_manager.add_player(name, max_health=max_health)

    def remove_player(self, player_id: str) -> Player:
        try:
            return self.session.state_manager.remove_player(PlayerId(player_id))
        except KeyError as exc:
            raise GameManagerError(f"Unknown player: {player_id}.") from exc

    def summon_card(self, player_id: str, instance_id: str, *, position: int | None = None) -> CardInstance:
        player = self.player(player_id)
        try:
            card = player.summon_to_board(CardInstanceId(instance_id), position=position)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise GameManagerError(str(exc)) from exc
        self.session.record_event(
            "api.player.card.summoned",
            {
                "player_id": player.player_id,
                "instance_id": instance_id,
                "position": position,
            },
        )
        return card

    def transition_phase(self, node_id: str) -> None:
        try:
            self.session.state_manager.transition_to(node_id)
        except KeyError as exc:
            raise GameManagerError(str(exc)) from exc

    def advance_phase(self) -> PhaseTransitionResult:
        try:
            return self.session.state_manager.advance()
        except ValueError as exc:
            raise GameManagerError(str(exc)) from exc

    def start_shop(self) -> None:
        self.session.shop_manager.start_shop_phase(self._phase_context())

    def end_shop(self) -> None:
        self.session.shop_manager.end_shop_phase(self._phase_context())

    def buy_shop_card(self, player_id: str, offer_index: int) -> CardInstance:
        player = self.player(player_id)
        try:
            return self.session.shop_manager.buy(player, offer_index)
        except (KeyError, ValueError) as exc:
            raise GameManagerError(str(exc)) from exc

    def sell_from_hand(self, player_id: str, instance_id: str) -> CardInstance:
        player = self.player(player_id)
        try:
            return self.session.shop_manager.sell_from_hand(player, CardInstanceId(instance_id))
        except (KeyError, ValueError) as exc:
            raise GameManagerError(str(exc)) from exc

    def sell_from_board(self, player_id: str, instance_id: str) -> CardInstance:
        player = self.player(player_id)
        try:
            return self.session.shop_manager.sell_from_board(player, CardInstanceId(instance_id))
        except (KeyError, ValueError) as exc:
            raise GameManagerError(str(exc)) from exc

    def resolve_combat_round(self) -> CombatRoundResult:
        try:
            return self.session.combat_manager.resolve_combat_round(self.session.state_manager.active_players())
        except ValueError as exc:
            raise GameManagerError(str(exc)) from exc

    def player(self, player_id: str) -> Player:
        try:
            return self.session.state_manager.players[PlayerId(player_id)]
        except KeyError as exc:
            raise GameManagerError(f"Unknown player: {player_id}.") from exc

    def _phase_context(self) -> PhaseContext:
        return PhaseContext(state_manager=self.session.state_manager)
