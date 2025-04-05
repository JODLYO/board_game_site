import json
from typing import Dict, Any, Optional, List
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import GameSession, Card, Lobby, User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        self.room_group_name = "game_room"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data: str) -> None:
        data = json.loads(text_data)
        if data["type"] == "start_game":
            await self.start_game(data)
        elif data["type"] == "make_move":
            await self.make_move(data)

    async def start_game(self, data: Dict[str, Any]) -> None:
        """Handle game initialization."""
        lobby_id = data.get("lobby_id")
        if not lobby_id:
            return await self.send_error("Lobby ID is required")

        try:
            lobby = await sync_to_async(Lobby.objects.get)(id=lobby_id)
        except Lobby.DoesNotExist:
            return await self.send_error("Lobby not found")

        game_session = await self.get_or_create_game_session(lobby)
        player_ids = await sync_to_async(
            lambda: list(game_session.players.values_list("id", flat=True))
        )()

        await self.send_game_started(game_session.id, player_ids, game_session)
        # await self.broadcast_game_state(game_session)

    async def get_or_create_game_session(self, lobby: Lobby) -> GameSession:
        """Get or create a GameSession for the given lobby."""
        game_session = await sync_to_async(
            GameSession.objects.filter(players__in=lobby.players.all()).first
        )()
        return game_session or await sync_to_async(self.create_game_session)(lobby)

    def create_game_session(self, lobby: Lobby) -> GameSession:
        """Create and initialize a new game session."""
        game_session = GameSession.objects.create(name=f"Lobby-{lobby.id}-{timezone.now().strftime('%H%M%S')}")        
        for lobby_player in lobby.lobbyplayer_set.all():
            game_session.players.add(lobby_player.player)

        game_session.initialize_game()
        game_session.state.update({
            "player_ids": [player.id for player in game_session.players.all()],
            "scores": {str(player.username): 0 for player in game_session.players.all()}
        })
        game_session.save()
        return game_session

    async def make_move(self, data: Dict[str, Any]) -> None:
        """Process a player's move"""
        try:
            result = await sync_to_async(self._process_move)(data)
            
            if result["success"]:
                await self.broadcast_game_state(result["game_session"])
                if result["game_session"].state.get("game_over", False):
                    await self.broadcast_game_over()
            else:
                await self.send_error(result["error"])
                
        except Exception as e:
            await self.send_error(f"Error processing move: {str(e)}")

    @transaction.atomic
    def _process_move(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous method to process move"""
        try:
            game_session = GameSession.objects.select_for_update().get(pk=data["session_id"])
            player = User.objects.get(username=data["username"])
            
            if not self.validate_card_ids(data["card_ids"], game_session.state["board"].values()):
                return {"success": False, "error": "Cards not on board"}
            
            game_session.validate_and_process_move(player, data["card_ids"])
            game_session.save()
            
            return {"success": True, "game_session": game_session}
            
        except GameSession.DoesNotExist:
            return {"success": False, "error": "Game session not found"}
        except User.DoesNotExist:
            return {"success": False, "error": "Player not found"}
        except ValidationError as e:
            return {"success": False, "error": str(e)}

    async def game_state(self, event: Dict[str, Any]) -> None:
        """Send game state update to client."""
        await self.send_json({
            "type": "game_state",
            "state": event["state"],
        })

    async def game_over(self, event: Dict[str, Any]) -> None:
        """Notify client that game has ended."""
        await self.send_json({
            "type": "game_over",
            "message": event["message"],
        })

    async def send_game_started(self, session_id: int, player_ids: List[int], game_session: GameSession) -> None:
        """Notify client that game has started."""
        await self.send_json({
            "type": "game_started",
            "session_id": session_id,
            "player_ids": player_ids,
            "state": await sync_to_async(self.serialize_game_state)(game_session),
        })

    async def broadcast_game_state(self, game_session: GameSession) -> None:
        """Broadcast current game state to all clients."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "game_state",
                "state": await sync_to_async(self.serialize_game_state)(game_session),
            }
        )

    def serialize_game_state(self, session: GameSession) -> Dict[str, Any]:
        """Prepare game state for serialization."""
        return {
            "session": session.name,
            "players": [player.username for player in session.players.all()],
            "board": session.state["board"],
            "scores": session.state["scores"],
            "cards": {
                str(card.id): {
                    "number": card.number,
                    "symbol": card.symbol,
                    "shading": card.shading,
                    "color": card.color,
                }
                for card in Card.objects.filter(id__in=session.state["board"].values())
            },
        }

    def validate_card_ids(self, card_ids: List[int], board_card_ids: List[int]) -> bool:
        """Verify all card IDs exist on the board."""
        return all(card_id in board_card_ids for card_id in card_ids)

    async def send_error(self, message: str) -> None:
        """Send error message to client."""
        await self.send_json({
            "type": "error",
            "message": message,
        })

    async def broadcast_game_over(self) -> None:
        """Notify all clients that game has ended."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "game_over",
                "message": "Game over! No more sets are possible.",
            }
        )

    async def send_json(self, data: Dict[str, Any]) -> None:
        """Helper method to send JSON data."""
        await self.send(text_data=json.dumps(data))
