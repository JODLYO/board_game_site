from django.shortcuts import render
from .models import Lobby, GameState, LobbyPlayer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.db.models import Count
from typing import cast

MAX_PLAYERS = 2

def home(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        username = request.POST.get("username")
        if not username:
            return render(
                request, "set_game/home.html", {"error": "This field is required."}
            )
        user, _ = User.objects.get_or_create(username=username)
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
    game_state = GameState.objects.get(id=game_state_id)
    lobby = game_state.lobby
    return render(
        request,
        "set_game/game_board.html",
        {
            "game_state": game_state,
            "lobby_id": lobby.id,
            "current_username": request.user.username,
        },
    )


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
