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


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_board_update_no_set(game_data):
    """Ensure that when no valid set is found, 3 cards are added while maintaining card placements."""

    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    game_session = game_data["game_session"]
    player = game_data["player"]


    # Initial board state (no valid sets)
    initial_board = {
        "0": "13", "1": "35", "2": "24", "3": "14",
        "4": "51", "5": "45", "6": "3", "7": "70",
        "8": "6", "9": "1", "10": "40", "11": "79"
    }
    valid_set = ["1", "40", "79"]
        # """(1, diamond, solid, red) → ID 1
        # (2, squiggle, striped, red) → ID 40
        # (3, oval, open, red) → ID 79"""
    # Simulated deck (next three cards to be drawn)
    # deck = ["46", "41", "52"]
    deck = ["61", "31", "49", "46", "41", "52"]

    # Set game state with no valid sets
    await sync_to_async(lambda: setattr(game_session, 'state', {
        'deck': deck,
        'board': initial_board.copy(),
        'scores': {player.username: 0},  # Ensure player exists in scores
        'game_over': False,
        'selected_sets': []
    }))()
    await sync_to_async(game_session.save)()

    # Trigger check for valid sets (which should result in adding new cards)
    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player.username,
        "card_ids": valid_set,
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "game_state"

    # Updated board after adding three cards
    expected_board = {
        "0": "13", "1": "35", "2": "24", "3": "14",
        "4": "51", "5": "45", "6": "3", "7": "70",
        "8": "6", "9": "61", "10": "31", "11": "49",
        "12": "46", "13": "41", "14": "52"
    }

    updated_board = response["state"]["board"]
    
    assert updated_board == expected_board, "Board did not update correctly."

    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_board_update_after_set(game_data):
    """Ensure that after a valid set is removed, the board updates correctly from 15 cards to 12 cards."""

    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    game_session = game_data["game_session"]
    player = game_data["player"]

    # Initial board state (before removing set)
    initial_board = {
        "0": "13", "1": "35", "2": "24", "3": "14",
        "4": "51", "5": "45", "6": "3", "7": "70",
        "8": "6", "9": "61", "10": "31", "11": "49",
        "12": "46", "13": "41", "14": "52"
    }

    # Set to be removed
    selected_set = ["13", "46", "61"]

    # Expected board after removing the set
    expected_board = {
        "0": "41", "1": "35", "2": "24", "3": "14",
        "4": "51", "5": "45", "6": "3", "7": "70",
        "8": "6", "9": "52", "10": "31", "11": "49"
    }

    # Set initial game state
    await sync_to_async(lambda: setattr(game_session, 'state', {
        'deck': [],  # No new cards to be added
        'board': initial_board.copy(),
        'scores': {player.username: 0},  # Ensure player exists in scores
        'game_over': False,
        'selected_sets': []
    }))()
    await sync_to_async(game_session.save)()

    # Simulate making a move (removing the valid set)
    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": game_data["player"].username,
        "card_ids": selected_set,
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "game_state"

    # Check if the board matches the expected state
    updated_board = response["state"]["board"]
    assert updated_board == expected_board, "Board did not update correctly after removing a set."

    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, reset_sequences=True)
async def test_score_updates_multiple_players(game_data):
    """Ensure that scores update correctly for two players."""
    
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    player1 = game_data["player"]
    game_session = game_data["game_session"]

    # Create second player and add them to the game session
    player2 = await sync_to_async(User.objects.create_user)(username="player2")
    await sync_to_async(game_session.players.add)(player2)

    # Initial scores
    initial_scores = {player1.username: 0, player2.username: 0}

    # Set up initial game state with predefined scores
    await sync_to_async(lambda: setattr(game_session, 'state', {
        'deck': [],
        'board': {str(i): str(game_data["cards"][i].id) for i in range(12)},
        'scores': initial_scores.copy(),
        'game_over': False,
        'selected_sets': []
    }))()
    await sync_to_async(game_session.save)()

    # Player 1 makes a move
    valid_set_p1 = [game_data["cards"][0].id, game_data["cards"][1].id, game_data["cards"][2].id]
    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player1.username,
        "card_ids": valid_set_p1,
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert response["state"]["scores"][player1.username] == 1  # Player 1 score should increase by 1
    assert response["state"]["scores"][player2.username] == 0  # Player 2 score should remain the same

    # Player 2 makes a move
    valid_set_p2 = [game_data["cards"][3].id, game_data["cards"][4].id, game_data["cards"][5].id]
    await communicator.send_json_to({
        "type": "make_move",
        "session_id": game_session.id,
        "username": player2.username,
        "card_ids": valid_set_p2,
    })

    response = await communicator.receive_json_from()
    assert response["type"] == "game_state"
    assert response["state"]["scores"][player1.username] == 1  # Player 1 score should remain the same
    assert response["state"]["scores"][player2.username] == 1  # Player 2 score should increase by 1

    await communicator.disconnect()
