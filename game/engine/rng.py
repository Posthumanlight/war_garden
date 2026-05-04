from __future__ import annotations

from collections.abc import MutableSequence, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

import numpy as np

from game.engine.events import EventLog, RngDrawEvent


RNG_ALGORITHM = "PCG64DXSM"
T = TypeVar("T")


@dataclass(slots=True)
class RngContext:
    """Audited deterministic RNG wrapper owned by a session."""

    seed: int
    event_log: EventLog
    _generator: np.random.Generator = field(init=False, repr=False)
    _draw_index: int = 0
    _state_version: int = 0

    def __post_init__(self) -> None:
        self._generator = np.random.Generator(np.random.PCG64DXSM(self.seed))

    @classmethod
    def from_state(cls, *, seed: int, state: dict[str, Any], event_log: EventLog) -> RngContext:
        rng = cls(seed=seed, event_log=event_log)
        rng.import_state(state)
        return rng

    def export_state(self) -> dict[str, Any]:
        return dict(self._generator.bit_generator.state)

    def import_state(self, state: dict[str, Any]) -> None:
        self._generator.bit_generator.state = state
        self._state_version += 1

    def coinflip(self, *, purpose: str) -> bool:
        result = bool(self._generator.integers(0, 2))
        self._record(
            purpose=purpose,
            method="coinflip",
            bounds={"low": 0, "high": 2},
            result=result,
        )
        return result

    def randint(self, low: int, high: int, *, purpose: str) -> int:
        if high <= low:
            raise ValueError("high must be greater than low.")
        result = int(self._generator.integers(low, high))
        self._record(
            purpose=purpose,
            method="randint",
            bounds={"low": low, "high": high},
            result=result,
        )
        return result

    def choice_index(self, size: int, *, purpose: str) -> int:
        if size <= 0:
            raise ValueError("Cannot choose from an empty collection.")
        result = int(self._generator.integers(0, size))
        self._record(
            purpose=purpose,
            method="choice_index",
            bounds={"size": size},
            result=result,
        )
        return result

    def choice_one(self, items: Sequence[T], *, purpose: str) -> T:
        index = self.choice_index(len(items), purpose=purpose)
        return items[index]

    def shuffle(self, items: MutableSequence[T], *, purpose: str) -> None:
        before_size = len(items)
        permutation = self._generator.permutation(before_size).tolist()
        shuffled = [items[index] for index in permutation]
        items[:] = shuffled
        self._record(
            purpose=purpose,
            method="shuffle",
            bounds={"size": before_size},
            result={"permutation": permutation},
        )

    def _record(self, *, purpose: str, method: str, bounds: dict[str, Any], result: Any) -> None:
        self._draw_index += 1
        self._state_version += 1
        self.event_log.add_rng_draw(
            RngDrawEvent(
                draw_index=self._draw_index,
                purpose=purpose,
                method=method,
                bounds=bounds,
                result=result,
                state_version=self._state_version,
            )
        )

