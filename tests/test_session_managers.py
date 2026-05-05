from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.engine.combat import CombatResult
from game.engine.events import EventLog
from game.engine.ids import IdFactory, PlayerId, SessionId
from game.engine.rng import RngContext
from game.players.player import Player
from game.session import GameSession, ShopManager, StateManager
from game.session.combat_manager import CombatManager
from game.cards.effects import EffectRegistry


def test_game_session_composes_managers_without_owning_players() -> None:
    session = GameSession(seed=1, session_id=SessionId("session"))

    assert isinstance(session.state_manager, StateManager)
    assert isinstance(session.combat_manager, CombatManager)
    assert isinstance(session.shop_manager, ShopManager)
    assert not hasattr(session, "players")
    assert session.snapshot_metadata()["player_count"] == 0


def test_state_manager_add_player_creates_default_health() -> None:
    manager = _state_manager()

    player = manager.add_player("Alice")

    assert player.health == 50
    assert player.max_health == 50
    assert player.is_defeated is False
    assert manager.players[player.player_id] is player


def test_state_manager_remove_player_removes_from_players() -> None:
    manager = _state_manager()
    player = manager.add_player("Alice")

    removed = manager.remove_player(player.player_id)

    assert removed is player
    assert player.player_id not in manager.players


def test_defeated_players_remain_stored_but_are_not_active() -> None:
    manager = _state_manager()
    active = manager.add_player("Active")
    defeated = manager.add_player("Defeated")

    manager.mark_defeated(defeated.player_id)

    assert defeated.player_id in manager.players
    assert defeated.is_defeated is True
    assert manager.active_players() == (active,)


def test_phase_flow_defaults_shop_to_combat_to_shop() -> None:
    manager = _state_manager()
    calls: list[str] = []
    manager.register_phase_node(_RecordingPhaseNode(node_id="shop", calls=calls))
    manager.register_phase_node(_RecordingPhaseNode(node_id="combat", calls=calls))

    first = manager.advance()
    second = manager.advance()

    assert first.executed_node_id == "shop"
    assert first.next_node_id == "combat"
    assert second.executed_node_id == "combat"
    assert second.next_node_id == "shop"
    assert second.round_number == 2
    assert calls == [
        "shop.enter",
        "shop.execute",
        "shop.exit",
        "combat.enter",
        "combat.execute",
        "combat.exit",
        "shop.enter",
    ]


def test_custom_phase_node_can_be_registered_and_transitioned_to() -> None:
    manager = _state_manager()
    calls: list[str] = []
    manager.register_phase_node(_RecordingPhaseNode(node_id="custom", calls=calls))

    manager.transition_to("custom")

    assert manager.current_node_id == "custom"
    assert calls == ["custom.enter"]


def test_combat_manager_seeded_shuffle_is_deterministic() -> None:
    first_manager = _combat_manager(seed=7)
    second_manager = _combat_manager(seed=7)
    first_players = tuple(_player(str(index)) for index in range(4))
    second_players = tuple(_player(str(index)) for index in range(4))

    first_pairs = first_manager.select_opponent_pairs(first_players)
    second_pairs = second_manager.select_opponent_pairs(second_players)

    assert _pair_ids(first_pairs.pairs) == _pair_ids(second_pairs.pairs)


def test_odd_active_player_receives_bye_and_no_damage() -> None:
    manager = _combat_manager(seed=3)
    players = tuple(_player(str(index)) for index in range(3))

    pairings = manager.select_opponent_pairs(players)

    assert len(pairings.pairs) == 1
    assert pairings.bye_player is not None
    assert pairings.bye_player.health == 50


def test_combat_loser_takes_fixed_damage() -> None:
    manager = _combat_manager()
    player_a = _player("a")
    player_b = _player("b")

    manager.apply_combat_damage(_combat_result("player_a", player_a, player_b), player_a, player_b)

    assert player_a.health == 50
    assert player_b.health == 45


def test_combat_draw_damages_both_players() -> None:
    manager = _combat_manager()
    player_a = _player("a")
    player_b = _player("b")

    manager.apply_combat_damage(_combat_result("draw", player_a, player_b), player_a, player_b)

    assert player_a.health == 45
    assert player_b.health == 45


def test_player_health_clamps_and_marks_defeated() -> None:
    events: list[str] = []
    state_manager = _state_manager()
    state_manager.event_recorder = lambda event_type, payload: events.append(event_type)
    manager = _combat_manager(state_manager=state_manager)
    player_a = state_manager.add_player("A")
    player_b = state_manager.add_player("B")
    player_b.health = 3

    manager.apply_combat_damage(_combat_result("player_a", player_a, player_b), player_a, player_b)

    assert player_b.health == 0
    assert player_b.is_defeated is True
    assert state_manager.active_players() == (player_a,)
    assert "state.player.defeated" in events


def test_shop_manager_emits_start_and_end_events() -> None:
    events: list[str] = []
    state_manager = _state_manager(event_recorder=lambda event_type, payload: events.append(event_type))
    shop_manager = ShopManager(event_recorder=lambda event_type, payload: events.append(event_type))
    context = state_manager_context(state_manager)

    shop_manager.start_shop_phase(context)
    shop_manager.end_shop_phase(context)

    assert events == ["shop.phase.started", "shop.phase.ended"]


def _state_manager(event_recorder: Any | None = None) -> StateManager:
    return StateManager(
        id_factory=IdFactory(session_id=SessionId("session")),
        event_recorder=(lambda event_type, payload: None) if event_recorder is None else event_recorder,
    )


def _combat_manager(*, seed: int = 1, state_manager: StateManager | None = None) -> CombatManager:
    manager = _state_manager() if state_manager is None else state_manager
    return CombatManager(
        effect_registry=EffectRegistry(),
        rng=RngContext(seed=seed, event_log=EventLog()),
        state_manager=manager,
        event_recorder=lambda event_type, payload: None,
    )


def _player(suffix: str) -> Player:
    return Player(player_id=PlayerId(f"player.{suffix}"), name=suffix)


def _pair_ids(pairs: tuple[Any, ...]) -> tuple[tuple[PlayerId, PlayerId], ...]:
    return tuple((pair.player_a.player_id, pair.player_b.player_id) for pair in pairs)


def _combat_result(outcome: str, player_a: Player, player_b: Player) -> CombatResult:
    winner = player_a.player_id if outcome == "player_a" else player_b.player_id if outcome == "player_b" else None
    return CombatResult(
        outcome=outcome,  # type: ignore[arg-type]
        winner_player_id=winner,
        player_a_id=player_a.player_id,
        player_b_id=player_b.player_id,
        steps=1,
        max_steps_reached=False,
        destroyed_instance_ids=(),
        start_of_combat_effects=(),
        end_of_combat_effects=(),
        player_a_living_count=1 if outcome in ("player_a", "draw") else 0,
        player_b_living_count=1 if outcome in ("player_b", "draw") else 0,
    )


def state_manager_context(state_manager: StateManager):
    from game.session.state_manager import PhaseContext

    return PhaseContext(state_manager=state_manager)


@dataclass(slots=True)
class _RecordingPhaseNode:
    node_id: str
    calls: list[str] = field(default_factory=list)

    def enter(self, context: Any) -> None:
        self.calls.append(f"{self.node_id}.enter")

    def execute(self, context: Any) -> None:
        self.calls.append(f"{self.node_id}.execute")

    def exit(self, context: Any) -> None:
        self.calls.append(f"{self.node_id}.exit")
