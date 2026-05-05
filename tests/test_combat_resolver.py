from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.cards import CreatureCard, EffectKeyword, EffectRegistry
from game.cards.effects import CombatEffectConditions, CombatEffectPhase
from game.engine.combat import CombatContext, CombatResolver
from game.engine.events import EventLog
from game.engine.ids import CardId, CardInstanceId, PlayerId
from game.engine.rng import RngContext
from game.cards.cards import CardInstance
from game.players.player import Player


def test_seeded_coinflip_picks_deterministic_first_attacker() -> None:
    first = _resolver(seed=7)
    second = _resolver(seed=7)
    first_context = CombatContext(player_a=_player("a"), player_b=_player("b"), rng=first.rng)
    second_context = CombatContext(player_a=_player("a"), player_b=_player("b"), rng=second.rng)

    assert first.resolve_first_attacker(first_context) == second.resolve_first_attacker(second_context)


def test_attacker_selection_uses_living_cards_left_to_right_and_advances_cursor() -> None:
    player = _player("a")
    dead = _board_creature(player, "dead", attack=1, health=1, current_health=0)
    first_living = _board_creature(player, "first", attack=1, health=1)
    second_living = _board_creature(player, "second", attack=1, health=1)
    resolver = _resolver()

    assert resolver.select_next_attacker(player) == (first_living, 1)
    assert resolver.select_next_attacker(player) == (second_living, 2)
    assert dead.current_health == 0


def test_target_selection_chooses_leftmost_living_enemy() -> None:
    player = _player("b")
    _board_creature(player, "dead", attack=1, health=1, current_health=0)
    target = _board_creature(player, "target", attack=1, health=1)
    resolver = _resolver()

    assert resolver.select_eligible_target(player) == (target, 1)


def test_combat_uses_hit_resolver_and_moves_destroyed_cards_to_graveyard() -> None:
    player_a = _player("a")
    player_b = _player("b")
    attacker = _board_creature(player_a, "attacker", attack=5, health=3)
    defender = _board_creature(player_b, "defender", attack=1, health=1)
    resolver = _resolver(seed=1)

    result = resolver.resolve_combat(player_a, player_b)

    assert result.outcome == "player_a"
    assert defender.instance_id in result.destroyed_instance_ids
    assert defender not in player_b.board.cards
    assert defender in player_b.graveyard.cards
    assert attacker in player_a.board.cards


def test_mutual_board_death_ends_in_draw() -> None:
    player_a = _player("a")
    player_b = _player("b")
    _board_creature(player_a, "a1", attack=2, health=1)
    _board_creature(player_b, "b1", attack=2, health=1)
    resolver = _resolver(seed=1)

    result = resolver.resolve_combat(player_a, player_b)

    assert result.outcome == "draw"
    assert result.player_a_living_count == 0
    assert result.player_b_living_count == 0


def test_max_step_guard_returns_forced_draw() -> None:
    player_a = _player("a")
    player_b = _player("b")
    _board_creature(player_a, "a1", attack=0, health=10)
    _board_creature(player_b, "b1", attack=0, health=10)
    resolver = _resolver(seed=1)

    result = resolver.resolve_combat(player_a, player_b, max_steps=1)

    assert result.outcome == "draw"
    assert result.max_steps_reached is True
    assert result.steps == 1


def test_start_of_combat_gathering_is_deterministic_and_non_mutating() -> None:
    executed: list[str] = []
    registry = EffectRegistry()
    registry.register("start.low", _RecordingCombatEffect(key="start.low", priority=10, executed=executed))
    registry.register("start.high", _RecordingCombatEffect(key="start.high", priority=20, executed=executed))
    player_a = _player("a")
    player_b = _player("b")
    source = _board_creature(player_a, "source", attack=1, health=1, effect_keys=("start.low", "start.high"))
    _board_creature(player_b, "target", attack=1, health=1)
    resolver = _resolver(registry=registry)
    context = CombatContext(player_a=player_a, player_b=player_b, rng=resolver.rng)

    first = resolver.gather_start_of_combat_effects(context)
    second = resolver.gather_start_of_combat_effects(context)

    assert [effect.effect_key for effect in first] == ["start.high", "start.low"]
    assert [effect.effect_key for effect in first] == [effect.effect_key for effect in second]
    assert executed == []
    assert source.current_attack == 1


def test_start_of_combat_execution_follows_priority_order() -> None:
    executed: list[str] = []
    registry = EffectRegistry()
    registry.register("start.low", _RecordingCombatEffect(key="start.low", priority=10, executed=executed))
    registry.register("start.high", _RecordingCombatEffect(key="start.high", priority=20, executed=executed))
    player_a = _player("a")
    player_b = _player("b")
    _board_creature(player_a, "source", attack=1, health=1, effect_keys=("start.low", "start.high"))
    resolver = _resolver(registry=registry)
    context = CombatContext(player_a=player_a, player_b=player_b, rng=resolver.rng)

    queued = resolver.gather_start_of_combat_effects(context)
    resolver.execute_start_of_combat_effects(context, queued)

    assert executed == ["start.high", "start.low"]


def test_end_of_combat_effects_gather_from_all_zones_after_cleanup() -> None:
    executed: list[str] = []
    registry = EffectRegistry()
    registry.register("end.board", _RecordingCombatEffect(key="end.board", phase="end_combat", priority=40, executed=executed))
    registry.register("end.hand", _RecordingCombatEffect(key="end.hand", phase="end_combat", priority=30, executed=executed))
    registry.register("end.deck", _RecordingCombatEffect(key="end.deck", phase="end_combat", priority=20, executed=executed))
    registry.register("end.graveyard", _RecordingCombatEffect(key="end.graveyard", phase="end_combat", priority=10, executed=executed))
    player_a = _player("a")
    player_b = _player("b")
    _board_creature(player_a, "board", attack=1, health=3, effect_keys=("end.board",))
    _hand_creature(player_a, "hand", effect_keys=("end.hand",))
    _deck_creature(player_a, "deck", effect_keys=("end.deck",))
    _graveyard_creature(player_a, "graveyard", effect_keys=("end.graveyard",))
    _board_creature(player_b, "target", attack=1, health=3)
    resolver = _resolver(registry=registry)
    context = CombatContext(player_a=player_a, player_b=player_b, rng=resolver.rng)

    queued = resolver.gather_end_of_combat_effects(context)
    resolver.execute_end_of_combat_effects(context, queued)

    assert [effect.source_zone for effect in queued] == ["board", "hand", "deck", "graveyard"]
    assert executed == ["end.board", "end.hand", "end.deck", "end.graveyard"]


def test_combat_events_wrap_hit_events() -> None:
    events: list[str] = []
    player_a = _player("a")
    player_b = _player("b")
    _board_creature(player_a, "attacker", attack=5, health=3)
    _board_creature(player_b, "defender", attack=1, health=1)
    resolver = _resolver(seed=1, event_recorder=lambda event_type, payload: events.append(event_type))

    resolver.resolve_combat(player_a, player_b)

    assert events[0] == "combat.started"
    assert "combat.first_attacker.selected" in events
    assert "hit.started" in events
    assert "combat.cards.destroyed" in events
    assert events[-1] == "combat.completed"


def _resolver(
    *,
    seed: int = 1,
    registry: EffectRegistry | None = None,
    event_recorder: Any = None,
) -> CombatResolver:
    event_log = EventLog()
    return CombatResolver(
        effect_registry=EffectRegistry() if registry is None else registry,
        rng=RngContext(seed=seed, event_log=event_log),
        event_recorder=event_recorder,
    )


def _player(suffix: str) -> Player:
    return Player(player_id=PlayerId(f"player.{suffix}"), name=suffix)


def _board_creature(
    player: Player,
    suffix: str,
    *,
    attack: int,
    health: int,
    current_health: int | None = None,
    effect_keys: tuple[str, ...] = (),
) -> CardInstance:
    card = _creature_instance(suffix, attack=attack, health=health, current_health=current_health, effect_keys=effect_keys)
    card.owner_id = player.player_id
    player.board.add(card)
    return card


def _hand_creature(player: Player, suffix: str, *, effect_keys: tuple[str, ...]) -> CardInstance:
    card = _creature_instance(suffix, attack=1, health=1, effect_keys=effect_keys)
    card.owner_id = player.player_id
    player.hand.add(card)
    return card


def _deck_creature(player: Player, suffix: str, *, effect_keys: tuple[str, ...]) -> CardInstance:
    card = _creature_instance(suffix, attack=1, health=1, effect_keys=effect_keys)
    card.owner_id = player.player_id
    player.deck.add_to_bottom(card)
    return card


def _graveyard_creature(player: Player, suffix: str, *, effect_keys: tuple[str, ...]) -> CardInstance:
    card = _creature_instance(suffix, attack=1, health=1, effect_keys=effect_keys)
    card.owner_id = player.player_id
    player.graveyard.add(card)
    return card


def _creature_instance(
    suffix: str,
    *,
    attack: int,
    health: int,
    current_health: int | None = None,
    effect_keys: tuple[str, ...] = (),
) -> CardInstance:
    return CardInstance(
        instance_id=CardInstanceId(f"instance.{suffix}"),
        definition=CreatureCard(
            card_id=CardId(f"creature.{suffix}"),
            name=suffix.title(),
            attack=attack,
            health=health,
            effect_keys=effect_keys,
        ),
        owner_id=PlayerId("unassigned"),
        zone="board",
        current_health=current_health,
    )


@dataclass(frozen=True, slots=True)
class _RecordingCombatEffect:
    key: str
    priority: int
    executed: list[str] = field(default_factory=list)
    phase: CombatEffectPhase = "start_combat"
    keyword: EffectKeyword = EffectKeyword(keyword_id="test", display_name="Test")
    conditions: CombatEffectConditions = CombatEffectConditions()

    def execute_combat_effect(self, context: CombatContext, source: CardInstance) -> None:
        self.executed.append(self.key)
