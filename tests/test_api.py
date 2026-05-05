from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

import services.api.app as api_app
from middleware import LobbyManager
from services.api.app import create_app


def test_health_endpoint_returns_ok() -> None:
    client = _client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_catalog_endpoint_exposes_knight() -> None:
    client = _client()

    response = client.get("/api/catalog/cards")

    assert response.status_code == 200
    cards = response.json()
    knight = next(card for card in cards if card["card_id"] == "creature.knight")
    assert knight["kind"] == "creature"
    assert knight["attack"] == 2
    assert knight["health"] == 3


def test_create_session_and_add_player() -> None:
    client = _client()
    session_id = _create_session(client)

    response = client.post(f"/api/sessions/{session_id}/players", json={"name": "Alice"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["player_count"] == 1
    assert payload["players"][0]["name"] == "Alice"
    assert payload["players"][0]["health"] == 50


def test_shop_buy_summon_and_combat_round_flow() -> None:
    client = _client()
    session_id = _create_session(client)
    first_player_id = _add_player(client, session_id, "Alice")
    second_player_id = _add_player(client, session_id, "Bob")

    shop_response = client.post(f"/api/sessions/{session_id}/shop/start")
    assert shop_response.status_code == 200

    first_bought = _buy_first_offer(client, session_id, first_player_id)
    second_bought = _buy_first_offer(client, session_id, second_player_id)

    first_summon = client.post(
        f"/api/sessions/{session_id}/players/{first_player_id}/summon",
        json={"instance_id": first_bought},
    )
    second_summon = client.post(
        f"/api/sessions/{session_id}/players/{second_player_id}/summon",
        json={"instance_id": second_bought},
    )
    assert first_summon.status_code == 200
    assert second_summon.status_code == 200

    combat_response = client.post(f"/api/sessions/{session_id}/combat/round")

    assert combat_response.status_code == 200
    payload = combat_response.json()
    assert payload["pair_results"]
    assert payload["session"]["events"]["events"]


def test_events_and_rng_endpoints_expose_session_debug_data() -> None:
    client = _client()
    session_id = _create_session(client)
    _add_player(client, session_id, "Alice")

    events_response = client.get(f"/api/sessions/{session_id}/events")
    rng_response = client.get(f"/api/sessions/{session_id}/rng")

    assert events_response.status_code == 200
    assert events_response.json()["events"]
    assert rng_response.status_code == 200
    assert rng_response.json()["algorithm"] == "PCG64DXSM"


def test_delete_session_returns_final_snapshot_and_removes_active_game() -> None:
    lobby = LobbyManager()
    client = TestClient(create_app(lobby))
    session_id = _create_session(client)
    _add_player(client, session_id, "Alice")

    response = client.delete(f"/api/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["metadata"]["player_count"] == 1
    assert not lobby.has_game(session_id)


def test_api_routes_do_not_use_session_store_or_game_session_managers_directly() -> None:
    source = inspect.getsource(api_app)

    assert "SessionStore" not in source
    assert ".state_manager" not in source
    assert ".shop_manager" not in source
    assert ".combat_manager" not in source


def _client() -> TestClient:
    return TestClient(create_app(LobbyManager()))


def _create_session(client: TestClient) -> str:
    response = client.post("/api/sessions", json={"seed": 11})
    assert response.status_code == 200
    return response.json()["metadata"]["session_id"]


def _add_player(client: TestClient, session_id: str, name: str) -> str:
    response = client.post(f"/api/sessions/{session_id}/players", json={"name": name})
    assert response.status_code == 200
    return response.json()["players"][-1]["player_id"]


def _buy_first_offer(client: TestClient, session_id: str, player_id: str) -> str:
    response = client.post(
        f"/api/sessions/{session_id}/shop/buy",
        json={"player_id": player_id, "offer_index": 0},
    )
    assert response.status_code == 200
    player = next(player for player in response.json()["players"] if player["player_id"] == player_id)
    return player["hand"][-1]["instance_id"]
