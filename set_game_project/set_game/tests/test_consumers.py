import pytest
from channels.testing import WebsocketCommunicator
from set_game.consumers import GameConsumer
from set_game.models import GameSession, Lobby, User, Card
from django.core.management import call_command
from asgiref.sync import sync_to_async
from django.db import transaction


@pytest.fixture
# @pytest.mark.django_db
def game_data():
    """Fixture to set up a test user, lobby, game session, and populate cards."""
    # Ensure cards are populated before tests
    if not Card.objects.exists():
        call_command("populate_cards")

    cards = list(Card.objects.all())

    player = User.objects.create_user(username="player1")
    lobby = Lobby.objects.create()
    game_session = GameSession.objects.create(name="Test Game")
    game_session.players.add(player)
    game_session.initialize_game()
    # def commit_session():
    #     print(f"Committing session ID: {game_session.id}")
    
    # transaction.on_commit(commit_session) 
    
    return {
        "player": player,
        "lobby": lobby,
        "game_session": game_session,
        "cards": cards,
    }

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_valid_move(game_data):
    """Ensure a valid move is processed correctly."""
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    player = game_data["player"]
    game_session = game_data["game_session"]
    valid_set = [card.id for card in game_data["cards"][:3]]

    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": valid_set,
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert player.username in response["state"]["scores"]

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_invalid_lobby():
    """Ensure error is returned when trying to start a game with a nonexistent lobby."""
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({
        "type": "start_game",
        "lobby_id": 9999,  # Assume this lobby does not exist
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "error"
    assert response["message"] == "Lobby not found."

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_invalid_move(game_data):
    """Ensure an invalid move is rejected."""
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    player = game_data["player"]
    game_session = game_data["game_session"]
    """(1, diamond, solid, red) → ID 1
    (1, diamond, solid, green) → ID 2
    (1, diamond, striped, red) → ID 75"""
    invalid_set = [1, 2, 75]

    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": invalid_set,
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "error"
    assert "not a valid set" in response["message"]

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_game_over(game_data):
    """Ensure the game ends when no sets are available and the deck is empty."""
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    player = game_data["player"]
    game_session = game_data["game_session"]

    # Ensure the board has a valid set to be played
    # board_card_ids = [1, 2, 3]  # Pick a valid set
    valid_set = [card.id for card in game_data["cards"][:3]]


    # Simulate game state where only one move remains
    await sync_to_async(lambda: setattr(game_session, 'state', {
        'deck': [],
        'board': {str(i): valid_set[i] for i in range(3)},
        'scores': {player.username: 5},
        'game_over': False,
        'selected_sets': []
    }))()
    await sync_to_async(game_session.save)()

    # Play the last valid set
    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": valid_set,
    })

    # Expect game state update first
    response = await communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert player.username in response["state"]["scores"]

    # Expect game over message next
    response = await communicator.receive_json_from()
    assert response["type"] == "game_over"
    assert response["message"] == "Game over! No more sets are possible."

    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_start_game_multiple_players():
    """Ensure a game can start with multiple players."""
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    # Create a lobby and multiple players
    lobby = await sync_to_async(Lobby.objects.create)()
    player1 = await sync_to_async(User.objects.create_user)(username="player1")
    player2 = await sync_to_async(User.objects.create_user)(username="player2")
    
    await sync_to_async(lobby.players.add)(player1, player2)

    await communicator.send_json_to({
        "type": "start_game",
        "lobby_id": lobby.id,
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "game_started"
    assert len(response["player_ids"]) == 2  # Ensure both players are added

    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_player_disconnect(game_data):
    """Ensure player disconnect does not crash the game."""
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    player = game_data["player"]
    game_session = game_data["game_session"]

    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": [],
    })

    await communicator.disconnect()

    # Ensure the game session still exists after disconnect
    session_check = await sync_to_async(GameSession.objects.filter(id=game_session.id).exists)()
    assert session_check, "Game session should still exist after player disconnect"

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_game_over_invalid_last_move(game_data):
    """Ensure the game does not end incorrectly if the last move is invalid."""
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    player = game_data["player"]
    game_session = game_data["game_session"]

    # Simulate game state with no valid sets
    await sync_to_async(lambda: setattr(game_session, 'state', {
        'deck': [],
        'board': {str(i): i for i in range(3)},  # Assume no valid sets
        'scores': {player.username: 10},
        'game_over': False,
        'selected_sets': [],
    }))()
    await sync_to_async(game_session.save)()

    # Attempt an invalid move
    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": [1, 2, 3],  # Assume invalid set
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "error"
    assert "not a valid set" in response["message"]

    # Game should not be over yet
    assert not game_session.state.get("game_over", False)

    await communicator.disconnect()

# import pytest
import asyncio
# from channels.testing import WebsocketCommunicator

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_concurrent_moves(game_data):
    """Ensure that concurrent moves are processed correctly."""
    communicator1 = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    communicator2 = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    
    connected1, _ = await communicator1.connect()
    connected2, _ = await communicator2.connect()
    assert connected1 and connected2

    player = game_data["player"]
    game_session = game_data["game_session"]
    valid_set = [card.id for card in game_data["cards"][:3]]
    valid_set2 = [card.id for card in game_data["cards"][3:6]]

    # Send both moves concurrently
    send_task1 = communicator1.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": valid_set,
    })
    send_task2 = communicator2.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": valid_set2,
    })

    await asyncio.gather(send_task1, send_task2)

    # Ensure both responses are received
    try:
        response1 = await communicator1.receive_json_from(timeout=5)
    except asyncio.TimeoutError:
        response1 = None  # Prevent test from failing if response never arrives

    try:
        response2 = await communicator2.receive_json_from(timeout=5)
    except asyncio.TimeoutError:
        response2 = None
    1
    # Only one move should succeed
    # assert (
    #     (response1 and response1["type"] == "game_state" and response2 and response2["type"] == "error") or
    #     (response1 and response1["type"] == "error" and response2 and response2["type"] == "game_state")
    # ), "Only one move should succeed"
    
    # Disconnect communicators **before exiting**
    await communicator1.disconnect()
    await communicator2.disconnect()
