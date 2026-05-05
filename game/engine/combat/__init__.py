"""Combat resolution primitives."""

from game.engine.combat.combat import (
    CombatContext,
    CombatOutcome,
    CombatResolutionError,
    CombatResolver,
    CombatResult,
    QueuedCombatEffect,
)
from game.engine.combat.hit import HitContext, HitResolutionError, HitResolver, HitResult, QueuedHitEffect

__all__ = [
    "CombatContext",
    "CombatOutcome",
    "CombatResolutionError",
    "CombatResolver",
    "CombatResult",
    "HitContext",
    "HitResolutionError",
    "HitResolver",
    "HitResult",
    "QueuedCombatEffect",
    "QueuedHitEffect",
]
