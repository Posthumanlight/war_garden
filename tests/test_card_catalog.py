from __future__ import annotations

from dataclasses import dataclass

import pytest

from game.cards import CardCatalogError, CreatureCard, EffectRegistry, load_card_catalog
from game.cards.catalog import parse_card_catalog
from game.engine.ids import CardId


def test_default_catalog_loads_knight() -> None:
    catalog = load_card_catalog()

    knight = catalog.get("creature.knight")

    assert isinstance(knight, CreatureCard)
    assert knight.name == "Knight"
    assert knight.tier == 1
    assert knight.attack == 2
    assert knight.health == 3
    assert knight.creature_types == ("Human", "Warrior")
    assert knight.effect_keys == (
        "knight.on_attack.attack_plus_1",
        "knight.bounty.health_plus_1",
    )


def test_catalog_lookup_accepts_string_and_card_id() -> None:
    catalog = load_card_catalog()

    by_string = catalog.get("creature.knight")
    by_card_id = catalog.get(CardId("creature.knight"))

    assert by_string == by_card_id


def test_loading_same_catalog_twice_produces_equivalent_definitions() -> None:
    first = load_card_catalog()
    second = load_card_catalog()

    assert first.all() == second.all()


def test_duplicate_card_ids_raise_catalog_error() -> None:
    raw_catalog = {
        "version": 1,
        "cards": [
            _creature_card("creature.knight"),
            _creature_card("creature.knight"),
        ],
    }

    with pytest.raises(CardCatalogError, match="Duplicate card id"):
        parse_card_catalog(raw_catalog)


def test_invalid_creature_health_raises_catalog_error() -> None:
    raw_catalog = {
        "version": 1,
        "cards": [_creature_card("creature.invalid", health=0)],
    }

    with pytest.raises(CardCatalogError, match="health"):
        parse_card_catalog(raw_catalog)


def test_negative_creature_attack_raises_catalog_error() -> None:
    raw_catalog = {
        "version": 1,
        "cards": [_creature_card("creature.invalid", attack=-1)],
    }

    with pytest.raises(CardCatalogError, match="attack"):
        parse_card_catalog(raw_catalog)


def test_bool_creature_stat_raises_catalog_error() -> None:
    raw_catalog = {
        "version": 1,
        "cards": [_creature_card("creature.invalid", attack=True)],
    }

    with pytest.raises(CardCatalogError, match="attack"):
        parse_card_catalog(raw_catalog)


def test_unknown_card_kind_raises_catalog_error() -> None:
    raw_catalog = {
        "version": 1,
        "cards": [
            {
                "id": "mystery.card",
                "kind": "mystery",
                "name": "Mystery",
            }
        ],
    }

    with pytest.raises(CardCatalogError, match="unknown kind"):
        parse_card_catalog(raw_catalog)


def test_unknown_effect_key_raises_when_registry_is_provided() -> None:
    raw_catalog = {
        "version": 1,
        "cards": [_creature_card("creature.effectful", effect_keys=["missing.effect"])],
    }

    with pytest.raises(CardCatalogError, match="Unknown effect keys"):
        parse_card_catalog(raw_catalog, effect_registry=EffectRegistry())


def test_known_effect_key_is_allowed_when_registry_is_provided() -> None:
    registry = EffectRegistry()
    registry.register("known.effect", _FakeEffect(key="known.effect"))
    raw_catalog = {
        "version": 1,
        "cards": [_creature_card("creature.effectful", effect_keys=["known.effect"])],
    }

    catalog = parse_card_catalog(raw_catalog, effect_registry=registry)

    assert catalog.get("creature.effectful").effect_keys == ("known.effect",)


def _creature_card(
    card_id: str,
    *,
    attack: int | bool = 2,
    health: int | bool = 3,
    effect_keys: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": card_id,
        "kind": "creature",
        "name": "Knight",
        "text": "",
        "tier": 1,
        "attack": attack,
        "health": health,
        "tags": [],
        "creature_types": ["Human", "Warrior"],
        "effect_keys": [] if effect_keys is None else effect_keys,
    }


@dataclass(frozen=True, slots=True)
class _FakeEffect:
    key: str
