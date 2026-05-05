from __future__ import annotations

from dataclasses import dataclass

from game.cards.cards import CardInstance
from game.cards.effects import EffectConditions, EffectKeyword, EffectRegistry, HitEffectPhase
from game.engine.combat.hit import HitContext


@dataclass(frozen=True, slots=True)
class KnightOnAttackAttackPlusOne:
    key: str = "knight.on_attack.attack_plus_1"
    keyword: EffectKeyword = EffectKeyword(keyword_id="on_attack", display_name="On Attack")
    phase: HitEffectPhase = "before_damage"
    priority: int = 100
    conditions: EffectConditions = EffectConditions(source_must_be_attacker=True)

    def execute_hit_effect(self, context: HitContext, source: CardInstance) -> None:
        if source.current_attack is None:
            raise TypeError("Only creature instances can gain attack.")
        source.current_attack += 1


@dataclass(frozen=True, slots=True)
class KnightBountyHealthPlusOne:
    key: str = "knight.bounty.health_plus_1"
    keyword: EffectKeyword = EffectKeyword(keyword_id="after_attack", display_name="Bounty")
    phase: HitEffectPhase = "after_damage"
    priority: int = 100
    conditions: EffectConditions = EffectConditions(source_must_be_attacker=True)

    def execute_hit_effect(self, context: HitContext, source: CardInstance) -> None:
        if source.current_health is None:
            raise TypeError("Only creature instances can gain health.")
        source.current_health += 1


def register_builtin_card_effects(registry: EffectRegistry) -> None:
    on_attack = KnightOnAttackAttackPlusOne()
    bounty = KnightBountyHealthPlusOne()
    registry.register(on_attack.key, on_attack)
    registry.register(bounty.key, bounty)

