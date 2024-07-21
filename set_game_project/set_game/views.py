from django.shortcuts import render
from .models import Card

def home(request):
    return render(request, 'set_game/home.html')


def game_board(request):
    # Fetch some cards to display (for now, fetch the first 12 cards)
    cards = Card.objects.all()[:12]
    return render(request, 'set_game/game_board.html', {'cards': cards})
