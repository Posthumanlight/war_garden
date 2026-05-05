from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from middleware import GameManagerError, LobbyManager, LobbyManagerError, get_lobby_manager
from services.api.schemas import (
    AddPlayerRequest,
    BuyShopCardRequest,
    CombatRoundResponse,
    CreateSessionRequest,
    EventLogResponse,
    RngStateResponse,
    SellCardRequest,
    SessionSnapshotResponse,
    StateAdvanceResponse,
    SummonCardRequest,
    TransitionRequest,
    card_definition_response,
    combat_round_response,
    event_log_response,
    session_snapshot_response,
)


def create_app(lobby: LobbyManager | None = None) -> FastAPI:
    lobby_manager = lobby or get_lobby_manager()
    app = FastAPI(title="Random Garden API", version="0.1.0")
    app.state.lobby_manager = lobby_manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/catalog/cards")
    def list_cards() -> list[dict[str, Any]]:
        game = lobby_manager.catalog_game()
        return [card_definition_response(card).model_dump() for card in game.list_catalog_cards()]

    @app.get("/api/catalog/cards/{card_id}")
    def get_card(card_id: str) -> dict[str, Any]:
        try:
            return card_definition_response(lobby_manager.catalog_game().get_catalog_card(card_id)).model_dump()
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.post("/api/sessions", response_model=SessionSnapshotResponse)
    def create_session(request: CreateSessionRequest) -> SessionSnapshotResponse:
        try:
            game = lobby_manager.launch_game(seed=request.seed, session_id=request.session_id)
        except LobbyManagerError as exc:
            raise _lobby_http_error(exc) from exc
        return session_snapshot_response(game)

    @app.get("/api/sessions", response_model=list[SessionSnapshotResponse])
    def list_sessions() -> list[SessionSnapshotResponse]:
        return [session_snapshot_response(game) for game in lobby_manager.list_games()]

    @app.get("/api/sessions/{session_id}", response_model=SessionSnapshotResponse)
    def get_session(session_id: str) -> SessionSnapshotResponse:
        return session_snapshot_response(_game(lobby_manager, session_id))

    @app.delete("/api/sessions/{session_id}", response_model=SessionSnapshotResponse)
    def delete_session(session_id: str) -> SessionSnapshotResponse:
        try:
            return session_snapshot_response(lobby_manager.terminate_game(session_id))
        except LobbyManagerError as exc:
            raise _lobby_http_error(exc) from exc

    @app.post("/api/sessions/{session_id}/players", response_model=SessionSnapshotResponse)
    def add_player(session_id: str, request: AddPlayerRequest) -> SessionSnapshotResponse:
        game = _game(lobby_manager, session_id)
        game.add_player(request.name, max_health=request.max_health)
        return session_snapshot_response(game)

    @app.delete("/api/sessions/{session_id}/players/{player_id}", response_model=SessionSnapshotResponse)
    def remove_player(session_id: str, player_id: str) -> SessionSnapshotResponse:
        try:
            game = _game(lobby_manager, session_id)
            game.remove_player(player_id)
            return session_snapshot_response(game)
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.post("/api/sessions/{session_id}/players/{player_id}/summon", response_model=SessionSnapshotResponse)
    def summon_card(session_id: str, player_id: str, request: SummonCardRequest) -> SessionSnapshotResponse:
        try:
            game = _game(lobby_manager, session_id)
            game.summon_card(player_id, request.instance_id, position=request.position)
            return session_snapshot_response(game)
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.post("/api/sessions/{session_id}/state/advance", response_model=StateAdvanceResponse)
    def advance_state(session_id: str) -> StateAdvanceResponse:
        game = _game(lobby_manager, session_id)
        try:
            result = game.advance_phase()
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc
        return StateAdvanceResponse(
            executed_node_id=result.executed_node_id,
            next_node_id=result.next_node_id,
            round_number=result.round_number,
            turn_number=result.turn_number,
            session=session_snapshot_response(game),
        )

    @app.post("/api/sessions/{session_id}/state/transition", response_model=SessionSnapshotResponse)
    def transition_state(session_id: str, request: TransitionRequest) -> SessionSnapshotResponse:
        try:
            game = _game(lobby_manager, session_id)
            game.transition_phase(request.node_id)
            return session_snapshot_response(game)
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.post("/api/sessions/{session_id}/shop/start", response_model=SessionSnapshotResponse)
    def start_shop(session_id: str) -> SessionSnapshotResponse:
        game = _game(lobby_manager, session_id)
        game.start_shop()
        return session_snapshot_response(game)

    @app.post("/api/sessions/{session_id}/shop/end", response_model=SessionSnapshotResponse)
    def end_shop(session_id: str) -> SessionSnapshotResponse:
        game = _game(lobby_manager, session_id)
        game.end_shop()
        return session_snapshot_response(game)

    @app.post("/api/sessions/{session_id}/shop/buy", response_model=SessionSnapshotResponse)
    def buy_shop_card(session_id: str, request: BuyShopCardRequest) -> SessionSnapshotResponse:
        try:
            game = _game(lobby_manager, session_id)
            game.buy_shop_card(request.player_id, request.offer_index)
            return session_snapshot_response(game)
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.post("/api/sessions/{session_id}/shop/sell-from-hand", response_model=SessionSnapshotResponse)
    def sell_from_hand(session_id: str, request: SellCardRequest) -> SessionSnapshotResponse:
        try:
            game = _game(lobby_manager, session_id)
            game.sell_from_hand(request.player_id, request.instance_id)
            return session_snapshot_response(game)
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.post("/api/sessions/{session_id}/shop/sell-from-board", response_model=SessionSnapshotResponse)
    def sell_from_board(session_id: str, request: SellCardRequest) -> SessionSnapshotResponse:
        try:
            game = _game(lobby_manager, session_id)
            game.sell_from_board(request.player_id, request.instance_id)
            return session_snapshot_response(game)
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.post("/api/sessions/{session_id}/combat/round", response_model=CombatRoundResponse)
    def resolve_combat_round(session_id: str) -> CombatRoundResponse:
        try:
            game = _game(lobby_manager, session_id)
            result = game.resolve_combat_round()
            return combat_round_response(result, game)
        except GameManagerError as exc:
            raise _game_http_error(exc) from exc

    @app.get("/api/sessions/{session_id}/events", response_model=EventLogResponse)
    def get_events(session_id: str) -> EventLogResponse:
        return event_log_response(_game(lobby_manager, session_id))

    @app.get("/api/sessions/{session_id}/rng", response_model=RngStateResponse)
    def get_rng(session_id: str) -> RngStateResponse:
        game = _game(lobby_manager, session_id)
        metadata = game.snapshot_metadata()
        return RngStateResponse(
            algorithm=metadata["rng_algorithm"],
            draw_count=metadata["rng_draw_count"],
            state=game.export_rng_state(),
        )

    return app


def _game(lobby: LobbyManager, session_id: str):
    try:
        return lobby.get_game(session_id)
    except LobbyManagerError as exc:
        raise _lobby_http_error(exc) from exc


def _lobby_http_error(error: LobbyManagerError) -> HTTPException:
    message = str(error)
    if "already exists" in message:
        return HTTPException(status_code=409, detail=message)
    if "Unknown session" in message:
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


def _game_http_error(error: GameManagerError) -> HTTPException:
    message = str(error)
    if message.startswith("Unknown"):
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)
