from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from set_game.models import Lobby

class Command(BaseCommand): #!TODO run this every so often somehow
    help = 'Deletes stale lobbies that have not started a game and have been inactive for a specified time.'

    def handle(self, *args, **kwargs):
        # Define the threshold for stale lobbies (e.g., 1 hour)
        stale_threshold = timezone.now() - timedelta(hours=1)

        # Find lobbies that:
        # 1. Have no GameState (game hasn't started)
        # 2. Have not been active for the stale_threshold
        stale_lobbies = Lobby.objects.filter(
            game_state__isnull=True,  # No GameState
            last_activity__lt=stale_threshold  # Inactive for too long
        )

        # Delete stale lobbies
        count = stale_lobbies.count()
        stale_lobbies.delete()

        self.stdout.write(self.style.SUCCESS(f'Deleted {count} stale lobbies.'))