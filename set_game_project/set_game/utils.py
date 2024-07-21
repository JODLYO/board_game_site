# set_game/utils.py

def validate_set(card1, card2, card3):
    """
    Validate if three cards form a set according to SET game rules.
    """
    attributes = ['number', 'symbol', 'shading', 'color']
    for attr in attributes:
        if len({getattr(card1, attr), getattr(card2, attr), getattr(card3, attr)}) == 2:
            return False
    return True
