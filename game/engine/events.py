from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.engine.ids import EventId


@dataclass(frozen=True, slots=True)
class EngineEvent:
    event_id: EventId
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RngDrawEvent:
    draw_index: int
    purpose: str
    method: str
    bounds: dict[str, Any]
    result: Any
    state_version: int


@dataclass(slots=True)
class EventLog:
    events: list[EngineEvent] = field(default_factory=list)
    rng_draws: list[RngDrawEvent] = field(default_factory=list)

    def add_event(self, event: EngineEvent) -> None:
        self.events.append(event)

    def add_rng_draw(self, draw: RngDrawEvent) -> None:
        self.rng_draws.append(draw)

