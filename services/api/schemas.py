from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from game.cards.cards import Card, CardInstance, CreatureCard, SpellCard
from game.engine.combat import CombatResult
from game.engine.events import EngineEvent, RngDrawEvent
from game.session.combat_manager import CombatRoundResult
from game.session.session import GameSession
from middleware.game_manager import GameManager


class CreateSessionRequest(BaseModel):
    seed: int = 1
    session_id: str | None = None


class AddPlayerRequest(BaseModel):
    name: str = Field(min_length=1)
    max_health: int = Field(default=50, gt=0)


class TransitionRequest(BaseModel):
    node_id: str = Field(min_length=1)


class BuyShopCardRequest(BaseModel):
    player_id: str
    offer_index: int = Field(ge=0)


class SellCardRequest(BaseModel):
    player_id: str
    instance_id: str


class SummonCardRequest(BaseModel):
    instance_id: str
    position: int | None = Field(default=None, ge=0)


class CardDefinitionResponse(BaseModel):
    card_id: str
    kind: Literal["card", "creature", "spell"]
    name: str
    text: str
    tags: list[str]
    tier: int | None
    rarity: str | None
    effect_keys: list[str]
    attack: int | None = None
    health: int | None = None
    creature_types: list[str] = Field(default_factory=list)
    timing: str | None = None
    target_rules: list[str] = Field(default_factory=list)


class CardInstanceResponse(BaseModel):
    instance_id: str
    card_id: str
    name: str
    kind: Literal["card", "creature", "spell"]
    owner_id: str
    zone: str
    current_attack: int | None
    current_health: int | None
    damage: int
    status_tags: list[str]


class PlayerResponse(BaseModel):
    player_id: str
    name: str
    health: int
    max_health: int
    is_defeated: bool
    board: list[CardInstanceResponse]
    hand: list[CardInstanceResponse]
    deck: list[CardInstanceResponse]
    graveyard: list[CardInstanceResponse]


class EconomyResponse(BaseModel):
    gold: int
    gold_per_round: int


class ShopOfferResponse(BaseModel):
    player_id: str
    cards: list[CardInstanceResponse]


class PlayerShopResponse(BaseModel):
    player_id: str
    economy: EconomyResponse | None
    offer: ShopOfferResponse | None


class SessionMetadataResponse(BaseModel):
    session_id: str
    seed: int
    phase: str | None
    round_number: int
    turn_number: int
    rng_algorithm: str
    player_count: int
    active_player_count: int
    rng_draw_count: int


class EventResponse(BaseModel):
    event_id: str
    event_type: str
    payload: dict[str, Any]


class RngDrawResponse(BaseModel):
    draw_index: int
    purpose: str
    method: str
    bounds: dict[str, Any]
    result: Any
    state_version: int


class EventLogResponse(BaseModel):
    events: list[EventResponse]
    rng_draws: list[RngDrawResponse]


class SessionSnapshotResponse(BaseModel):
    metadata: SessionMetadataResponse
    players: list[PlayerResponse]
    shops: list[PlayerShopResponse]
    events: EventLogResponse


class StateAdvanceResponse(BaseModel):
    executed_node_id: str
    next_node_id: str
    round_number: int
    turn_number: int
    session: SessionSnapshotResponse


class CombatResultResponse(BaseModel):
    outcome: str
    winner_player_id: str | None
    player_a_id: str
    player_b_id: str
    steps: int
    max_steps_reached: bool
    destroyed_instance_ids: list[str]
    player_a_living_count: int
    player_b_living_count: int


class PairCombatResultResponse(BaseModel):
    player_a_id: str
    player_b_id: str
    combat_result: CombatResultResponse


class CombatRoundResponse(BaseModel):
    pair_results: list[PairCombatResultResponse]
    bye_player_id: str | None
    defeated_player_ids: list[str]
    session: SessionSnapshotResponse


class RngStateResponse(BaseModel):
    algorithm: str
    draw_count: int
    state: dict[str, Any]


def card_definition_response(card: Card) -> CardDefinitionResponse:
    kind: Literal["card", "creature", "spell"] = "card"
    attack: int | None = None
    health: int | None = None
    creature_types: list[str] = []
    timing: str | None = None
    target_rules: list[str] = []

    if isinstance(card, CreatureCard):
        kind = "creature"
        attack = card.attack
        health = card.health
        creature_types = list(card.creature_types)
    elif isinstance(card, SpellCard):
        kind = "spell"
        timing = card.timing
        target_rules = list(card.target_rules)

    return CardDefinitionResponse(
        card_id=str(card.card_id),
        kind=kind,
        name=card.name,
        text=card.text,
        tags=list(card.tags),
        tier=card.tier,
        rarity=card.rarity,
        effect_keys=list(card.effect_keys),
        attack=attack,
        health=health,
        creature_types=creature_types,
        timing=timing,
        target_rules=target_rules,
    )


def card_instance_response(card: CardInstance) -> CardInstanceResponse:
    definition = card.definition
    kind: Literal["card", "creature", "spell"] = "card"
    if isinstance(definition, CreatureCard):
        kind = "creature"
    elif isinstance(definition, SpellCard):
        kind = "spell"
    return CardInstanceResponse(
        instance_id=str(card.instance_id),
        card_id=str(definition.card_id),
        name=definition.name,
        kind=kind,
        owner_id=str(card.owner_id),
        zone=card.zone,
        current_attack=card.current_attack,
        current_health=card.current_health,
        damage=card.damage,
        status_tags=sorted(card.status_tags),
    )


def session_snapshot_response(source: GameManager | GameSession) -> SessionSnapshotResponse:
    session = _session_from_source(source)
    return SessionSnapshotResponse(
        metadata=SessionMetadataResponse(**_to_jsonable(session.snapshot_metadata())),
        players=[_player_response(player) for player in session.state_manager.players.values()],
        shops=[_player_shop_response(session, player_id) for player_id in session.state_manager.players],
        events=event_log_response(source),
    )


def event_log_response(source: GameManager | GameSession) -> EventLogResponse:
    session = _session_from_source(source)
    return EventLogResponse(
        events=[event_response(event) for event in session.event_log.events],
        rng_draws=[rng_draw_response(draw) for draw in session.event_log.rng_draws],
    )


def event_response(event: EngineEvent) -> EventResponse:
    return EventResponse(
        event_id=str(event.event_id),
        event_type=event.event_type,
        payload=_to_jsonable(event.payload),
    )


def rng_draw_response(draw: RngDrawEvent) -> RngDrawResponse:
    return RngDrawResponse(
        draw_index=draw.draw_index,
        purpose=draw.purpose,
        method=draw.method,
        bounds=_to_jsonable(draw.bounds),
        result=_to_jsonable(draw.result),
        state_version=draw.state_version,
    )


def combat_round_response(result: CombatRoundResult, source: GameManager | GameSession) -> CombatRoundResponse:
    return CombatRoundResponse(
        pair_results=[
            PairCombatResultResponse(
                player_a_id=str(pair_result.pair.player_a.player_id),
                player_b_id=str(pair_result.pair.player_b.player_id),
                combat_result=combat_result_response(pair_result.combat_result),
            )
            for pair_result in result.pair_results
        ],
        bye_player_id=None if result.bye_player_id is None else str(result.bye_player_id),
        defeated_player_ids=[str(player_id) for player_id in result.defeated_player_ids],
        session=session_snapshot_response(source),
    )


def combat_result_response(result: CombatResult) -> CombatResultResponse:
    return CombatResultResponse(
        outcome=result.outcome,
        winner_player_id=None if result.winner_player_id is None else str(result.winner_player_id),
        player_a_id=str(result.player_a_id),
        player_b_id=str(result.player_b_id),
        steps=result.steps,
        max_steps_reached=result.max_steps_reached,
        destroyed_instance_ids=[str(instance_id) for instance_id in result.destroyed_instance_ids],
        player_a_living_count=result.player_a_living_count,
        player_b_living_count=result.player_b_living_count,
    )


def _player_response(player) -> PlayerResponse:
    return PlayerResponse(
        player_id=str(player.player_id),
        name=player.name,
        health=player.health,
        max_health=player.max_health,
        is_defeated=player.is_defeated,
        board=[card_instance_response(card) for card in player.board.cards],
        hand=[card_instance_response(card) for card in player.hand.cards],
        deck=[card_instance_response(card) for card in player.deck.cards],
        graveyard=[card_instance_response(card) for card in player.graveyard.cards],
    )


def _player_shop_response(session: GameSession, player_id) -> PlayerShopResponse:
    economy = session.shop_manager.economies.get(player_id)
    offer = session.shop_manager.offers.get(player_id)
    return PlayerShopResponse(
        player_id=str(player_id),
        economy=None
        if economy is None
        else EconomyResponse(gold=economy.gold, gold_per_round=economy.gold_per_round),
        offer=None
        if offer is None
        else ShopOfferResponse(
            player_id=str(offer.player_id),
            cards=[card_instance_response(card) for card in offer.cards],
        ),
    )


def _session_from_source(source: GameManager | GameSession) -> GameSession:
    if isinstance(source, GameManager):
        return source.session
    return source


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if hasattr(value, "item"):
        return value.item()
    return value
