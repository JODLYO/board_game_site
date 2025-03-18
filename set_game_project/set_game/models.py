from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from random import sample, shuffle
from itertools import combinations

import traceback
import datetime

def set_state(game, new_state):
    print(f"🔄 Changing state of GameSession {game.id} at {datetime.now()}")
    print(f"📍 Stack trace:\n{''.join(traceback.format_stack())}")
    game.state = new_state

class Card(models.Model):
    number = models.IntegerField()
    symbol = models.CharField(max_length=20)
    shading = models.CharField(max_length=20)
    color = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.number} {self.shading} {self.color} {self.symbol}"


class GameSession(models.Model):
    name = models.CharField(max_length=100)
    players = models.ManyToManyField(User, related_name='game_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.JSONField(default=dict)

    def __str__(self):
        return self.name

    def initialize_game(self):
        deck = list(Card.objects.all())
        shuffle(deck)
        initial_board_cards = deck[:12]
        remaining_deck = deck[12:]
        scores = {str(player.username): 0 for player in self.players.all()}

        state = {
            'deck': [str(card.id) for card in remaining_deck],
            'board': {str(i): str(card.id) for i, card in enumerate(initial_board_cards)},
            'selected_sets': [],
            'scores': scores
        }
        self.state = state
        self.save()

    def validate_and_process_move(self, player, selected_cards):
        self.refresh_from_db()
        if 'selected_sets' not in self.state:
            raise KeyError("Key 'selected_sets' not found in state.")
        self.process_set(player, selected_cards)
        if not self.state['deck'] and not self.is_set_available():
            self.end_game()
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
        self.state['scores'][str(player.username)] += 1
        print(f"🔄 Updated state before save: {self.state}")
        self.save()
        print(f"💾 Saved state: {self.state}")


        # Remove selected cards from the board
        self.state['board'] = {
            pos: card_id for pos, card_id in self.state['board'].items()
            if card_id not in selected_cards
        }
            # If the board has more 12 or more cards, move cards from positions 13-15 to fill empty positions
        if len(self.state['board']) >= 12:
            empty_positions = sorted(set(str(i) for i in range(12)) - self.state['board'].keys(), key=int)
            extra_positions = sorted(self.state['board'].keys(), key=int)[-len(empty_positions):]  # Get positions beyond 12

            # Move cards from extra positions to empty positions
            for empty_pos, extra_pos in zip(empty_positions, extra_positions):
                self.state['board'][empty_pos] = self.state['board'].pop(extra_pos)
        else:
            empty_positions = set(str(i) for i in range(12)).difference(set(self.state['board'].keys()))
            empty_positions = sorted(empty_positions, key=int)
            self.add_cards_to_board(3, empty_positions)
        self.handle_no_set_available()
        self.save()

    def add_cards_to_board(self, count, empty_positions):
        new_cards = self.state['deck'][:count]
        self.state['deck'] = self.state['deck'][count:]
        for pos, card_id in zip(empty_positions, new_cards):
            self.state['board'][pos] = card_id

    def is_set_available(self):
        # Get all card IDs on the board
        card_ids = list(self.state['board'].values())
        if len(card_ids) < 3:
            return False

        # Check all combinations of 3 cards
        for combo in combinations(card_ids, 3):
            if self.validate_set(combo):
                return True
        return False
    
    def handle_no_set_available(self):
        """
        Add 3 new cards to the board if no valid set is available.
        """
        if not self.is_set_available():
            if self.state['deck']:
                # Find the next available positions (e.g., 12, 13, 14)
                next_positions = [str(i) for i in range(len(self.state['board']), len(self.state['board']) + 3)]
                self.add_cards_to_board(3, next_positions)
            else:
                self.end_game()
        
    def end_game(self):
        self.state['game_over'] = True
        self.save()


class GameMove(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    cards = models.ManyToManyField(Card, related_name='moves')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Move by {self.player} in {self.session}"


class Lobby(models.Model):
    players = models.ManyToManyField(User, through='LobbyPlayer')
    created_at = models.DateTimeField(auto_now_add=True)

    def is_full(self):
        return self.players.count() >= 2  # Adjust this for your game's player limit

    def all_ready(self):
        return all(lobby_player.ready for lobby_player in self.lobbyplayer_set.all())

    def __str__(self):
        return f"Lobby {self.id}"
    
class LobbyPlayer(models.Model):
    lobby = models.ForeignKey(Lobby, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    ready = models.BooleanField(default=False)

    class Meta:
        unique_together = ('lobby', 'player')  # Ensure a player can only join a lobby once

    def __str__(self):
        return f"{self.player.username} in Lobby {self.lobby.id}"

class GameState(models.Model):
    lobby = models.OneToOneField(Lobby, on_delete=models.CASCADE, related_name='game_state')
    state_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
