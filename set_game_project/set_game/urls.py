from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("lobby/", views.lobby, name="lobby"),
    path("game/<int:game_state_id>/", views.game_board, name="game_board"),
    path("api/lobby_status/<int:lobby_id>/", views.lobby_status, name="lobby_status"),
    path("game/", views.game_board, name="game_board"),
]
