import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter  # type: ignore
from channels.auth import AuthMiddlewareStack  # type: ignore


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "set_game_project.settings")

django_asgi_app = get_asgi_application()
import set_game.routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(set_game.routing.websocket_urlpatterns)
        ),
    }
)
