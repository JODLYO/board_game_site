from typing import List, Tuple, Optional, ClassVar
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from random import shuffle
from itertools import combinations

MAX_PLAYERS = 2
NO_CARDS_IN_SET = 3
DEFAULT_BOARD_SIZE = 12


class Card(models.Model):
    """Represents a Set game card with four attributes."""

    number = models.IntegerField()
    symbol = models.CharField(max_length=20)
    shading = models.CharField(max_length=20)
    color = models.CharField(max_length=20)

    def __str__(self) -> str:
        return f"{self.number} {self.shading} {self.color} {self.symbol}"

    class Meta:
        ordering = ["number", "symbol", "shading", "color"]


class GameSession(models.Model):
    name = models.CharField(max_length=100)
    players = models.ManyToManyField(User, related_name="game_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.name

    def initialize_game(self) -> None:
        deck = list(Card.objects.all())
        shuffle(deck)
        initial_board_cards, remaining_deck = self._get_initial_board_and_deck(deck)
        scores = {str(player.username): 0 for player in self.players.all()}

        self.state = {
            "deck": [card.id for card in remaining_deck],
            "board": {str(i): card.id for i, card in enumerate(initial_board_cards)},
            "selected_sets": [],
            "scores": scores,
        }
        self.save()

    def _get_initial_board_and_deck(
        self, deck: List[Card]
    ) -> Tuple[List[Card], List[Card]]:
        initial_board_cards = deck[:12]
        has_set = self.is_set_available([card.id for card in initial_board_cards])
        if has_set:
            initial_no_cards = 12
        else:
            initial_no_cards = 15
        initial_board_cards = deck[:initial_no_cards]
        remaining_deck = deck[initial_no_cards:]
        return initial_board_cards, remaining_deck

    def validate_and_process_move(
        self, player: User, selected_cards: List[int]
    ) -> None:
        self.refresh_from_db()

        if not self.validate_set(selected_cards):
            raise ValidationError("Invalid set selection")

        self.process_set(player, selected_cards)
        self.save()

    def validate_set(self, selected_cards: List[int]) -> bool:
        if len(selected_cards) != NO_CARDS_IN_SET:
            return False
        # if "selected_sets" not in self.state:
        #     return False
        cards = Card.objects.filter(id__in=[str(card_id) for card_id in selected_cards])
        return self._check_set_attributes(cards)

    def _check_set_attributes(self, cards: models.QuerySet) -> bool:
        card_list = list(cards.values("number", "symbol", "shading", "color"))
        for attribute in ["number", "symbol", "shading", "color"]:
            if len(set([card[attribute] for card in card_list])) not in [
                1,
                NO_CARDS_IN_SET,
            ]:
                return False
        return True

    def process_set(self, player: User, card_ids: List[int]) -> None:
        self.state["selected_sets"].append(card_ids)
        self.state["scores"][str(player.username)] += 1

        self._remove_cards_from_board(card_ids)
        self.add_cards_to_board()
        self.handle_no_set_available()
        self._check_game_end()
        self.save()

    def _remove_cards_from_board(self, card_ids: List[int]) -> None:
        self.state["board"] = {
            pos: card_id
            for pos, card_id in self.state["board"].items()
            if card_id not in card_ids
        }

    def _check_game_end(self) -> None:
        if not self.state["deck"] and not self.is_set_available():
            self.end_game()

    def add_cards_to_board(self) -> None:
        if len(self.state["board"]) >= 12:
            empty_positions = sorted(
                list(set(str(i) for i in range(12)) - set(self.state["board"].keys())),
                key=int,
            )
            extra_positions = sorted(self.state["board"].keys(), key=int)[
                -len(empty_positions) :
            ]
            for empty_pos, extra_pos in zip(empty_positions, extra_positions):
                self.state["board"][empty_pos] = self.state["board"].pop(extra_pos)
        else:
            empty_positions_set = set(str(i) for i in range(12)).difference(
                set(self.state["board"].keys())
            )
            empty_positions = sorted(list(empty_positions_set), key=int)
            self.add_cards_from_deck(NO_CARDS_IN_SET, empty_positions)

    def add_cards_from_deck(self, count: int, empty_positions: List[str]) -> None:
        new_cards = self.state["deck"][:count]
        self.state["deck"] = self.state["deck"][count:]
        for pos, card_id in zip(empty_positions, new_cards):
            self.state["board"][pos] = card_id

    def is_set_available(self, card_ids: Optional[List[int]] = None) -> bool:
        if card_ids is None:
            card_ids = list(self.state["board"].values())

        if len(card_ids) < NO_CARDS_IN_SET:
            return False
        for combo in combinations(card_ids, NO_CARDS_IN_SET):
            if self.validate_set(list(combo)):
                return True
        return False

    def handle_no_set_available(self) -> None:
        if not self.is_set_available():
            if self.state["deck"]:
                next_positions = [
                    str(i)
                    for i in range(
                        len(self.state["board"]),
                        len(self.state["board"]) + NO_CARDS_IN_SET,
                    )
                ]
                self.add_cards_from_deck(NO_CARDS_IN_SET, next_positions)
            else:
                self.end_game()
                self.save()

    def end_game(self) -> None:
        self.state["game_over"] = True


class GameMove(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    cards = models.ManyToManyField(Card, related_name="moves")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Move by {self.player} in {self.session}"


class Lobby(models.Model):
    players: ClassVar[models.ManyToManyField] = models.ManyToManyField(
        User, through="LobbyPlayer"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def is_full(self) -> bool:
        return self.players.count() == MAX_PLAYERS

    def all_ready(self) -> bool:
        return all(lobby_player.ready for lobby_player in self.lobbyplayer_set.all())

    def __str__(self) -> str:
        return f"Lobby {self.id}"


class LobbyPlayer(models.Model):
    lobby = models.ForeignKey(Lobby, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(auto_now=True)
    ready = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["lobby", "player"],
                name="unique_player_per_lobby",
            )
        ]

    def __str__(self) -> str:
        return f"{self.player.username} in Lobby {self.lobby.id}"


class GameState(models.Model):
    lobby = models.OneToOneField(
        Lobby, on_delete=models.CASCADE, related_name="game_state"
    )
    state_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
