from django.test import TestCase, Client
from django.urls import reverse
from set_game.models import Card, Player, GameSession

class ViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.player = Player.objects.create(name="Test Player")
        self.game_session = GameSession.objects.create(name="Test Game")
        self.game_session.players.add(self.player)
        self.game_session.initialize_game()

    def test_home_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'set_game/home.html')

    def test_game_view(self):
        response = self.client.get(reverse('game_board'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'set_game/game_board.html')  # Correct template name
 