from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from game.cards.effects import EffectRegistry
from game.engine.combat import CombatResolver, CombatResult
from game.engine.events import EngineEvent
from game.engine.ids import PlayerId
from game.session.state_manager import PhaseContext, StateManager

if TYPE_CHECKING:
    from game.engine.rng import RngContext
    from game.players.player import Player


FIXED_COMBAT_DAMAGE = 5


@dataclass(frozen=True, slots=True)
class CombatPair:
    player_a: Player
    player_b: Player


@dataclass(frozen=True, slots=True)
class CombatPairingResult:
    pairs: tuple[CombatPair, ...]
    bye_player: Player | None = None


@dataclass(frozen=True, slots=True)
class PairCombatResult:
    pair: CombatPair
    combat_result: CombatResult


@dataclass(frozen=True, slots=True)
class CombatRoundResult:
    pair_results: tuple[PairCombatResult, ...]
    bye_player_id: PlayerId | None
    defeated_player_ids: tuple[PlayerId, ...]


@dataclass(slots=True)
class CombatManager:
    effect_registry: EffectRegistry
    rng: RngContext
    state_manager: StateManager
    event_recorder: Callable[[str, dict[str, Any]], EngineEvent | None]
    fixed_damage: int = FIXED_COMBAT_DAMAGE
    combat_resolver: CombatResolver | None = None

    def __post_init__(self) -> None:
        if self.fixed_damage < 0:
            raise ValueError("fixed_damage cannot be negative.")
        if self.combat_resolver is None:
            self.combat_resolver = CombatResolver(
                effect_registry=self.effect_registry,
                rng=self.rng,
                event_recorder=self.event_recorder,
            )

    def select_opponent_pairs(self, players: tuple[Player, ...]) -> CombatPairingResult:
        shuffled_players = list(players)
        self.rng.shuffle(shuffled_players, purpose="combat_manager.opponent_pairing")
        bye_player = shuffled_players[-1] if len(shuffled_players) % 2 == 1 else None
        pairable_players = shuffled_players[:-1] if bye_player is not None else shuffled_players
        pairs = tuple(
            CombatPair(player_a=pairable_players[index], player_b=pairable_players[index + 1])
            for index in range(0, len(pairable_players), 2)
        )
        return CombatPairingResult(pairs=pairs, bye_player=bye_player)

    def resolve_combat_round(self, players: tuple[Player, ...]) -> CombatRoundResult:
        active_players = tuple(player for player in players if not player.is_defeated)
        self._record(
            "combat_round.started",
            {
                "active_player_ids": tuple(player.player_id for player in active_players),
            },
        )
        pairing_result = self.select_opponent_pairs(active_players)
        self._record(
            "combat_round.pairings.selected",
            {
                "pairs": tuple((pair.player_a.player_id, pair.player_b.player_id) for pair in pairing_result.pairs),
                "bye_player_id": None if pairing_result.bye_player is None else pairing_result.bye_player.player_id,
            },
        )
        if pairing_result.bye_player is not None:
            self._record("combat_round.bye.assigned", {"player_id": pairing_result.bye_player.player_id})

        pair_results: list[PairCombatResult] = []
        defeated_before = {player.player_id for player in self.state_manager.players.values() if player.is_defeated}
        for pair in pairing_result.pairs:
            combat_result = self.combat_resolver.resolve_combat(pair.player_a, pair.player_b)
            self.apply_combat_damage(combat_result, pair.player_a, pair.player_b)
            pair_results.append(PairCombatResult(pair=pair, combat_result=combat_result))

        defeated_after = {player.player_id for player in self.state_manager.players.values() if player.is_defeated}
        defeated_player_ids = tuple(defeated_after - defeated_before)
        round_result = CombatRoundResult(
            pair_results=tuple(pair_results),
            bye_player_id=None if pairing_result.bye_player is None else pairing_result.bye_player.player_id,
            defeated_player_ids=defeated_player_ids,
        )
        self._record(
            "combat_round.completed",
            {
                "pair_count": len(pair_results),
                "bye_player_id": round_result.bye_player_id,
                "defeated_player_ids": round_result.defeated_player_ids,
            },
        )
        return round_result

    def apply_combat_damage(self, result: CombatResult, player_a: Player, player_b: Player) -> None:
        damaged_players: list[Player] = []
        if result.outcome == "player_a":
            damaged_players.append(player_b)
        elif result.outcome == "player_b":
            damaged_players.append(player_a)
        else:
            damaged_players.extend((player_a, player_b))

        for player in damaged_players:
            previous_health = player.health
            player.take_player_damage(self.fixed_damage)
            self._record(
                "combat_round.damage.applied",
                {
                    "player_id": player.player_id,
                    "damage": self.fixed_damage,
                    "previous_health": previous_health,
                    "health": player.health,
                },
            )
            if player.health == 0:
                self.state_manager.mark_defeated(player.player_id)

    def create_phase_node(self) -> CombatPhaseNode:
        return CombatPhaseNode(combat_manager=self)

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        self.event_recorder(event_type, payload)


@dataclass(slots=True)
class CombatPhaseNode:
    combat_manager: CombatManager
    node_id: str = "combat"

    def enter(self, context: PhaseContext) -> None:
        return None

    def execute(self, context: PhaseContext) -> None:
        self.combat_manager.resolve_combat_round(context.state_manager.active_players())

    def exit(self, context: PhaseContext) -> None:
        return None

