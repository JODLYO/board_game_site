# set_game/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import GameSession, Player, Card, GameMove
from django.core.exceptions import ValidationError


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'game_room'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        print(data)
        if data['type'] == 'start_game':
            await self.start_game(data)
        elif data['type'] == 'make_move':
            await self.make_move(data)

    async def start_game(self, data):
        game_session = await sync_to_async(self.create_game_session)()
        # player_ids = await sync_to_async(lambda: [player.id for player in game_session.players.all()])() #I think add in player ids
        player_ids = await sync_to_async(lambda: list(game_session.players.values_list('id', flat=True)))()

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

    def create_game_session(self):
        game_session = GameSession.objects.create(name="New Game")
        player = Player.objects.create(name="Player 1")
        game_session.players.add(player)
        game_session.initialize_game()
        game_session.state["player_ids"] = [player.id for player in game_session.players.all()]
        game_session.state['scores'] = {str(player.id): 0 for player in game_session.players.all()}
        game_session.save()  # Save the game session to the database
        return game_session

    async def make_move(self, data):
        try:
            game_session = await sync_to_async(GameSession.objects.get)(pk=data['session_id'])
        except GameSession.DoesNotExist:
            print("Error game session does not exist")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Game session not found.'
            }))
            return

        await sync_to_async(game_session.refresh_from_db)()  # Ensure the state is refreshed from the database

        player = await sync_to_async(Player.objects.get)(pk=data['player_id'])
        card_ids = data['card_ids']

        try:
            await sync_to_async(game_session.validate_and_process_move)(player, card_ids)
            # Send only one game state update message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_state',
                    'state': await sync_to_async(self.serialize_game_state)(game_session),
                }
            )
        except ValidationError as e:
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
        return {
            'session': session.name,
            'players': [player.name for player in session.players.all()],
            'board': session.state['board'],
            'scores': session.state['scores'],
            'cards': {str(card.id): {
                'number': card.number,
                'symbol': card.symbol,
                'shading': card.shading,
                'color': card.color,
            } for card in Card.objects.filter(id__in=session.state['board'].values())},
        }
