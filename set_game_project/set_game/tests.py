# set_game/tests.py

from django.test import TestCase
from .models import Card, Player, GameSession, GameMove
from django.core.exceptions import ValidationError

class GameSessionModelTests(TestCase):

    def setUp(self):
        # Create cards
        self.cards = [
            Card.objects.create(number=i % 3 + 1, symbol=f"symbol_{i % 3}", shading=f"shading_{i % 3}", color=f"color_{i % 3}")
            for i in range(12)
        ]
        self.extra_cards = [
            Card.objects.create(number=i % 3 + 1, symbol=f"symbol_{i % 3}", shading=f"shading_{i % 3}", color=f"color_{i % 3}")
            for i in range(12, 15)
        ]

        # Create player
        self.player = Player.objects.create(name="Player 1")

        # Create game session
        self.game_session = GameSession.objects.create(name="Test Game")
        self.game_session.players.add(self.player)
        self.game_session.initialize_game()

    def test_initialize_game(self):
        state = self.game_session.state
        self.assertEqual(len(state['board']), 12)
        self.assertEqual(len(state['deck']), len(Card.objects.all()) - 12)  # Adjust the expected deck length
        self.assertEqual(len(state['scores']), 1)
        self.assertEqual(state['scores'][str(self.player.id)], 0)

    def test_validate_set(self):
        # Test a valid set
        valid_set = [str(self.cards[0].id), str(self.cards[1].id), str(self.cards[2].id)]
        self.assertTrue(self.game_session.validate_set(valid_set))

        # Test an invalid set
        invalid_set = [str(self.cards[0].id), str(self.cards[1].id), str(self.extra_cards[0].id)]
        self.assertFalse(self.game_session.validate_set(invalid_set))

    def test_is_set(self):
        # Convert list to queryset
        valid_set = Card.objects.filter(id__in=[self.cards[0].id, self.cards[1].id, self.cards[2].id])
        invalid_set = Card.objects.filter(id__in=[self.cards[0].id, self.cards[1].id, self.extra_cards[0].id])

        # Test a valid set
        self.assertTrue(self.game_session.is_set(valid_set))

        # Test an invalid set
        self.assertFalse(self.game_session.is_set(invalid_set))

    def test_process_set(self):
        # Test processing a valid set
        valid_set = [str(self.cards[3].id), str(self.cards[4].id), str(self.cards[5].id)]
        print(valid_set)
        self.game_session.process_set(self.player, valid_set)
        state = self.game_session.state
        self.assertEqual(state['scores'][str(self.player.id)], 1)
        # Check if the cards were removed from the board positions
        print(state['board'])
        print(state['board'].values())
        for pos, card_id in state['board'].items():
            self.assertNotIn(card_id, valid_set)
        self.assertEqual(len(state['board']), 12)

    def test_validate_and_process_move(self):
        # Test validating and processing a valid set
        valid_set = [str(self.cards[0].id), str(self.cards[1].id), str(self.cards[2].id)]
        self.game_session.validate_and_process_move(self.player, valid_set)
        state = self.game_session.state
        self.assertEqual(state['scores'][str(self.player.id)], 1)
        # Check if the cards were removed from the board positions
        for pos, card_id in state['board'].items():
            self.assertNotIn(card_id, valid_set)
        self.assertEqual(len(state['board']), 12)

        # Test validating and processing an invalid set
        invalid_set = [str(self.cards[0].id), str(self.cards[1].id), str(self.extra_cards[0].id)]
        with self.assertRaises(ValidationError):
            self.game_session.validate_and_process_move(self.player, invalid_set)
