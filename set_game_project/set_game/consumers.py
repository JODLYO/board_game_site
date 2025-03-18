import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import GameSession, Card, GameMove, Lobby, User
from django.core.exceptions import ValidationError
from django.db import transaction


@sync_to_async(thread_sensitive=True)
def get_locked_game_session(session_id):
    """Fetch the game session with a row-level lock to prevent concurrent modifications."""
    with transaction.atomic():
        print(f"🔒 Attempting to lock GameSession {session_id}")
        game_session = GameSession.objects.select_for_update().get(pk=session_id)
        print(f"🔒 Locked GameSession {session_id}: {game_session.state}")
        return game_session

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'game_room'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"🔗 WebSocket connected: {self.channel_name}")


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print(f"🔌 WebSocket disconnected: {self.channel_name}, close_code: {close_code}")


    async def receive(self, text_data):
        data = json.loads(text_data)
        print(f"📥 Received WebSocket message: {data}")
        if data['type'] == 'start_game':
            await self.start_game(data)
        elif data['type'] == 'make_move':
            await self.make_move(data)

    async def start_game(self, data):
        lobby_id = data.get('lobby_id')  # Assume the lobby ID is passed in the data
        print(f"🎮 Starting game for lobby: {lobby_id}")

        if not lobby_id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Lobby ID is required.',
            }))
            return
        try:
            lobby = await sync_to_async(Lobby.objects.get)(id=lobby_id)
        except Lobby.DoesNotExist:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Lobby not found.',
            }))
            return
        # Check if a GameSession already exists for this lobby
        game_session = await sync_to_async(GameSession.objects.filter(players__in=lobby.players.all()).first)()
        if not game_session:
            # Create a new GameSession if one doesn't exist
            game_session = await sync_to_async(self.create_game_session)(lobby)
        else:
            # Use the existing GameSession
            print(f"🔄 Reusing existing GameSession: {game_session.id}")
        # player_ids = await sync_to_async(lambda: [player.id for player in game_session.players.all()])() #I think add in player ids
        player_ids = await sync_to_async(lambda: list(game_session.players.values_list('id', flat=True)))()
        print(f"🆕 Created game session: {game_session.id}, players: {player_ids}")

        await self.send(text_data=json.dumps({
            'type': 'game_started',
            'session_id': game_session.id,  # Send the session ID to the client
            'player_ids': player_ids,
        }))

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_state',
                'state': await sync_to_async(self.serialize_game_state)(game_session),
            }
        )

    def create_game_session(self, lobby):
        game_session = GameSession.objects.create(name="New Game")
        for lobby_player in lobby.lobbyplayer_set.all():
            game_session.players.add(lobby_player.player)

        game_session.initialize_game()
        game_session.state["player_ids"] = [player.id for player in game_session.players.all()]
        game_session.state['scores'] = {str(player.username): 0 for player in game_session.players.all()}
        game_session.save()
        return game_session

    async def make_move(self, data):
        try:
            game_session = await get_locked_game_session(data['session_id'])
            print(f"🔒 Locked game session: {game_session.id}, state before move: {game_session.state}")
        except GameSession.DoesNotExist:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Game session not found.'
            }))
            return
        await sync_to_async(game_session.refresh_from_db)()  # Ensure the state is refreshed from the database
        print(f"🔒 Locked game session: {game_session.id}, state before move: {game_session.state}")

        # Validate card IDs
        card_ids = data['card_ids']
        board_card_ids = list(game_session.state['board'].values())
        print(card_ids)
        print(board_card_ids)
        if not all(card_id in board_card_ids for card_id in card_ids):
            raise ValidationError("Invalid card IDs: not all cards are on the board.")

        player = await sync_to_async(User.objects.get)(username=data['username'])
        card_ids = data['card_ids']
        print(f"🎲 Player {player.username} attempting move with cards: {card_ids}")

        try:
            await sync_to_async(game_session.validate_and_process_move)(player, card_ids)
            print(f"✅ Move processed successfully. New state: {game_session.state}")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_state',
                    'state': await sync_to_async(self.serialize_game_state)(game_session),
                }
            )


            # Check if the game is over
            if game_session.state.get('game_over', False):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_over',
                        'message': 'Game over! No more sets are possible.',
                    }
                )

        except ValidationError as e:
            print(f"❌ Move validation failed: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e),
            }))

    async def game_state(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'state': event['state'],
        }))

    def serialize_game_state(self, session):
        print(f"📤 Serializing game state for session {session.id}")
        print(f"📤 Current session state: {session.state}")
        state = {
            'session': session.name,
            'players': [player.username for player in session.players.all()],
            'board': session.state['board'],
            'scores': session.state['scores'],
            'cards': {str(card.id): {
                'number': card.number,
                'symbol': card.symbol,
                'shading': card.shading,
                'color': card.color,
            } for card in Card.objects.filter(id__in=session.state['board'].values())},
        }
        print(f"📤 Serialized game state: {state}")
        return state

    async def game_over(self, event):
        """
        Send a game_over message to the client.
        """
        await self.send(text_data=json.dumps({
            'type': 'game_over',
            'message': event['message'],
        }))
