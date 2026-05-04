from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from game.cards.cards import Card, CreatureCard, SpellCard
from game.cards.effects import EffectRegistry
from game.engine.ids import CardId


CATALOG_VERSION = 1
DEFAULT_CARD_CATALOG_PATH = Path(__file__).parent / "content" / "catalog.toml"


class CardCatalogError(ValueError):
    """Raised when authored card content is invalid."""


@dataclass(frozen=True, slots=True)
class CardCatalog:
    _cards_by_id: dict[CardId, Card]

    def get(self, card_id: CardId | str) -> Card:
        normalized_id = CardId(str(card_id))
        try:
            return self._cards_by_id[normalized_id]
        except KeyError as exc:
            raise KeyError(f"Unknown card id: {normalized_id}") from exc

    def all(self) -> tuple[Card, ...]:
        return tuple(self._cards_by_id.values())

    def creatures(self) -> tuple[CreatureCard, ...]:
        return tuple(card for card in self._cards_by_id.values() if isinstance(card, CreatureCard))

    def spells(self) -> tuple[SpellCard, ...]:
        return tuple(card for card in self._cards_by_id.values() if isinstance(card, SpellCard))


def load_card_catalog(
    path: Path = DEFAULT_CARD_CATALOG_PATH,
    effect_registry: EffectRegistry | None = None,
) -> CardCatalog:
    with path.open("rb") as catalog_file:
        raw_catalog = tomllib.load(catalog_file)
    return parse_card_catalog(raw_catalog, effect_registry=effect_registry)


def parse_card_catalog(
    raw_catalog: dict[str, Any],
    effect_registry: EffectRegistry | None = None,
) -> CardCatalog:
    version = raw_catalog.get("version")
    if version is None:
        raise CardCatalogError("Card catalog is missing required field: version.")
    if version != CATALOG_VERSION:
        raise CardCatalogError(f"Unsupported card catalog version: {version!r}.")

    raw_cards = raw_catalog.get("cards")
    if not isinstance(raw_cards, list):
        raise CardCatalogError("Card catalog field 'cards' must be a list.")

    cards_by_id: dict[CardId, Card] = {}
    for index, raw_card in enumerate(raw_cards):
        if not isinstance(raw_card, dict):
            raise CardCatalogError(f"Card entry #{index} must be a table.")

        card = _parse_card(raw_card, index=index, effect_registry=effect_registry)
        if card.card_id in cards_by_id:
            raise CardCatalogError(f"Duplicate card id: {card.card_id}.")
        cards_by_id[card.card_id] = card

    return CardCatalog(cards_by_id)


def _parse_card(
    raw_card: dict[str, Any],
    *,
    index: int,
    effect_registry: EffectRegistry | None,
) -> Card:
    card_id = CardId(_required_str(raw_card, "id", index=index))
    kind = _required_str(raw_card, "kind", index=index)
    name = _required_str(raw_card, "name", index=index)
    text = _optional_str(raw_card, "text", default="")
    tier = _optional_tier(raw_card, "tier")
    tags = _string_tuple(raw_card, "tags", default=())
    effect_keys = _string_tuple(raw_card, "effect_keys", default=())
    _validate_effect_keys(effect_keys, effect_registry)

    if kind == "creature":
        attack = _required_int(raw_card, "attack", index=index)
        health = _required_int(raw_card, "health", index=index)
        creature_types = _string_tuple(raw_card, "creature_types", default=())
        return CreatureCard(
            card_id=card_id,
            name=name,
            text=text,
            tags=tags,
            tier=tier,
            effect_keys=effect_keys,
            attack=attack,
            health=health,
            creature_types=creature_types,
        )

    if kind == "spell":
        timing = _optional_str(raw_card, "timing", default="normal")
        target_rules = _string_tuple(raw_card, "target_rules", default=())
        return SpellCard(
            card_id=card_id,
            name=name,
            text=text,
            tags=tags,
            tier=tier,
            effect_keys=effect_keys,
            timing=timing,
            target_rules=target_rules,
        )

    raise CardCatalogError(f"Card entry #{index} has unknown kind: {kind!r}.")


def _required_str(raw_card: dict[str, Any], field_name: str, *, index: int) -> str:
    value = raw_card.get(field_name)
    if not isinstance(value, str) or not value:
        raise CardCatalogError(f"Card entry #{index} field '{field_name}' must be a non-empty string.")
    return value


def _optional_str(raw_card: dict[str, Any], field_name: str, *, default: str) -> str:
    value = raw_card.get(field_name, default)
    if not isinstance(value, str):
        raise CardCatalogError(f"Card field '{field_name}' must be a string.")
    return value


def _required_int(raw_card: dict[str, Any], field_name: str, *, index: int) -> int:
    value = raw_card.get(field_name)
    if not isinstance(value, int):
        raise CardCatalogError(f"Card entry #{index} field '{field_name}' must be an integer.")
    return value


def _optional_tier(raw_card: dict[str, Any], field_name: str) -> int | None:
    value = raw_card.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or value <= 0:
        raise CardCatalogError("Card field 'tier' must be a positive integer when present.")
    return value


def _string_tuple(raw_card: dict[str, Any], field_name: str, *, default: tuple[str, ...]) -> tuple[str, ...]:
    value = raw_card.get(field_name, list(default))
    if not isinstance(value, list):
        raise CardCatalogError(f"Card field '{field_name}' must be a list of strings.")
    if not all(isinstance(item, str) and item for item in value):
        raise CardCatalogError(f"Card field '{field_name}' must contain only non-empty strings.")
    return tuple(value)


def _validate_effect_keys(effect_keys: tuple[str, ...], effect_registry: EffectRegistry | None) -> None:
    if effect_registry is None:
        return

    unknown_keys = [effect_key for effect_key in effect_keys if not effect_registry.has(effect_key)]
    if unknown_keys:
        raise CardCatalogError(f"Unknown effect keys: {', '.join(unknown_keys)}.")

