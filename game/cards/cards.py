from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from game.engine.ids import CardId, CardInstanceId, PlayerId


Zone = Literal["deck", "hand", "board", "graveyard"]


@dataclass(frozen=True, slots=True)
class Card:
    """Immutable card definition."""

    card_id: CardId
    name: str
    text: str = ""
    tags: tuple[str, ...] = ()
    tier: int | None = None
    rarity: str | None = None
    effect_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CreatureCard(Card):
    attack: int = 0
    health: int = 1
    creature_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.attack < 0:
            raise ValueError("Creature attack cannot be negative.")
        if self.health <= 0:
            raise ValueError("Creature health must be positive.")


@dataclass(frozen=True, slots=True)
class SpellCard(Card):
    timing: str = "normal"
    target_rules: tuple[str, ...] = ()


@dataclass(slots=True)
class CardInstance:
    """Mutable runtime state for one card definition."""

    instance_id: CardInstanceId
    definition: Card
    owner_id: PlayerId
    zone: Zone
    current_attack: int | None = None
    current_health: int | None = None
    damage: int = 0
    status_tags: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if isinstance(self.definition, CreatureCard):
            if self.current_attack is None:
                self.current_attack = self.definition.attack
            if self.current_health is None:
                self.current_health = self.definition.health
        elif self.current_attack is not None or self.current_health is not None:
            raise ValueError("Only creature instances can have combat stats.")

    @property
    def is_creature(self) -> bool:
        return isinstance(self.definition, CreatureCard)

    @property
    def is_spell(self) -> bool:
        return isinstance(self.definition, SpellCard)

    @property
    def is_alive(self) -> bool:
        return self.is_creature and self.current_health is not None and self.current_health > 0

    def take_damage(self, amount: int) -> None:
        if not self.is_creature or self.current_health is None:
            raise TypeError("Only creature instances can take damage.")
        if amount < 0:
            raise ValueError("Damage amount cannot be negative.")
        self.damage += amount
        self.current_health -= amount

    def move_to(self, zone: Zone) -> None:
        self.zone = zone
