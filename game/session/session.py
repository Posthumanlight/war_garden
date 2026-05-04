from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.cards.cards import Card, CardInstance
from game.engine.events import EngineEvent, EventLog
from game.engine.ids import CardId, IdFactory, PlayerId, SessionId
from game.engine.rng import RNG_ALGORITHM, RngContext
from game.players.player import Player


@dataclass(slots=True)
class GameSession:
    """Root owner of deterministic execution state."""

    seed: int
    session_id: SessionId
    phase: str = "setup"
    players: dict[PlayerId, Player] = field(default_factory=dict)
    event_log: EventLog = field(default_factory=EventLog)
    id_factory: IdFactory = field(init=False)
    rng: RngContext = field(init=False)

    def __post_init__(self) -> None:
        self.id_factory = IdFactory(session_id=self.session_id)
        self.rng = RngContext(seed=self.seed, event_log=self.event_log)

    def add_player(self, name: str) -> Player:
        player = Player(player_id=self.id_factory.next_player_id(), name=name)
        self.players[player.player_id] = player
        self.record_event("player.added", {"player_id": player.player_id, "name": player.name})
        return player

    def create_card_instance(
        self,
        *,
        definition: Card,
        owner_id: PlayerId,
        zone: str = "deck",
    ) -> CardInstance:
        instance = CardInstance(
            instance_id=self.id_factory.next_card_instance_id(),
            definition=definition,
            owner_id=owner_id,
            zone=zone,  # type: ignore[arg-type]
        )
        self.record_event(
            "card.instance.created",
            {
                "instance_id": instance.instance_id,
                "card_id": definition.card_id,
                "owner_id": owner_id,
                "zone": zone,
            },
        )
        return instance

    def add_card_to_player_deck(self, *, player_id: PlayerId, definition: Card) -> CardInstance:
        player = self.players[player_id]
        instance = self.create_card_instance(definition=definition, owner_id=player_id, zone="deck")
        player.deck.add_to_bottom(instance)
        self.record_event(
            "card.moved",
            {
                "instance_id": instance.instance_id,
                "owner_id": player_id,
                "to_zone": "deck",
            },
        )
        return instance

    def draw_card(self, player_id: PlayerId) -> CardInstance | None:
        player = self.players[player_id]
        card = player.draw_card()
        if card is None:
            self.record_event("deck.draw.empty", {"player_id": player_id})
            return None
        self.record_event(
            "card.moved",
            {
                "instance_id": card.instance_id,
                "owner_id": player_id,
                "from_zone": "deck",
                "to_zone": "hand",
            },
        )
        return card

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
            "phase": self.phase,
            "rng_algorithm": RNG_ALGORITHM,
            "player_count": len(self.players),
            "rng_draw_count": len(self.event_log.rng_draws),
        }


def card_id(value: str) -> CardId:
    return CardId(value)

