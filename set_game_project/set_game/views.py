from django.shortcuts import render
from .models import Card, Lobby, GameState
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import JsonResponse
from django.urls import reverse


def home(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        user, created = User.objects.get_or_create(username=username)
        if created:
            print(f"New user created: {username}")
        else:
            print(f"Existing user logged in: {username}")
        login(request, user)
        return redirect('lobby')
    return render(request, 'set_game/home.html')

@login_required
def lobby(request):
    print(f"Current user: {request.user}")
    # Try to join an existing lobby
    # lobby = Lobby.objects.filter(player2__isnull=True).first()
    lobby = Lobby.objects.filter(player1=request.user).first() or Lobby.objects.filter(player2=request.user).first()

    if not lobby:
        open_lobby = Lobby.objects.filter(player2__isnull=True).first()
        if open_lobby:
            print(f"Joining existing lobby as Player2: {request.user}")
            open_lobby.player2 = request.user
            open_lobby.save()
            lobby = open_lobby
        else:
            print(f"Creating new lobby as Player1: {request.user}")
            lobby = Lobby.objects.create(player1=request.user)

    # print(request.user)
    # if lobby:
    #     print("going to existing lobby")
    #     lobby.player2 = request.user
    #     lobby.save()
    # else:
    #     print("creating lobby")
    #     lobby = Lobby.objects.create(player1=request.user)
    print(f"Lobby: Player1={lobby.player1}, Player2={lobby.player2}")
    if request.method == 'POST':
        print(f"Handling POST request for user: {request.user}")
        print(f"Lobby before update: Player1={lobby.player1}, Player1 Ready={lobby.player1_ready}, Player2={lobby.player2}, Player2 Ready={lobby.player2_ready}")
        if lobby.player1 == request.user:
            print("Updating Player1 ready status")
            lobby.player1_ready = True
        elif lobby.player2 == request.user:
            print("Updating Player2 ready status")
            lobby.player2_ready = True
        lobby.save()
        print(f"Lobby after update: Player1={lobby.player1}, Player1 Ready={lobby.player1_ready}, Player2={lobby.player2}, Player2 Ready={lobby.player2_ready}")

        # if lobby.all_ready():
        #     print("Both players are ready. Creating game state.")
        #     game_state = GameState.objects.create(lobby=lobby)
        if lobby.all_ready():
            print("Both players are ready. Creating game state.")
            game_state = GameState.objects.create(lobby=lobby)
            print(f"GameState created: {game_state.id}")
            lobby.game_state = game_state
            lobby.save()
            print(f"Lobby updated with GameState: {lobby.game_state.id}")
            # return JsonResponse({
            #     'is_full': True,
            #     'all_ready': True,
            #     'game_state_id': game_state.id,
            #     'player1': lobby.player1.username,
            #     'player1_ready': lobby.player1_ready,
            #     'player2': lobby.player2.username if lobby.player2 else None,
            #     'player2_ready': lobby.player2_ready if lobby.player2 else False,
            #     'csrf_token': request.COOKIES['csrftoken']
            # })
            # return redirect('game_board', game_state_id=game_state.id)
                # Return the updated lobby status
        return JsonResponse({
            'is_full': lobby.player2 is not None,
            'all_ready': lobby.all_ready(),
            'player1': lobby.player1.username,
            'player1_ready': lobby.player1_ready,
            'player2': lobby.player2.username if lobby.player2 else None,
            'player2_ready': lobby.player2_ready if lobby.player2 else False,
            'csrf_token': request.COOKIES['csrftoken']
        })

    return render(request, 'set_game/lobby.html', {'lobby': lobby})



# def game_board(request):
#     # Fetch some cards to display (for now, fetch the first 12 cards)
#     cards = Card.objects.all()[:12]
#     return render(request, 'set_game/game_board.html', {'cards': cards})

@login_required
def game_board(request, game_state_id):
    game_state = GameState.objects.get(id=game_state_id)
    return render(request, 'set_game/game_board.html', {'game_state': game_state})


def lobby_status(request, lobby_id):
    try:
        lobby = Lobby.objects.get(id=lobby_id)
        lobby.refresh_from_db()  # Ensure the latest data is fetched
        if hasattr(lobby, 'game_state'):
            print(f"lobby.game_state from lobby_status id {lobby.game_state}")
        data = {
            'player1': lobby.player1.username if lobby.player1 else None,
            'player1_ready': lobby.player1_ready if lobby.player1 else None,
            'player2': lobby.player2.username if lobby.player2 else None,
            'player2_ready': lobby.player2_ready if lobby.player2 else None,
            'is_full': lobby.player2 is not None,
            'all_ready': lobby.all_ready() if lobby.player2 else False,
            'csrf_token': request.META.get('CSRF_COOKIE'),
            'game_state_id': lobby.game_state.id if hasattr(lobby, 'game_state') and lobby.game_state else None,
        }
        return JsonResponse(data)
    except Lobby.DoesNotExist:
        return JsonResponse({'error': 'Lobby not found'}, status=404)
    except Exception as e:
        # Log the exception for debugging
        print(f"Error in lobby_status view: {e}")
        return JsonResponse({'error': 'An unexpected error occurred.'}, status=500)
