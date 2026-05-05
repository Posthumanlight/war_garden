"""Low-level deterministic engine utilities."""

from game.engine.combat import (
    CombatContext,
    CombatOutcome,
    CombatResolutionError,
    CombatResolver,
    CombatResult,
    HitContext,
    HitResolutionError,
    HitResolver,
    HitResult,
    QueuedCombatEffect,
    QueuedHitEffect,
)
from game.engine.events import EngineEvent, EventLog, RngDrawEvent
from game.engine.ids import CardId, CardInstanceId, EventId, IdFactory, PlayerId, SessionId
from game.engine.rng import RNG_ALGORITHM, RngContext

__all__ = [
    "CardId",
    "CardInstanceId",
    "CombatContext",
    "CombatOutcome",
    "CombatResolutionError",
    "CombatResolver",
    "CombatResult",
    "EngineEvent",
    "EventId",
    "EventLog",
    "HitContext",
    "HitResolutionError",
    "HitResolver",
    "HitResult",
    "IdFactory",
    "PlayerId",
    "QueuedCombatEffect",
    "QueuedHitEffect",
    "RNG_ALGORITHM",
    "RngContext",
    "RngDrawEvent",
    "SessionId",
]
