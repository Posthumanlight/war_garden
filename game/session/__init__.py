"""Game session root objects."""

from game.session.combat_manager import CombatManager, CombatPair, CombatPairingResult, CombatRoundResult
from game.session.session import GameSession
from game.session.shop_manager import ShopManager
from game.session.state_manager import PhaseContext, PhaseNode, PhaseTransitionResult, StateManager

__all__ = [
    "CombatManager",
    "CombatPair",
    "CombatPairingResult",
    "CombatRoundResult",
    "GameSession",
    "PhaseContext",
    "PhaseNode",
    "PhaseTransitionResult",
    "ShopManager",
    "StateManager",
]
