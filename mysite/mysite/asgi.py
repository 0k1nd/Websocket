
import os
import django
django.setup()
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from chat.middleware import JwtAuthMiddleware
from chat import routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')



application = ProtocolTypeRouter({
  "http": get_asgi_application(),
  "websocket":URLRouter(
            routing.websocket_urlpatterns
    ),
})