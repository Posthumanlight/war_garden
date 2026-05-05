from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from game.cards.cards import CardInstance
    from game.engine.combat.combat import CombatContext
    from game.engine.combat.hit import HitContext


HitEffectPhase = Literal["before_damage", "after_damage", "after_death"]
EffectSourceSide = Literal["attacker", "defender"]
CombatEffectPhase = Literal["start_combat", "end_combat"]
CombatEffectSourceZone = Literal["board", "hand", "deck", "graveyard"]
CombatEffectOwnerSide = Literal["player_a", "player_b"]


class CardEffect(Protocol):
    """Marker protocol for future Python-backed card effects."""

    key: str


@dataclass(frozen=True, slots=True)
class EffectKeyword:
    keyword_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class EffectConditions:
    source_must_be_attacker: bool | None = None
    source_must_be_defender: bool | None = None
    source_must_be_alive: bool | None = None
    target_must_be_alive: bool | None = None

    def matches_static(self, *, source_side: EffectSourceSide) -> bool:
        if self.source_must_be_attacker is True and source_side != "attacker":
            return False
        if self.source_must_be_attacker is False and source_side == "attacker":
            return False
        if self.source_must_be_defender is True and source_side != "defender":
            return False
        if self.source_must_be_defender is False and source_side == "defender":
            return False
        return True

    def matches(self, *, context: HitContext, source: CardInstance, source_side: EffectSourceSide) -> bool:
        if not self.matches_static(source_side=source_side):
            return False

        if self.source_must_be_alive is not None and source.is_alive != self.source_must_be_alive:
            return False

        target = context.defender if source_side == "attacker" else context.attacker
        if self.target_must_be_alive is not None and target.is_alive != self.target_must_be_alive:
            return False

        return True


@dataclass(frozen=True, slots=True)
class CombatEffectConditions:
    source_zones: tuple[CombatEffectSourceZone, ...] = ("board", "hand", "deck", "graveyard")
    source_owner_side: CombatEffectOwnerSide | None = None
    source_must_be_alive_when_on_board: bool | None = None
    owner_must_have_living_board_cards: bool | None = None
    opponent_must_have_living_board_cards: bool | None = None

    def matches_static(self, *, owner_side: CombatEffectOwnerSide, source_zone: CombatEffectSourceZone) -> bool:
        if source_zone not in self.source_zones:
            return False
        if self.source_owner_side is not None and owner_side != self.source_owner_side:
            return False
        return True

    def matches(
        self,
        *,
        context: CombatContext,
        source: CardInstance,
        owner_side: CombatEffectOwnerSide,
        source_zone: CombatEffectSourceZone,
    ) -> bool:
        if not self.matches_static(owner_side=owner_side, source_zone=source_zone):
            return False

        if (
            source_zone == "board"
            and self.source_must_be_alive_when_on_board is not None
            and source.is_alive != self.source_must_be_alive_when_on_board
        ):
            return False

        owner = context.player_for_side(owner_side)
        opponent = context.opponent_for_side(owner_side)
        if (
            self.owner_must_have_living_board_cards is not None
            and bool(owner.board.living_cards()) != self.owner_must_have_living_board_cards
        ):
            return False
        if (
            self.opponent_must_have_living_board_cards is not None
            and bool(opponent.board.living_cards()) != self.opponent_must_have_living_board_cards
        ):
            return False

        return True


@runtime_checkable
class OnHitEffect(CardEffect, Protocol):
    keyword: EffectKeyword
    phase: HitEffectPhase
    priority: int
    conditions: EffectConditions

    def execute_hit_effect(self, context: HitContext, source: CardInstance) -> None:
        """Apply this effect to a source card during hit resolution."""


@runtime_checkable
class OnCombatEffect(CardEffect, Protocol):
    keyword: EffectKeyword
    phase: CombatEffectPhase
    priority: int
    conditions: CombatEffectConditions

    def execute_combat_effect(self, context: CombatContext, source: CardInstance) -> None:
        """Apply this effect during start/end combat resolution."""


@dataclass(slots=True)
class EffectRegistry:
    _effects: dict[str, CardEffect] = field(default_factory=dict)

    def register(self, key: str, effect: CardEffect) -> None:
        if not key:
            raise ValueError("Effect key cannot be empty.")
        if key in self._effects:
            raise ValueError(f"Effect key is already registered: {key}.")
        self._effects[key] = effect

    def has(self, key: str) -> bool:
        return key in self._effects

    def get(self, key: str) -> CardEffect:
        try:
            return self._effects[key]
        except KeyError as exc:
            raise KeyError(f"Unknown effect key: {key}.") from exc

    def get_on_hit_effect(self, key: str) -> OnHitEffect:
        effect = self.get(key)
        if not isinstance(effect, OnHitEffect):
            raise TypeError(f"Effect key is not an on-hit effect: {key}.")
        return effect

    def get_combat_effect(self, key: str) -> OnCombatEffect:
        effect = self.get(key)
        if not isinstance(effect, OnCombatEffect):
            raise TypeError(f"Effect key is not a combat effect: {key}.")
        return effect
