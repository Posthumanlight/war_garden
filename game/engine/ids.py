from __future__ import annotations

from dataclasses import dataclass, field
from typing import NewType


SessionId = NewType("SessionId", str)
PlayerId = NewType("PlayerId", str)
CardId = NewType("CardId", str)
CardInstanceId = NewType("CardInstanceId", str)
EventId = NewType("EventId", str)


@dataclass(slots=True)
class IdFactory:
    """Deterministic per-session ID generator."""

    session_id: SessionId
    counters: dict[str, int] = field(default_factory=dict)

    def next_player_id(self) -> PlayerId:
        return PlayerId(self._next("player"))

    def next_card_instance_id(self) -> CardInstanceId:
        return CardInstanceId(self._next("card-instance"))

    def next_event_id(self) -> EventId:
        return EventId(self._next("event"))

    def _next(self, namespace: str) -> str:
        next_value = self.counters.get(namespace, 0) + 1
        self.counters[namespace] = next_value
        return f"{self.session_id}:{namespace}:{next_value}"

