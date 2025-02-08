# set_game/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from random import sample, shuffle

class Card(models.Model):
    number = models.IntegerField()
    symbol = models.CharField(max_length=20)
    shading = models.CharField(max_length=20)
    color = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.number} {self.shading} {self.color} {self.symbol}"

class Player(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class GameSession(models.Model):
    name = models.CharField(max_length=100)
    players = models.ManyToManyField(Player, related_name='game_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.JSONField(default=dict)

    def __str__(self):
        return self.name

    def initialize_game(self):
        deck = list(Card.objects.all())
        import os
        print("zsdcfg")
        print(os.getcwd())
        shuffle(deck)
        initial_board_cards = deck[:12]
        remaining_deck = deck[12:]

        state = {
            'deck': [str(card.id) for card in remaining_deck],
            'board': {str(i): str(card.id) for i, card in enumerate(initial_board_cards)},
            'selected_sets': [],  # Track which sets have been selected
            'scores': {str(player.id): 0 for player in self.players.all()}
        }
        self.state = state
        self.save()

    def validate_and_process_move(self, player, selected_cards):
        self.refresh_from_db()

        if 'selected_sets' not in self.state:
            raise KeyError("Key 'selected_sets' not found in state.")
        self.process_set(player, selected_cards)
        self.save()

    def validate_set(self, selected_cards):
        if len(selected_cards) != 3:
            return False

        cards = Card.objects.filter(id__in=selected_cards)

        if len(cards) != 3:
            return False

        return self.is_set(cards)

    def is_set(self, cards):
        if len(cards) != 3:
            return False

        card_list = list(cards.values('number', 'symbol', 'shading', 'color'))

        for attribute in ['number', 'symbol', 'shading', 'color']:
            if len(set([card[attribute] for card in card_list])) not in [1, 3]:
                return False

        return True

    def process_set(self, player, selected_cards):
        if not self.validate_set(selected_cards):
            raise ValidationError(f"The cards {selected_cards} are not a valid set")
        game_move = GameMove.objects.create(session=self, player=player)

        for card_id in selected_cards:
            card = Card.objects.get(id=card_id)
            game_move.cards.add(card)

        self.state['selected_sets'].append(selected_cards)
        self.state['scores'][str(player.id)] += 1

        # Remove selected cards from the board
        self.state['board'] = {pos: card_id for pos, card_id in self.state['board'].items() if all([card_id != selected_card for selected_card in selected_cards])}
        empty_positions = set(str(i) for i in range(12)).difference(set(self.state['board'].keys()))
        self.add_cards_to_board(3, empty_positions)
        self.save()

    def add_cards_to_board(self, count, empty_positions):
        new_cards = self.state['deck'][:count]
        self.state['deck'] = self.state['deck'][count:]

        for pos, card_id in zip(empty_positions, new_cards):
            self.state['board'][pos] = card_id


class GameMove(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    cards = models.ManyToManyField(Card, related_name='moves')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Move by {self.player} in {self.session}"


class Lobby(models.Model):
    player1 = models.ForeignKey(User, related_name='lobby_player1', on_delete=models.CASCADE)
    player2 = models.ForeignKey(User, related_name='lobby_player2', on_delete=models.CASCADE, null=True, blank=True)
    player1_ready = models.BooleanField(default=False)
    player2_ready = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_full(self):
        return self.player2 is not None

    def all_ready(self):
        return self.player1_ready and self.player2_ready

class GameState(models.Model):
    # lobby = models.OneToOneField(Lobby, on_delete=models.CASCADE)
    lobby = models.OneToOneField(Lobby, on_delete=models.CASCADE, related_name='game_state')
    state_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
