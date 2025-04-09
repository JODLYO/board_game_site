from typing import List
from set_game.models import Card


def validate_set(card1: Card, card2: Card, card3: Card) -> bool:
    """
    Validate if three cards form a set according to SET game rules.
    """
    attributes: List[str] = ["number", "symbol", "shading", "color"]
    for attr in attributes:
        if len({getattr(card1, attr), getattr(card2, attr), getattr(card3, attr)}) == 2:
            return False
    return True
