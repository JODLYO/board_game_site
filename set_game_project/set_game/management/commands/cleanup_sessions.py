from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from set_game.models import Lobby, GameSession

class Command(BaseCommand):
    help = 'Cleans up inactive lobbies and game sessions'

    def handle(self, *args, **options) -> None:
        # Get current time
        now = timezone.now()
        
        # Calculate cutoff times
        lobby_cutoff = now - timedelta(minutes=5)  # 5 minutes for lobbies
        game_cutoff = now - timedelta(hours=1)     # 1 hour for game sessions
        
        # Clean up inactive lobbies
        inactive_lobbies = Lobby.objects.filter(last_activity__lt=lobby_cutoff)
        lobby_count = inactive_lobbies.count()
        inactive_lobbies.delete()
        
        # Clean up inactive game sessions
        inactive_games = GameSession.objects.filter(last_activity__lt=game_cutoff)
        game_count = inactive_games.count()
        inactive_games.delete()
        
        # Log the results
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cleaned up {lobby_count} inactive lobbies and {game_count} inactive game sessions'
            )
        )
