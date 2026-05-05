from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from game.cards.effects import EffectRegistry, EffectSourceSide, HitEffectPhase, OnHitEffect
from game.engine.events import EngineEvent
from game.engine.ids import CardInstanceId

if TYPE_CHECKING:
    from game.cards.cards import CardInstance


PHASE_ORDER: dict[HitEffectPhase, int] = {
    "before_damage": 0,
    "after_damage": 1,
    "after_death": 2,
}


class HitResolutionError(ValueError):
    """Raised when a hit cannot be resolved."""


@dataclass(frozen=True, slots=True)
class HitContext:
    attacker: CardInstance
    defender: CardInstance
    attacker_position: int | None = None
    defender_position: int | None = None


@dataclass(frozen=True, slots=True)
class QueuedHitEffect:
    phase: HitEffectPhase
    priority: int
    source_side: EffectSourceSide
    source_position: int | None
    source_instance_id: CardInstanceId
    effect_key: str
    keyword_id: str
    keyword_display_name: str
    effect: OnHitEffect


@dataclass(frozen=True, slots=True)
class HitResult:
    attacker_damage_taken: int
    defender_damage_taken: int
    attacker_destroyed: bool
    defender_destroyed: bool
    destroyed_instance_ids: tuple[CardInstanceId, ...]
    before_damage_effects: tuple[QueuedHitEffect, ...]
    after_damage_effects: tuple[QueuedHitEffect, ...]
    after_death_effects: tuple[QueuedHitEffect, ...]


@dataclass(slots=True)
class HitResolver:
    effect_registry: EffectRegistry
    event_recorder: Callable[[str, dict[str, Any]], EngineEvent | None] | None = None

    def resolve_hit(
        self,
        attacker: CardInstance,
        defender: CardInstance,
        *,
        attacker_position: int | None = None,
        defender_position: int | None = None,
    ) -> HitResult:
        self._validate_hit_participant(attacker, role="attacker")
        self._validate_hit_participant(defender, role="defender")
        context = HitContext(
            attacker=attacker,
            defender=defender,
            attacker_position=attacker_position,
            defender_position=defender_position,
        )
        self._record(
            "hit.started",
            {
                "attacker_instance_id": attacker.instance_id,
                "defender_instance_id": defender.instance_id,
            },
        )

        queued_effects = self.gather_on_hit_effects(context)
        before_damage_effects = self._effects_for_phase(queued_effects, "before_damage")
        after_damage_effects = self._effects_for_phase(queued_effects, "after_damage")
        after_death_effects = self._effects_for_phase(queued_effects, "after_death")

        self.execute_on_hit_effects(context, before_damage_effects)

        defender_damage_taken = self._combat_attack(attacker)
        attacker_damage_taken = self._combat_attack(defender)
        defender.take_damage(defender_damage_taken)
        attacker.take_damage(attacker_damage_taken)
        self._record(
            "hit.damage.applied",
            {
                "attacker_instance_id": attacker.instance_id,
                "defender_instance_id": defender.instance_id,
                "attacker_damage_taken": attacker_damage_taken,
                "defender_damage_taken": defender_damage_taken,
                "attacker_health": attacker.current_health,
                "defender_health": defender.current_health,
            },
        )

        self.execute_on_hit_effects(context, after_damage_effects)

        attacker_destroyed = not attacker.is_alive
        defender_destroyed = not defender.is_alive
        destroyed_instance_ids = tuple(
            card.instance_id
            for card, destroyed in ((attacker, attacker_destroyed), (defender, defender_destroyed))
            if destroyed
        )
        self._record(
            "hit.death.pending",
            {
                "attacker_instance_id": attacker.instance_id,
                "defender_instance_id": defender.instance_id,
                "destroyed_instance_ids": destroyed_instance_ids,
            },
        )

        self.execute_on_hit_effects(context, after_death_effects)
        result = HitResult(
            attacker_damage_taken=attacker_damage_taken,
            defender_damage_taken=defender_damage_taken,
            attacker_destroyed=attacker_destroyed,
            defender_destroyed=defender_destroyed,
            destroyed_instance_ids=destroyed_instance_ids,
            before_damage_effects=before_damage_effects,
            after_damage_effects=after_damage_effects,
            after_death_effects=after_death_effects,
        )
        self._record(
            "hit.completed",
            {
                "attacker_instance_id": attacker.instance_id,
                "defender_instance_id": defender.instance_id,
                "attacker_destroyed": attacker_destroyed,
                "defender_destroyed": defender_destroyed,
                "destroyed_instance_ids": destroyed_instance_ids,
            },
        )
        return result

    def gather_on_hit_effects(self, context: HitContext) -> tuple[QueuedHitEffect, ...]:
        queued_effects: list[QueuedHitEffect] = []
        for source_side, source, source_position in self._effect_sources(context):
            for effect_key in source.definition.effect_keys:
                effect = self.effect_registry.get_on_hit_effect(effect_key)
                if not effect.conditions.matches_static(source_side=source_side):
                    continue
                queued_effects.append(
                    QueuedHitEffect(
                        phase=effect.phase,
                        priority=effect.priority,
                        source_side=source_side,
                        source_position=source_position,
                        source_instance_id=source.instance_id,
                        effect_key=effect.key,
                        keyword_id=effect.keyword.keyword_id,
                        keyword_display_name=effect.keyword.display_name,
                        effect=effect,
                    )
                )

        ordered_effects = tuple(sorted(queued_effects, key=self._effect_sort_key))
        self._record(
            "hit.effects.gathered",
            {
                "attacker_instance_id": context.attacker.instance_id,
                "defender_instance_id": context.defender.instance_id,
                "queued_effects": [self._effect_payload(effect) for effect in ordered_effects],
            },
        )
        return ordered_effects

    def execute_on_hit_effects(self, context: HitContext, queued_effects: tuple[QueuedHitEffect, ...]) -> None:
        for queued_effect in queued_effects:
            source = context.attacker if queued_effect.source_side == "attacker" else context.defender
            if not queued_effect.effect.conditions.matches(
                context=context,
                source=source,
                source_side=queued_effect.source_side,
            ):
                self._record("hit.effect.skipped", self._effect_payload(queued_effect))
                continue

            queued_effect.effect.execute_hit_effect(context, source)
            payload = self._effect_payload(queued_effect)
            payload.update(
                {
                    "source_attack": source.current_attack,
                    "source_health": source.current_health,
                }
            )
            self._record("hit.effect.executed", payload)

    def _validate_hit_participant(self, card: CardInstance, *, role: Literal["attacker", "defender"]) -> None:
        if not card.is_creature:
            raise HitResolutionError(f"Hit {role} must be a creature.")
        if not card.is_alive:
            raise HitResolutionError(f"Hit {role} must be alive.")

    def _combat_attack(self, card: CardInstance) -> int:
        if card.current_attack is None:
            raise HitResolutionError("Creature attack is missing.")
        return max(0, card.current_attack)

    def _effects_for_phase(
        self,
        queued_effects: tuple[QueuedHitEffect, ...],
        phase: HitEffectPhase,
    ) -> tuple[QueuedHitEffect, ...]:
        return tuple(effect for effect in queued_effects if effect.phase == phase)

    def _effect_sources(
        self,
        context: HitContext,
    ) -> tuple[tuple[EffectSourceSide, CardInstance, int | None], ...]:
        return (
            ("attacker", context.attacker, context.attacker_position),
            ("defender", context.defender, context.defender_position),
        )

    def _effect_sort_key(self, queued_effect: QueuedHitEffect) -> tuple[int, int, int, bool, int, str, str]:
        return (
            PHASE_ORDER[queued_effect.phase],
            -queued_effect.priority,
            0 if queued_effect.source_side == "attacker" else 1,
            queued_effect.source_position is None,
            -1 if queued_effect.source_position is None else queued_effect.source_position,
            str(queued_effect.source_instance_id),
            queued_effect.effect_key,
        )

    def _effect_payload(self, queued_effect: QueuedHitEffect) -> dict[str, Any]:
        return {
            "phase": queued_effect.phase,
            "priority": queued_effect.priority,
            "source_side": queued_effect.source_side,
            "source_position": queued_effect.source_position,
            "source_instance_id": queued_effect.source_instance_id,
            "effect_key": queued_effect.effect_key,
            "keyword_id": queued_effect.keyword_id,
            "keyword_display_name": queued_effect.keyword_display_name,
        }

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.event_recorder is not None:
            self.event_recorder(event_type, payload)
