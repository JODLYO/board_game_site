from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from typing import Dict, Any

from set_game.models import Lobby, LobbyPlayer

User = get_user_model()


class HomeViewTest(TestCase):
    def test_home_get_request(self) -> None:
        """Test that home page loads successfully."""
        response: Any = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "set_game/home.html")

    def test_home_post_valid_username(self) -> None:
        """Test form submission with a valid username."""
        response: Any = self.client.post(reverse("home"), {"username": "testuser"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="testuser").exists())

    def test_home_post_missing_username(self) -> None:
        """Test form submission without a username."""
        response: Any = self.client.post(reverse("home"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")


class LobbyViewTest(TestCase):
    def setUp(self) -> None:
        self.user: Any = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.login(username="testuser", password="testpass")

    def test_lobby_creation(self) -> None:
        """Test that a new user creates a new lobby."""
        response: Any = self.client.get(reverse("lobby"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lobby.objects.count(), 1)
        self.assertTrue(LobbyPlayer.objects.filter(player=self.user).exists())

    def test_lobby_join_existing(self) -> None:
        """Test that a second user joins an existing lobby if one is open."""
        Lobby.objects.create()
        _: AbstractUser = User.objects.create_user(username="testuser2")
        self.client.login(username="testuser2", password="testpass")
        response: Any = self.client.get(reverse("lobby"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lobby.objects.count(), 1)  # Should still be 1


class LobbyStatusViewTest(TestCase):
    def setUp(self) -> None:
        self.user: AbstractUser = User.objects.create_user(username="testuser")
        self.client.login(username="testuser", password="testpass")
        self.lobby: Lobby = Lobby.objects.create()
        LobbyPlayer.objects.create(lobby=self.lobby, player=self.user)

    def test_lobby_status_success(self) -> None:
        """Test lobby status endpoint returns correct data."""
        response: Any = self.client.get(reverse("lobby_status", args=[self.lobby.id]))
        self.assertEqual(response.status_code, 200)
        data: Dict[str, Any] = response.json()
        self.assertEqual(data["players"][0]["username"], "testuser")
