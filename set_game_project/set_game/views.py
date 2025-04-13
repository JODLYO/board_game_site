from django.shortcuts import render
from .models import Lobby, GameState, LobbyPlayer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import JsonResponse, HttpRequest, HttpResponse, Http404
from django.db.models import Count, Q
from typing import cast

MAX_PLAYERS = 2

def generate_unique_username(base_username: str) -> str:
    """Generate a unique username by appending a number if needed."""
    # First try the base username
    if not User.objects.filter(username=base_username).exists():
        return base_username
        
    # Find the highest number used with this base username
    pattern = f"{base_username}#"
    existing_users = User.objects.filter(username__startswith=pattern)
    
    if not existing_users.exists():
        return f"{base_username}#0000"
        
    # Get the highest number used
    numbers = [int(user.username.split('#')[1]) for user in existing_users]
    next_number = max(numbers) + 1
    
    # Format with leading zeros
    return f"{base_username}#{next_number:04d}"

def home(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        username = request.POST.get("username")
        if not username:
            return render(
                request, "set_game/home.html", {"error": "This field is required."}
            )
            
        # Generate a unique username
        unique_username = generate_unique_username(username)
        user, _ = User.objects.get_or_create(username=unique_username)
        login(request, user, "django.contrib.auth.backends.ModelBackend")
        return redirect("lobby")
    return render(request, "set_game/home.html")


@login_required
def lobby(request: HttpRequest) -> HttpResponse:
    lobby = Lobby.objects.filter(players=cast(User, request.user)).first()
    if not lobby:
        open_lobby = (
            Lobby.objects.annotate(player_count=Count("players"))
            .filter(
                player_count__lt=MAX_PLAYERS,
                game_state__isnull=True,
            )
            .first()
        )
        if open_lobby:
            LobbyPlayer.objects.create(
                lobby=open_lobby, player=cast(User, request.user)
            )
            lobby = open_lobby
        else:
            lobby = Lobby.objects.create()
            LobbyPlayer.objects.create(lobby=lobby, player=cast(User, request.user))

    if request.method == "POST":
        lobby_player = LobbyPlayer.objects.get(
            lobby=lobby, player=cast(User, request.user)
        )
        lobby_player.ready = True
        lobby_player.save()

        if lobby.all_ready():
            game_state = GameState.objects.create(lobby=lobby)
            lobby.game_state = game_state
            lobby.save()

        return JsonResponse(
            {
                "is_full": lobby.is_full(),
                "all_ready": lobby.all_ready(),
                "players": [
                    {"username": lp.player.username, "ready": lp.ready}
                    for lp in lobby.lobbyplayer_set.all()
                ],
                "csrf_token": request.COOKIES["csrftoken"],
            }
        )

    return render(request, "set_game/lobby.html", {"lobby": lobby})


@login_required
def game_board(request: HttpRequest, game_state_id: int) -> HttpResponse:
    """View for the game board."""
    try:
        game_state = GameState.objects.get(id=game_state_id)
        lobby = game_state.lobby
        
        # Verify the user is a player in this game
        if not lobby.players.filter(id=request.user.id).exists():
            raise Http404("You are not a player in this game")
            
        return render(
            request,
            "set_game/game_board.html",
            {
                "game_state": game_state,
                "lobby_id": lobby.id,
                "current_username": request.user.username,
            },
        )
    except GameState.DoesNotExist:
        raise Http404("Game not found")


def lobby_status(request: HttpRequest, lobby_id: int) -> JsonResponse:
    try:
        lobby = Lobby.objects.get(id=lobby_id)
        lobby.refresh_from_db()
        lobby_players = lobby.lobbyplayer_set.all()
        players = [
            {"username": lp.player.username, "ready": lp.ready} for lp in lobby_players
        ]

        data = {
            "players": players,
            "is_full": lobby.is_full(),
            "all_ready": lobby.all_ready(),
            "csrf_token": request.META.get("CSRF_COOKIE"),
            "game_state_id": lobby.game_state.id
            if hasattr(lobby, "game_state") and lobby.game_state
            else None,
            "lobby_id": lobby_id,
        }
        return JsonResponse(data)
    except Lobby.DoesNotExist:
        return JsonResponse({"error": "Lobby not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)
