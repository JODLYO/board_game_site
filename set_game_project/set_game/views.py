from django.shortcuts import render
from .models import Card, Lobby, GameState, LobbyPlayer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import JsonResponse
from django.urls import reverse
from django.db.models import Count


def home(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        if not username:
            return render(request, 'set_game/home.html', {'error': "This field is required."})
        user, created = User.objects.get_or_create(username=username)
        if created:
            print(f"New user created: {username}")
        else:
            print(f"Existing user logged in: {username}")
        login(request, user, "django.contrib.auth.backends.ModelBackend")
        return redirect('lobby')
    return render(request, 'set_game/home.html')


@login_required
def lobby(request):
    print(f"Current user: {request.user}")
    
    # Fetch or create the lobby
    lobby = Lobby.objects.filter(players=request.user).first()
    if not lobby:
        open_lobby = Lobby.objects.annotate(player_count=Count('players')).filter(player_count__lt=2).first()
        if open_lobby:
            print(f"Joining existing lobby: {open_lobby}")
            LobbyPlayer.objects.create(lobby=open_lobby, player=request.user)
            lobby = open_lobby
        else:
            print(f"Creating new lobby")
            lobby = Lobby.objects.create()
            LobbyPlayer.objects.create(lobby=lobby, player=request.user)

    print(f"Lobby: Players={[lp.player.username for lp in lobby.lobbyplayer_set.all()]}")
    print(f"Lobby ID in view: {lobby.id}")  # Debugging
    
    if request.method == 'POST':
        print(f"Handling POST request for user: {request.user}")
        
        # Update the player's ready status
        lobby_player = LobbyPlayer.objects.get(lobby=lobby, player=request.user)
        lobby_player.ready = True
        lobby_player.save()
        
        print(f"Lobby after update: Players={[lp.player.username for lp in lobby.lobbyplayer_set.all()]}, Ready={[lp.ready for lp in lobby.lobbyplayer_set.all()]}")
        
        if lobby.all_ready():
            print("Both players are ready. Creating game state.")
            game_state = GameState.objects.create(lobby=lobby)
            print(f"GameState created: {game_state.id}")
            lobby.game_state = game_state
            lobby.save()
            print(f"Lobby updated with GameState: {lobby.game_state.id}")

        return JsonResponse({
            'is_full': lobby.is_full(),
            'all_ready': lobby.all_ready(),
            'players': [{
                'username': lp.player.username,
                'ready': lp.ready
            } for lp in lobby.lobbyplayer_set.all()],
            'csrf_token': request.COOKIES['csrftoken']
        })

    return render(request, 'set_game/lobby.html', {'lobby': lobby})

@login_required
def game_board(request, game_state_id):
    game_state = GameState.objects.get(id=game_state_id)
    lobby = game_state.lobby
    return render(
        request,
        'set_game/game_board.html',
        {'game_state': game_state, 'lobby_id': lobby.id, 'current_username': request.user.username}
        )


def lobby_status(request, lobby_id):
    try:
        lobby = Lobby.objects.get(id=lobby_id)
        lobby.refresh_from_db()  # Ensure the latest data is fetched

        # Fetch players and their readiness from the LobbyPlayer model
        lobby_players = lobby.lobbyplayer_set.all()
        players = [{
            'username': lp.player.username,
            'ready': lp.ready
        } for lp in lobby_players]

        data = {
            'players': players,  # List of players and their readiness
            'is_full': lobby.is_full(),  # Check if the lobby is full
            'all_ready': lobby.all_ready(),  # Check if all players are ready
            'csrf_token': request.META.get('CSRF_COOKIE'),
            'game_state_id': lobby.game_state.id if hasattr(lobby, 'game_state') and lobby.game_state else None,
            'lobby_id': lobby_id,
        }
        return JsonResponse(data)
    except Lobby.DoesNotExist:
        return JsonResponse({'error': 'Lobby not found'}, status=404)
    except Exception as e:
        # Log the exception for debugging
        print(f"Error in lobby_status view: {e}")
        return JsonResponse({'error': 'An unexpected error occurred.'}, status=500)
