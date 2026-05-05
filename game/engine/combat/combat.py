from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from game.cards.effects import (
    CombatEffectOwnerSide,
    CombatEffectPhase,
    CombatEffectSourceZone,
    EffectRegistry,
    OnCombatEffect,
)
from game.engine.combat.hit import HitResolver, HitResult
from game.engine.events import EngineEvent
from game.engine.ids import CardInstanceId, PlayerId

if TYPE_CHECKING:
    from game.cards.cards import CardInstance
    from game.engine.rng import RngContext
    from game.players.player import Player


CombatOutcome = Literal["player_a", "player_b", "draw"]

COMBAT_PHASE_ORDER: dict[CombatEffectPhase, int] = {
    "start_combat": 0,
    "end_combat": 1,
}
COMBAT_ZONE_ORDER: dict[CombatEffectSourceZone, int] = {
    "board": 0,
    "hand": 1,
    "deck": 2,
    "graveyard": 3,
}


class CombatResolutionError(ValueError):
    """Raised when combat cannot be resolved."""


@dataclass(slots=True)
class CombatContext:
    player_a: Player
    player_b: Player
    rng: RngContext
    step: int = 0
    destroyed_instance_ids: list[CardInstanceId] = field(default_factory=list)
    start_of_combat_effects: tuple[QueuedCombatEffect, ...] = ()
    end_of_combat_effects: tuple[QueuedCombatEffect, ...] = ()

    def player_for_side(self, side: CombatEffectOwnerSide) -> Player:
        return self.player_a if side == "player_a" else self.player_b

    def opponent_for_side(self, side: CombatEffectOwnerSide) -> Player:
        return self.player_b if side == "player_a" else self.player_a


@dataclass(frozen=True, slots=True)
class QueuedCombatEffect:
    phase: CombatEffectPhase
    priority: int
    owner_side: CombatEffectOwnerSide
    source_zone: CombatEffectSourceZone
    source_position: int | None
    source_instance_id: CardInstanceId
    effect_key: str
    keyword_id: str
    keyword_display_name: str
    effect: OnCombatEffect


@dataclass(frozen=True, slots=True)
class CombatResult:
    outcome: CombatOutcome
    winner_player_id: PlayerId | None
    player_a_id: PlayerId
    player_b_id: PlayerId
    steps: int
    max_steps_reached: bool
    destroyed_instance_ids: tuple[CardInstanceId, ...]
    start_of_combat_effects: tuple[QueuedCombatEffect, ...]
    end_of_combat_effects: tuple[QueuedCombatEffect, ...]
    player_a_living_count: int
    player_b_living_count: int


@dataclass(slots=True)
class CombatResolver:
    effect_registry: EffectRegistry
    rng: RngContext
    hit_resolver: HitResolver | None = None
    event_recorder: Callable[[str, dict[str, Any]], EngineEvent | None] | None = None

    def __post_init__(self) -> None:
        if self.hit_resolver is None:
            self.hit_resolver = HitResolver(
                effect_registry=self.effect_registry,
                event_recorder=self.event_recorder,
            )

    def resolve_combat(self, player_a: Player, player_b: Player, *, max_steps: int = 200) -> CombatResult:
        if max_steps <= 0:
            raise CombatResolutionError("max_steps must be greater than 0.")

        player_a.reset_combat_cursor()
        player_b.reset_combat_cursor()
        context = CombatContext(player_a=player_a, player_b=player_b, rng=self.rng)
        self._record(
            "combat.started",
            {
                "player_a_id": player_a.player_id,
                "player_b_id": player_b.player_id,
                "max_steps": max_steps,
            },
        )

        context.start_of_combat_effects = self.gather_start_of_combat_effects(context)
        self.execute_start_of_combat_effects(context, context.start_of_combat_effects)

        first_attacker_id = self.resolve_first_attacker(context)
        active_side = self._side_for_player_id(context, first_attacker_id)
        self._record(
            "combat.first_attacker.selected",
            {
                "first_attacker_player_id": first_attacker_id,
                "first_attacker_side": active_side,
            },
        )

        max_steps_reached = False
        while not self.is_combat_over(context):
            if context.step >= max_steps:
                max_steps_reached = True
                self._record(
                    "combat.max_steps.reached",
                    {
                        "step": context.step,
                        "max_steps": max_steps,
                    },
                )
                break

            context.step += 1
            active_player = context.player_for_side(active_side)
            defending_side = self._opposite_side(active_side)
            defending_player = context.player_for_side(defending_side)
            self._record(
                "combat.step.started",
                {
                    "step": context.step,
                    "active_player_id": active_player.player_id,
                    "active_side": active_side,
                },
            )

            attacker_selection = self.select_next_attacker(active_player)
            target_selection = self.select_eligible_target(defending_player)
            if attacker_selection is None or target_selection is None:
                break

            attacker, attacker_position = attacker_selection
            target, target_position = target_selection
            self._record(
                "combat.attacker.selected",
                {
                    "step": context.step,
                    "attacker_player_id": active_player.player_id,
                    "attacker_instance_id": attacker.instance_id,
                    "attacker_position": attacker_position,
                },
            )
            self._record(
                "combat.target.selected",
                {
                    "step": context.step,
                    "defending_player_id": defending_player.player_id,
                    "target_instance_id": target.instance_id,
                    "target_position": target_position,
                },
            )

            hit_result = self.hit_resolver.resolve_hit(
                attacker,
                target,
                attacker_position=attacker_position,
                defender_position=target_position,
            )
            destroyed_ids = self.cleanup_destroyed_cards(player_a, player_b)
            context.destroyed_instance_ids.extend(destroyed_ids)
            if destroyed_ids:
                self._record(
                    "combat.cards.destroyed",
                    {
                        "step": context.step,
                        "destroyed_instance_ids": destroyed_ids,
                    },
                )
            self._record(
                "combat.step.completed",
                {
                    "step": context.step,
                    "active_player_id": active_player.player_id,
                    "defending_player_id": defending_player.player_id,
                    "hit_destroyed_instance_ids": hit_result.destroyed_instance_ids,
                    "destroyed_instance_ids": destroyed_ids,
                },
            )
            active_side = defending_side

        context.end_of_combat_effects = self.gather_end_of_combat_effects(context)
        self.execute_end_of_combat_effects(context, context.end_of_combat_effects)
        result = self.build_result(context, max_steps_reached=max_steps_reached)
        self._record(
            "combat.completed",
            {
                "outcome": result.outcome,
                "winner_player_id": result.winner_player_id,
                "steps": result.steps,
                "max_steps_reached": result.max_steps_reached,
                "destroyed_instance_ids": result.destroyed_instance_ids,
            },
        )
        return result

    def gather_start_of_combat_effects(self, context: CombatContext) -> tuple[QueuedCombatEffect, ...]:
        return self._gather_combat_effects(context, phase="start_combat")

    def execute_start_of_combat_effects(
        self,
        context: CombatContext,
        queued_effects: tuple[QueuedCombatEffect, ...],
    ) -> None:
        self._execute_combat_effects(context, queued_effects)

    def gather_end_of_combat_effects(self, context: CombatContext) -> tuple[QueuedCombatEffect, ...]:
        return self._gather_combat_effects(context, phase="end_combat")

    def execute_end_of_combat_effects(
        self,
        context: CombatContext,
        queued_effects: tuple[QueuedCombatEffect, ...],
    ) -> None:
        self._execute_combat_effects(context, queued_effects)

    def resolve_first_attacker(self, context: CombatContext) -> PlayerId:
        player_a_attacks_first = context.rng.coinflip(purpose="combat.first_attacker")
        return context.player_a.player_id if player_a_attacks_first else context.player_b.player_id

    def select_next_attacker(self, player: Player) -> tuple[CardInstance, int] | None:
        attacker = player.next_living_attacker()
        if attacker is None:
            return None
        return attacker, self._board_position(player, attacker.instance_id)

    def select_eligible_target(self, defending_player: Player) -> tuple[CardInstance, int] | None:
        for index, card in enumerate(defending_player.board.cards):
            if card.is_alive:
                return card, index
        return None

    def cleanup_destroyed_cards(self, player_a: Player, player_b: Player) -> tuple[CardInstanceId, ...]:
        destroyed = (
            *player_a.move_destroyed_board_cards_to_graveyard(),
            *player_b.move_destroyed_board_cards_to_graveyard(),
        )
        return tuple(card.instance_id for card in destroyed)

    def is_combat_over(self, context: CombatContext) -> bool:
        return not context.player_a.board.living_cards() or not context.player_b.board.living_cards()

    def build_result(self, context: CombatContext, *, max_steps_reached: bool) -> CombatResult:
        player_a_living_count = len(context.player_a.board.living_cards())
        player_b_living_count = len(context.player_b.board.living_cards())

        if max_steps_reached:
            outcome: CombatOutcome = "draw"
            winner_player_id = None
        elif player_a_living_count > 0 and player_b_living_count == 0:
            outcome = "player_a"
            winner_player_id = context.player_a.player_id
        elif player_b_living_count > 0 and player_a_living_count == 0:
            outcome = "player_b"
            winner_player_id = context.player_b.player_id
        else:
            outcome = "draw"
            winner_player_id = None

        return CombatResult(
            outcome=outcome,
            winner_player_id=winner_player_id,
            player_a_id=context.player_a.player_id,
            player_b_id=context.player_b.player_id,
            steps=context.step,
            max_steps_reached=max_steps_reached,
            destroyed_instance_ids=tuple(context.destroyed_instance_ids),
            start_of_combat_effects=context.start_of_combat_effects,
            end_of_combat_effects=context.end_of_combat_effects,
            player_a_living_count=player_a_living_count,
            player_b_living_count=player_b_living_count,
        )

    def _gather_combat_effects(
        self,
        context: CombatContext,
        *,
        phase: CombatEffectPhase,
    ) -> tuple[QueuedCombatEffect, ...]:
        queued_effects: list[QueuedCombatEffect] = []
        for owner_side, source_zone, source, source_position in self._combat_effect_sources(context):
            for effect_key in source.definition.effect_keys:
                try:
                    effect = self.effect_registry.get_combat_effect(effect_key)
                except TypeError:
                    continue
                if effect.phase != phase:
                    continue
                if not effect.conditions.matches_static(owner_side=owner_side, source_zone=source_zone):
                    continue
                queued_effects.append(
                    QueuedCombatEffect(
                        phase=effect.phase,
                        priority=effect.priority,
                        owner_side=owner_side,
                        source_zone=source_zone,
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
            "combat.effects.gathered",
            {
                "phase": phase,
                "queued_effects": [self._effect_payload(effect) for effect in ordered_effects],
            },
        )
        return ordered_effects

    def _execute_combat_effects(self, context: CombatContext, queued_effects: tuple[QueuedCombatEffect, ...]) -> None:
        for queued_effect in queued_effects:
            source = self._source_by_queued_effect(context, queued_effect)
            if not queued_effect.effect.conditions.matches(
                context=context,
                source=source,
                owner_side=queued_effect.owner_side,
                source_zone=queued_effect.source_zone,
            ):
                self._record("combat.effect.skipped", self._effect_payload(queued_effect))
                continue
            queued_effect.effect.execute_combat_effect(context, source)
            self._record("combat.effect.executed", self._effect_payload(queued_effect))

    def _combat_effect_sources(
        self,
        context: CombatContext,
    ) -> tuple[tuple[CombatEffectOwnerSide, CombatEffectSourceZone, CardInstance, int], ...]:
        sources: list[tuple[CombatEffectOwnerSide, CombatEffectSourceZone, CardInstance, int]] = []
        for owner_side in ("player_a", "player_b"):
            player = context.player_for_side(owner_side)
            zone_cards = (
                ("board", player.board.cards),
                ("hand", player.hand.cards),
                ("deck", player.deck.cards),
                ("graveyard", player.graveyard.cards),
            )
            for source_zone, cards in zone_cards:
                sources.extend((owner_side, source_zone, card, index) for index, card in enumerate(cards))
        return tuple(sources)

    def _source_by_queued_effect(self, context: CombatContext, queued_effect: QueuedCombatEffect) -> CardInstance:
        player = context.player_for_side(queued_effect.owner_side)
        zone_cards = {
            "board": player.board.cards,
            "hand": player.hand.cards,
            "deck": player.deck.cards,
            "graveyard": player.graveyard.cards,
        }[queued_effect.source_zone]
        for card in zone_cards:
            if card.instance_id == queued_effect.source_instance_id:
                return card
        raise CombatResolutionError(f"Combat effect source no longer exists: {queued_effect.source_instance_id}.")

    def _effect_sort_key(self, queued_effect: QueuedCombatEffect) -> tuple[int, int, int, int, bool, int, str, str]:
        return (
            COMBAT_PHASE_ORDER[queued_effect.phase],
            -queued_effect.priority,
            0 if queued_effect.owner_side == "player_a" else 1,
            COMBAT_ZONE_ORDER[queued_effect.source_zone],
            queued_effect.source_position is None,
            -1 if queued_effect.source_position is None else queued_effect.source_position,
            str(queued_effect.source_instance_id),
            queued_effect.effect_key,
        )

    def _effect_payload(self, queued_effect: QueuedCombatEffect) -> dict[str, Any]:
        return {
            "phase": queued_effect.phase,
            "priority": queued_effect.priority,
            "owner_side": queued_effect.owner_side,
            "source_zone": queued_effect.source_zone,
            "source_position": queued_effect.source_position,
            "source_instance_id": queued_effect.source_instance_id,
            "effect_key": queued_effect.effect_key,
            "keyword_id": queued_effect.keyword_id,
            "keyword_display_name": queued_effect.keyword_display_name,
        }

    def _board_position(self, player: Player, instance_id: CardInstanceId) -> int:
        for index, card in enumerate(player.board.cards):
            if card.instance_id == instance_id:
                return index
        raise CombatResolutionError(f"Card is not on player board: {instance_id}.")

    def _side_for_player_id(self, context: CombatContext, player_id: PlayerId) -> CombatEffectOwnerSide:
        if player_id == context.player_a.player_id:
            return "player_a"
        if player_id == context.player_b.player_id:
            return "player_b"
        raise CombatResolutionError(f"Unknown combat player id: {player_id}.")

    def _opposite_side(self, side: CombatEffectOwnerSide) -> CombatEffectOwnerSide:
        return "player_b" if side == "player_a" else "player_a"

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.event_recorder is not None:
            self.event_recorder(event_type, payload)

