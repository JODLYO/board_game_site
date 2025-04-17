import pytest
import pytest_asyncio
import asyncio
from channels.testing import WebsocketCommunicator
from set_game.consumers import GameConsumer
from set_game.models import GameSession, Lobby, User, Card
from django.core.management import call_command
from asgiref.sync import sync_to_async
from typing import Dict, List, Optional, Any

# Constants for board states
INITIAL_BOARD: Dict[str, str] = {
    "0": "13",
    "1": "35",
    "2": "24",
    "3": "14",
    "4": "51",
    "5": "45",
    "6": "3",
    "7": "70",
    "8": "6",
    "9": "61",
    "10": "31",
    "11": "49",
    "12": "46",
    "13": "41",
    "14": "52",
}

EXPECTED_BOARD_AFTER_SET: Dict[str, str] = {
    "0": "41",
    "1": "35",
    "2": "24",
    "3": "14",
    "4": "51",
    "5": "45",
    "6": "3",
    "7": "70",
    "8": "6",
    "9": "52",
    "10": "31",
    "11": "49",
}

INITIAL_BOARD_NO_SETS: Dict[str, str] = {"0": "13", "1": "35"}

INITIAL_BOARD_MULTIPLE_PLAYERS: Dict[str, str] = {
    "0": "42",
    "1": "66",
    "2": "80",
    "3": "60",
    "4": "34",
    "5": "57",
    "6": "6",
    "7": "20",
    "8": "10",
    "9": "59",
    "10": "67",
    "11": "45",
}

DECK: List[str] = ["55", "17", "39", "46", "41", "52"]


@pytest.fixture
def event_loop():
    """The most compatible version"""

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    if not loop.is_closed():
        loop.close()

    # Cleanup
    loop.close()
    asyncio.set_event_loop(None)


# @pytest.fixture(autouse=True)
# async def setup_db():
#     """Ensure database is ready for async tests."""
#     await sync_to_async(call_command)("migrate")
#     if not await sync_to_async(Card.objects.exists)():
#         await sync_to_async(call_command)("populate_cards")


@pytest_asyncio.fixture
async def game_data() -> Dict[str, Any]:
    """Fixture to set up a test user, lobby, game session, and populate cards."""
    # Check if cards exist using sync_to_async
    cards_exist = await sync_to_async(Card.objects.exists)()
    if not cards_exist:
        await sync_to_async(call_command)("populate_cards")

    # Create user, lobby, and game session using sync_to_async
    player: User = await sync_to_async(User.objects.create_user)(username="player1")
    lobby: Lobby = await sync_to_async(Lobby.objects.create)()
    create_game = sync_to_async(GameSession.objects.create)
    game_session: GameSession = await create_game(name="Test Game")
    await sync_to_async(game_session.players.add)(player)
    await sync_to_async(game_session.initialize_game)()

    # Get all cards using sync_to_async
    cards: List[Card] = await sync_to_async(lambda: list(Card.objects.all()))()

    return {
        "player": player,
        "lobby": lobby,
        "game_session": game_session,
        "cards": cards,
    }


async def create_websocket_communicator() -> WebsocketCommunicator:
    """Helper function to create and connect a WebSocket communicator."""
    communicator: WebsocketCommunicator = WebsocketCommunicator(
        GameConsumer.as_asgi(), "/ws/game/"
    )
    connected, _ = await communicator.connect()
    assert connected
    return communicator


async def setup_game_state(
    game_session: GameSession,
    board: Dict[str, str],
    deck: Optional[List[str]] = None,
    scores: Optional[Dict[str, int]] = None,
    game_over: bool = False,
    selected_sets: Optional[List[str]] = None,
) -> None:
    """Helper function to set up the game state."""
    if deck is None:
        deck = []
    if scores is None:
        scores = {}
    if selected_sets is None:
        selected_sets = []

    # Update game state using sync_to_async
    await sync_to_async(
        lambda: setattr(
            game_session,
            "state",
            {
                "deck": deck,
                "board": board,
                "scores": scores,
                "game_over": game_over,
                "selected_sets": selected_sets,
            },
        )
    )()
    await sync_to_async(game_session.save)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_valid_move(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure a valid move is processed correctly."""
    game_session: GameSession = game_data["game_session"]
    player: User = game_data["player"]

    await setup_game_state(game_session, INITIAL_BOARD, scores={player.username: 0})

    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player.username,
            "card_ids": ["13", "46", "61"],
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert player.username in response["state"]["scores"]
    assert response["state"]["board"] == EXPECTED_BOARD_AFTER_SET


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_invalid_lobby(websocket_communicator: WebsocketCommunicator) -> None:
    """Ensure error is returned when trying to start a game with a nonexistent lobby."""
    await websocket_communicator.send_json_to(
        {
            "type": "start_game",
            "lobby_id": 9999,  # Invalid lobby ID
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "error"
    assert response["message"] == "Lobby not found"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_invalid_move(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure an invalid move is rejected."""
    game_session: GameSession = game_data["game_session"]
    player: User = game_data["player"]

    await setup_game_state(game_session, INITIAL_BOARD, scores={player.username: 0})

    invalid_set: List[int] = [1, 2, 75]  # Invalid set
    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player.username,
            "card_ids": invalid_set,
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "error"
    assert "Cards not on board" in response["message"]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_game_over(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure the game ends when no sets are available and the deck is empty."""
    game_session: GameSession = game_data["game_session"]
    player: User = game_data["player"]

    valid_set: List[str] = ["1", "2", "3"]
    await setup_game_state(
        game_session,
        {"0": "1", "1": "2", "2": "3"},
        deck=[],
        scores={player.username: 5},
    )

    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player.username,
            "card_ids": valid_set,
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert player.username in response["state"]["scores"]

    response = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_over"
    assert response["message"] == "Game over! No more sets are possible."


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_start_game_multiple_players(
    websocket_communicator: WebsocketCommunicator,
) -> None:
    """Ensure a game can start with multiple players."""
    lobby: Lobby = await sync_to_async(Lobby.objects.create)()
    player1: User = await sync_to_async(User.objects.create_user)(username="player1")
    player2: User = await sync_to_async(User.objects.create_user)(username="player2")
    player3: User = await sync_to_async(User.objects.create_user)(username="player3")
    await sync_to_async(lobby.players.add)(player1, player2, player3)

    await websocket_communicator.send_json_to(
        {
            "type": "start_game",
            "lobby_id": lobby.id,
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_started"
    assert len(response["player_ids"]) == 3


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_player_disconnect(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure player disconnect does not crash the game."""
    game_session: GameSession = game_data["game_session"]
    player: User = game_data["player"]

    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player.username,
            "card_ids": [],
        }
    )

    await websocket_communicator.disconnect()

    # Ensure the game session still exists after disconnect
    session_check: bool = await sync_to_async(
        GameSession.objects.filter(id=game_session.id).exists
    )()
    assert session_check, "Game session should still exist after player disconnect"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_game_over_invalid_last_move(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure the game does not end incorrectly if the last move is invalid."""
    game_session: GameSession = game_data["game_session"]
    player: User = game_data["player"]

    await setup_game_state(
        game_session, INITIAL_BOARD_NO_SETS, deck=[], scores={player.username: 10}
    )

    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player.username,
            "card_ids": [1, 2],
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "error"
    assert "Cards not on board" in response["message"]

    # Game should not be over yet
    game_over = await sync_to_async(
        lambda: game_session.state.get("game_over", False)
    )()
    assert not game_over


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_board_update_no_set(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure that when no valid set is found, 3 cards are added while maintaining card placements."""
    game_session: GameSession = game_data["game_session"]
    player: User = game_data["player"]

    await setup_game_state(
        game_session,
        INITIAL_BOARD_MULTIPLE_PLAYERS,
        deck=DECK,
        scores={player.username: 0},
    )

    valid_set: List[str] = ["67", "57", "80"]
    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player.username,
            "card_ids": valid_set,
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_state"

    expected_board: Dict[str, str] = {
        "0": "42",
        "1": "66",
        "2": "55",
        "3": "60",
        "4": "34",
        "5": "17",
        "6": "6",
        "7": "20",
        "8": "10",
        "9": "59",
        "10": "39",
        "11": "45",
    }
    assert response["state"]["board"] == expected_board


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_board_update_after_set(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure that after a valid set is removed, the board updates correctly from 15 cards to 12 cards."""
    game_session: GameSession = game_data["game_session"]
    player: User = game_data["player"]

    await setup_game_state(game_session, INITIAL_BOARD, scores={player.username: 0})

    selected_set: List[str] = ["13", "46", "61"]
    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player.username,
            "card_ids": selected_set,
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert response["state"]["board"] == EXPECTED_BOARD_AFTER_SET


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_score_updates_multiple_players(
    game_data: Dict[str, Any], websocket_communicator: WebsocketCommunicator
) -> None:
    """Ensure that scores update correctly for two players."""
    game_session: GameSession = game_data["game_session"]
    player1: User = game_data["player"]

    player2: User = await sync_to_async(User.objects.create_user)(username="player2")
    await sync_to_async(game_session.players.add)(player2)

    await setup_game_state(
        game_session,
        board=INITIAL_BOARD_MULTIPLE_PLAYERS,
        deck=DECK,
        scores={player1.username: 0, player2.username: 0},
    )

    valid_set_p1: List[str] = ["67", "57", "80"]
    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player1.username,
            "card_ids": valid_set_p1,
        }
    )

    response: Dict[str, Any] = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert response["state"]["scores"][player1.username] == 1
    assert response["state"]["scores"][player2.username] == 0

    valid_set_p2: List[str] = ["45", "39", "42"]
    await websocket_communicator.send_json_to(
        {
            "type": "make_move",
            "session_id": game_session.id,
            "username": player2.username,
            "card_ids": valid_set_p2,
        }
    )

    response = await websocket_communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert response["state"]["scores"][player1.username] == 1
    assert response["state"]["scores"][player2.username] == 1
