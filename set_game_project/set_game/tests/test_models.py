from django.test import TestCase
from django.contrib.auth.models import User
from set_game.models import Card, GameSession, Lobby, LobbyPlayer, GameMove
from unittest.mock import patch
from django.core.management import call_command

class CardModelTest(TestCase):
    def test_card_creation(self):
        card = Card.objects.create(number=1, symbol='oval', shading='solid', color='red')
        self.assertEqual(str(card), "1 solid red oval")

class GameSessionModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Runs once for the test class"""

        # Ensure cards are in the test database BEFORE mocking
        if not Card.objects.exists():
            call_command("populate_cards")
        cls.cards = Card.objects.all()

        cls.player1 = User.objects.create_user(username="player1")
        cls.player2 = User.objects.create_user(username="player2")

        cls.session = GameSession.objects.create(name="Test Game")
        cls.session.players.set([cls.player1, cls.player2])
        cls.session.initialize_game()
    
    def test_initialize_game(self):
        self.session.initialize_game()
        self.assertEqual(len(self.session.state['board']), 12)
        self.assertGreater(len(self.session.state['deck']), 0)
        self.assertEqual(self.session.state['scores'][self.player1.username], 0)
    
    def test_validate_sets(self):
        """(1, diamond, solid, red) → ID 1
        (2, squiggle, striped, green) → ID 41
        (3, oval, open, purple) → ID 81"""
        all_different_set = [1, 41, 81]
        self.assertTrue(self.session.validate_set(all_different_set))

        """Same Symbol, Different Everything Else
            (1, squiggle, solid, red) → ID 10
            (2, squiggle, striped, green) → ID 41
            (3, squiggle, open, purple) → ID 72"""
        same_symbol_else_different = [10, 41, 72]
        self.assertTrue(self.session.validate_set(same_symbol_else_different))

        """(1, diamond, solid, red) → ID 1
        (2, squiggle, striped, red) → ID 40
        (3, oval, open, red) → ID 79"""
        same_colour_else_different = [1, 40, 79]
        self.assertTrue(self.session.validate_set(same_colour_else_different))

        """(1, diamond, solid, red) → ID 1
        (1, squiggle, striped, green) → ID 14
        (1, oval, open, purple) → ID 27"""
        same_no_else_different = [1, 14, 27]
        self.assertTrue(self.session.validate_set(same_no_else_different))

        """(1, diamond, solid, red) → ID 1
        (2, squiggle, solid, green) → ID 38
        (3, oval, solid, purple) → ID 75"""
        same_shading_else_different = [1, 38, 75]
        self.assertTrue(self.session.validate_set(same_shading_else_different))

        """(1, diamond, solid, red) → ID 1
        (1, diamond, solid, green) → ID 2
        (1, diamond, striped, red) → ID 75"""
        not_set = [1, 2, 75]
        self.assertFalse(self.session.validate_set(not_set))

        two_cards = [1, 2]
        self.assertFalse(self.session.validate_set(two_cards))

        four_cards = [1, 38, 75, 76]
        self.assertFalse(self.session.validate_set(four_cards))

    def test_process_set(self):
        self.session.initialize_game()
        selected_cards = [str(card.id) for card in self.cards[:3]]
        self.session.process_set(self.player1, selected_cards)
        
        self.assertIn(selected_cards, self.session.state['selected_sets'])
        self.assertEqual(self.session.state['scores'][self.player1.username], 1)
    
    def test_end_game(self):
        self.session.end_game()
        self.assertTrue(self.session.state['game_over'])
    
class LobbyModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='player1')
        self.user2 = User.objects.create(username='player2')
        self.lobby = Lobby.objects.create()
        LobbyPlayer.objects.create(lobby=self.lobby, player=self.user1, ready=True)
        LobbyPlayer.objects.create(lobby=self.lobby, player=self.user2, ready=True)
    
    def test_lobby_is_full(self):
        self.assertTrue(self.lobby.is_full())
    
    def test_lobby_all_ready(self):
        self.assertTrue(self.lobby.all_ready())

class GameEndTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up a game session with an empty deck and no valid sets"""
        call_command("populate_cards")
        cls.cards = list(Card.objects.all())

        cls.player1 = User.objects.create_user(username="player1")
        cls.player2 = User.objects.create_user(username="player2")

        cls.session = GameSession.objects.create(name="Test Game")
        cls.session.players.set([cls.player1, cls.player2])

    def test_end_game_no_sets_available(self):
        """Ensure the game ends when no sets are available and the deck is empty"""
        self.session.initialize_game()

        # Simulate an empty deck
        self.session.state['deck'] = []

        # Simulate a board where no valid sets exist
        # Example: Choosing cards that ensure no valid set remains
        self.session.state['board'] = {
            "0": "1", "1": "2", "2": "3",
            "3": "4", "4": "5", "5": "6",
            "6": "7", "7": "8", "8": "9",
            "9": "10", "10": "11", "11": "12"
        }

        # Ensure there are no valid sets left
        self.assertFalse(self.session.is_set_available())

        # Trigger the end-game check
        self.session.handle_no_set_available()

        # Assert that the game is over
        self.assertTrue(self.session.state['game_over'])
