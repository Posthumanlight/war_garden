from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from game.engine.events import EngineEvent
from game.engine.ids import IdFactory, PlayerId
from game.players.player import Player


DEFAULT_PLAYER_HEALTH = 50


class PhaseNode(Protocol):
    node_id: str

    def enter(self, context: PhaseContext) -> None:
        """Run when this phase becomes active."""

    def execute(self, context: PhaseContext) -> None:
        """Run the phase's main work."""

    def exit(self, context: PhaseContext) -> None:
        """Run before leaving this phase."""


@dataclass(frozen=True, slots=True)
class PhaseContext:
    state_manager: StateManager

    @property
    def current_node_id(self) -> str | None:
        return self.state_manager.current_node_id

    @property
    def round_number(self) -> int:
        return self.state_manager.round_number

    @property
    def turn_number(self) -> int:
        return self.state_manager.turn_number


@dataclass(frozen=True, slots=True)
class PhaseTransitionResult:
    executed_node_id: str
    next_node_id: str
    round_number: int
    turn_number: int


@dataclass(slots=True)
class StateManager:
    id_factory: IdFactory
    event_recorder: Callable[[str, dict[str, Any]], EngineEvent | None]
    players: dict[PlayerId, Player] = field(default_factory=dict)
    defeated_player_ids: set[PlayerId] = field(default_factory=set)
    phase_nodes: dict[str, PhaseNode] = field(default_factory=dict)
    phase_order: list[str] = field(default_factory=lambda: ["shop", "combat"])
    current_node_id: str | None = None
    round_number: int = 1
    turn_number: int = 0

    def add_player(self, name: str, *, max_health: int = DEFAULT_PLAYER_HEALTH) -> Player:
        player = Player(
            player_id=self.id_factory.next_player_id(),
            name=name,
            max_health=max_health,
            health=max_health,
        )
        self.players[player.player_id] = player
        self._record(
            "state.player.added",
            {
                "player_id": player.player_id,
                "name": player.name,
                "health": player.health,
                "max_health": player.max_health,
            },
        )
        return player

    def remove_player(self, player_id: PlayerId) -> Player:
        player = self.players.pop(player_id)
        self._record("state.player.removed", {"player_id": player.player_id, "name": player.name})
        return player

    def mark_defeated(self, player_id: PlayerId) -> None:
        player = self.players[player_id]
        player.health = 0
        player.is_defeated = True
        if player_id in self.defeated_player_ids:
            return
        self.defeated_player_ids.add(player_id)
        self._record("state.player.defeated", {"player_id": player.player_id, "name": player.name})

    def active_players(self) -> tuple[Player, ...]:
        return tuple(player for player in self.players.values() if not player.is_defeated)

    def register_phase_node(self, node: PhaseNode) -> None:
        self.phase_nodes[node.node_id] = node
        if node.node_id not in self.phase_order:
            self.phase_order.append(node.node_id)

    def transition_to(self, node_id: str) -> None:
        if node_id not in self.phase_nodes:
            raise KeyError(f"Unknown phase node: {node_id}.")

        context = PhaseContext(state_manager=self)
        if self.current_node_id is not None:
            previous_node = self.phase_nodes[self.current_node_id]
            previous_node.exit(context)
            self._record("state.phase.exited", {"node_id": previous_node.node_id})

        self.current_node_id = node_id
        next_node = self.phase_nodes[node_id]
        next_node.enter(context)
        self._record("state.phase.entered", {"node_id": next_node.node_id})

    def advance(self) -> PhaseTransitionResult:
        if not self.phase_order:
            raise ValueError("StateManager has no phase order.")
        if self.current_node_id is None:
            self.transition_to(self.phase_order[0])
        if self.current_node_id is None:
            raise ValueError("StateManager failed to enter an initial phase.")

        executed_node_id = self.current_node_id
        context = PhaseContext(state_manager=self)
        node = self.phase_nodes[executed_node_id]
        node.execute(context)
        self._record("state.phase.executed", {"node_id": executed_node_id})

        next_node_id = self._next_node_id(executed_node_id)
        self.turn_number += 1
        if executed_node_id == "combat" and next_node_id == "shop":
            self.round_number += 1
        self.transition_to(next_node_id)
        return PhaseTransitionResult(
            executed_node_id=executed_node_id,
            next_node_id=next_node_id,
            round_number=self.round_number,
            turn_number=self.turn_number,
        )

    def _next_node_id(self, node_id: str) -> str:
        try:
            current_index = self.phase_order.index(node_id)
        except ValueError as exc:
            raise ValueError(f"Current phase is not in phase order: {node_id}.") from exc
        return self.phase_order[(current_index + 1) % len(self.phase_order)]

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        self.event_recorder(event_type, payload)
