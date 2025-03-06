# set_game/tests/test_consumers.py
from channels.testing import WebsocketCommunicator
from set_game.consumers import GameConsumer
import pytest

@pytest.mark.asyncio
async def test_game_consumer():
    communicator = WebsocketCommunicator(GameConsumer, "/ws/game/")
    connected, _ = await communicator.connect()
    assert connected

    # Send a start_game message
    await communicator.send_json_to({
        "type": "start_game",
        "lobby_id": 1,  # Replace with a valid lobby ID
    })

    # Receive the game_started message
    response = await communicator.receive_json_from()
    assert response["type"] == "game_started"

    await communicator.disconnect()
