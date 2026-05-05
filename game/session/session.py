from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.cards.card_effects import register_builtin_card_effects
from game.cards.catalog import CardCatalog, load_card_catalog
from game.cards.effects import EffectRegistry
from game.engine.events import EngineEvent, EventLog
from game.engine.ids import CardId, IdFactory, SessionId
from game.engine.rng import RNG_ALGORITHM, RngContext
from game.session.combat_manager import CombatManager
from game.session.shop_manager import ShopManager
from game.session.state_manager import StateManager


@dataclass(slots=True)
class GameSession:
    """Infrastructure composer for deterministic game sessions."""

    seed: int
    session_id: SessionId
    event_log: EventLog = field(default_factory=EventLog)
    id_factory: IdFactory = field(init=False)
    rng: RngContext = field(init=False)
    effect_registry: EffectRegistry = field(init=False)
    card_catalog: CardCatalog = field(init=False)
    state_manager: StateManager = field(init=False)
    combat_manager: CombatManager = field(init=False)
    shop_manager: ShopManager = field(init=False)

    def __post_init__(self) -> None:
        self.id_factory = IdFactory(session_id=self.session_id)
        self.rng = RngContext(seed=self.seed, event_log=self.event_log)
        self.effect_registry = EffectRegistry()
        register_builtin_card_effects(self.effect_registry)
        self.card_catalog = load_card_catalog(effect_registry=self.effect_registry)

        self.state_manager = StateManager(
            id_factory=self.id_factory,
            event_recorder=self.record_event,
        )
        self.shop_manager = ShopManager(
            event_recorder=self.record_event,
            card_catalog=self.card_catalog,
            rng=self.rng,
            id_factory=self.id_factory,
        )
        self.combat_manager = CombatManager(
            effect_registry=self.effect_registry,
            rng=self.rng,
            state_manager=self.state_manager,
            event_recorder=self.record_event,
        )
        self.state_manager.register_phase_node(self.shop_manager.create_phase_node())
        self.state_manager.register_phase_node(self.combat_manager.create_phase_node())

    def record_event(self, event_type: str, payload: dict[str, Any]) -> EngineEvent:
        event = EngineEvent(
            event_id=self.id_factory.next_event_id(),
            event_type=event_type,
            payload=payload,
        )
        self.event_log.add_event(event)
        return event

    def export_rng_state(self) -> dict[str, Any]:
        return self.rng.export_state()

    def snapshot_metadata(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "seed": self.seed,
            "phase": self.state_manager.current_node_id,
            "round_number": self.state_manager.round_number,
            "turn_number": self.state_manager.turn_number,
            "rng_algorithm": RNG_ALGORITHM,
            "player_count": len(self.state_manager.players),
            "active_player_count": len(self.state_manager.active_players()),
            "rng_draw_count": len(self.event_log.rng_draws),
        }


def card_id(value: str) -> CardId:
    return CardId(value)
