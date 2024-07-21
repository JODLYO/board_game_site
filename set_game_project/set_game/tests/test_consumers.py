import json
import pytest
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from set_game.consumers import GameConsumer
from set_game.models import GameSession, Player, Card
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_start_game():

    for i in range(12):
        await sync_to_async(Card.objects.create)(
            number=i % 3 + 1,
            symbol=['diamond', 'squiggle', 'oval'][i % 3],
            shading=['solid', 'striped', 'open'][i % 3],
            color=['red', 'green', 'purple'][i % 3],
        )
    # player = await sync_to_async(Player.objects.create)(name="Test Player")

     # Create a communicator instance for our consumer
    communicator = WebsocketCommunicator(GameConsumer.as_asgi(), "/ws/game/")
    connected, subprotocol = await communicator.connect()
    assert connected

    # Send a start_game message
    await communicator.send_json_to({'type': 'start_game'})

    # Receive the game_started message
    response = await communicator.receive_json_from()
    assert response['type'] == 'game_started'
    session_id = response['session_id']

    # Verify game session is created
    game_session = await sync_to_async(GameSession.objects.get)(id=session_id)

    assert game_session is not None

    assert session_id == game_session.id
    state = game_session.state
    player_id = state["player_ids"][0] #Should change, same as line 127 in game.js
    assert len(state['board']) == 12  # Ensure the board has 12 cards
    assert len(state['deck']) == 0   # Ensure the deck is empty
    assert 'selected_sets' in state
    assert len(state['selected_sets']) == 0
    assert 'scores' in state
    assert len(state['scores']) > 0
    valid_set = list(state['board'].values())[:3]  # Select first three cards on the board
    await communicator.send_json_to({
        'type': 'make_move',
        'session_id': session_id,
        'player_id': player_id,
        'card_ids': valid_set
    })

    response = await communicator.receive_json_from()
    await communicator.disconnect()
