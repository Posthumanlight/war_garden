from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from game.cards import CreatureCard, EffectConditions, EffectKeyword, EffectRegistry, load_card_catalog
from game.cards.card_effects import register_builtin_card_effects
from game.cards.cards import CardInstance, SpellCard
from game.cards.effects import HitEffectPhase
from game.engine.combat import HitContext, HitResolutionError, HitResolver
from game.engine.ids import CardId, CardInstanceId, PlayerId


def test_basic_hit_applies_simultaneous_damage() -> None:
    attacker = _instance(_creature("attacker", attack=2, health=3), "a")
    defender = _instance(_creature("defender", attack=1, health=4), "d")
    resolver = HitResolver(effect_registry=EffectRegistry())

    result = resolver.resolve_hit(attacker, defender)

    assert result.attacker_damage_taken == 1
    assert result.defender_damage_taken == 2
    assert attacker.current_health == 2
    assert defender.current_health == 2


def test_health_clamps_to_zero() -> None:
    attacker = _instance(_creature("attacker", attack=10, health=3), "a")
    defender = _instance(_creature("defender", attack=1, health=1), "d")
    resolver = HitResolver(effect_registry=EffectRegistry())

    result = resolver.resolve_hit(attacker, defender)

    assert defender.current_health == 0
    assert result.defender_destroyed is True


def test_dead_or_non_creature_participants_cannot_resolve_hits() -> None:
    resolver = HitResolver(effect_registry=EffectRegistry())
    dead_attacker = _instance(_creature("dead", attack=1, health=1), "dead", current_health=0)
    defender = _instance(_creature("defender", attack=1, health=1), "defender")
    spell = CardInstance(
        instance_id=CardInstanceId("spell"),
        definition=SpellCard(card_id=CardId("spell.spark"), name="Spark"),
        owner_id=PlayerId("p1"),
        zone="hand",
    )

    with pytest.raises(HitResolutionError, match="attacker must be alive"):
        resolver.resolve_hit(dead_attacker, defender)

    with pytest.raises(HitResolutionError, match="attacker must be a creature"):
        resolver.resolve_hit(spell, defender)


def test_gather_on_hit_effects_does_not_mutate_state() -> None:
    registry = _builtin_registry()
    knight = _knight_instance(registry, "knight")
    defender = _instance(_creature("defender", attack=1, health=4), "defender")
    resolver = HitResolver(effect_registry=registry)

    queued = resolver.gather_on_hit_effects(HitContext(attacker=knight, defender=defender))

    assert [effect.effect_key for effect in queued] == [
        "knight.on_attack.attack_plus_1",
        "knight.bounty.health_plus_1",
    ]
    assert knight.current_attack == 2
    assert knight.current_health == 3
    assert defender.current_health == 4


def test_knight_on_attack_and_bounty_trigger_when_attacking() -> None:
    registry = _builtin_registry()
    knight = _knight_instance(registry, "knight")
    defender = _instance(_creature("defender", attack=2, health=4), "defender")
    resolver = HitResolver(effect_registry=registry)

    result = resolver.resolve_hit(knight, defender)

    assert knight.current_attack == 3
    assert knight.current_health == 2
    assert defender.current_health == 1
    assert result.defender_damage_taken == 3
    assert [effect.keyword_id for effect in result.before_damage_effects] == ["on_attack"]
    assert [effect.keyword_id for effect in result.after_damage_effects] == ["after_attack"]


def test_knight_effects_do_not_trigger_when_defending() -> None:
    registry = _builtin_registry()
    attacker = _instance(_creature("attacker", attack=1, health=3), "attacker")
    knight = _knight_instance(registry, "knight")
    resolver = HitResolver(effect_registry=registry)

    result = resolver.resolve_hit(attacker, knight)

    assert knight.current_attack == 2
    assert knight.current_health == 2
    assert attacker.current_health == 1
    assert result.before_damage_effects == ()
    assert result.after_damage_effects == ()


def test_bounty_can_save_knight_before_death_reporting() -> None:
    registry = _builtin_registry()
    knight = _knight_instance(registry, "knight", current_health=1)
    defender = _instance(_creature("defender", attack=1, health=10), "defender")
    resolver = HitResolver(effect_registry=registry)

    result = resolver.resolve_hit(knight, defender)

    assert knight.current_health == 1
    assert result.attacker_destroyed is False
    assert result.destroyed_instance_ids == ()


def test_higher_priority_effects_execute_earlier() -> None:
    executed: list[str] = []
    registry = EffectRegistry()
    registry.register("low", _RecordingEffect(key="low", priority=10, executed=executed))
    registry.register("high", _RecordingEffect(key="high", priority=20, executed=executed))
    attacker = _instance(_creature("attacker", attack=1, health=3, effect_keys=("low", "high")), "attacker")
    defender = _instance(_creature("defender", attack=1, health=3), "defender")
    resolver = HitResolver(effect_registry=registry)

    queued = resolver.gather_on_hit_effects(HitContext(attacker=attacker, defender=defender))
    resolver.execute_on_hit_effects(HitContext(attacker=attacker, defender=defender), queued)

    assert [effect.effect_key for effect in queued] == ["high", "low"]
    assert executed == ["high", "low"]


def test_equal_priority_attacker_effects_order_before_defender_effects() -> None:
    registry = EffectRegistry()
    registry.register("attacker.effect", _RecordingEffect(key="attacker.effect", priority=10))
    registry.register("defender.effect", _RecordingEffect(key="defender.effect", priority=10))
    attacker = _instance(_creature("attacker", attack=1, health=3, effect_keys=("attacker.effect",)), "attacker")
    defender = _instance(_creature("defender", attack=1, health=3, effect_keys=("defender.effect",)), "defender")
    resolver = HitResolver(effect_registry=registry)

    queued = resolver.gather_on_hit_effects(HitContext(attacker=attacker, defender=defender))

    assert [effect.effect_key for effect in queued] == ["attacker.effect", "defender.effect"]


def test_queue_order_is_deterministic_across_repeated_gathers() -> None:
    registry = _builtin_registry()
    knight = _knight_instance(registry, "knight")
    defender = _instance(_creature("defender", attack=1, health=4), "defender")
    resolver = HitResolver(effect_registry=registry)
    context = HitContext(attacker=knight, defender=defender)

    first = resolver.gather_on_hit_effects(context)
    second = resolver.gather_on_hit_effects(context)

    assert [effect.effect_key for effect in first] == [effect.effect_key for effect in second]


def test_hit_result_reports_destroyed_ids_without_moving_cards() -> None:
    attacker = _instance(_creature("attacker", attack=5, health=3), "attacker")
    defender = _instance(_creature("defender", attack=1, health=1), "defender")
    resolver = HitResolver(effect_registry=EffectRegistry())

    result = resolver.resolve_hit(attacker, defender)

    assert result.destroyed_instance_ids == (defender.instance_id,)
    assert defender.zone == "board"


def test_structured_events_are_emitted_in_expected_order() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    registry = _builtin_registry()
    knight = _knight_instance(registry, "knight")
    defender = _instance(_creature("defender", attack=1, health=4), "defender")
    resolver = HitResolver(effect_registry=registry, event_recorder=lambda event_type, payload: events.append((event_type, payload)))

    resolver.resolve_hit(knight, defender)

    assert [event_type for event_type, _ in events] == [
        "hit.started",
        "hit.effects.gathered",
        "hit.effect.executed",
        "hit.damage.applied",
        "hit.effect.executed",
        "hit.death.pending",
        "hit.completed",
    ]


def _builtin_registry() -> EffectRegistry:
    registry = EffectRegistry()
    register_builtin_card_effects(registry)
    return registry


def _knight_instance(registry: EffectRegistry, instance_id: str, *, current_health: int | None = None) -> CardInstance:
    catalog = load_card_catalog(effect_registry=registry)
    return _instance(catalog.get("creature.knight"), instance_id, current_health=current_health)


def _creature(
    suffix: str,
    *,
    attack: int,
    health: int,
    effect_keys: tuple[str, ...] = (),
) -> CreatureCard:
    return CreatureCard(
        card_id=CardId(f"creature.{suffix}"),
        name=suffix.title(),
        attack=attack,
        health=health,
        effect_keys=effect_keys,
    )


def _instance(
    definition: CreatureCard,
    instance_id: str,
    *,
    current_health: int | None = None,
) -> CardInstance:
    return CardInstance(
        instance_id=CardInstanceId(instance_id),
        definition=definition,
        owner_id=PlayerId("player"),
        zone="board",
        current_health=current_health,
    )


@dataclass(frozen=True, slots=True)
class _RecordingEffect:
    key: str
    priority: int
    executed: list[str] = field(default_factory=list)
    keyword: EffectKeyword = EffectKeyword(keyword_id="test", display_name="Test")
    phase: HitEffectPhase = "before_damage"
    conditions: EffectConditions = EffectConditions()

    def execute_hit_effect(self, context: HitContext, source: CardInstance) -> None:
        self.executed.append(self.key)
